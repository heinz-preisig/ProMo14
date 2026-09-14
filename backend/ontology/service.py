"""Ontology editor FastAPI service.

CRUD endpoints for networks, variables, indices, tokens, and equations.  All
state lives in the shared ``RdfStore``; the ontology graph is saved to
``PROMO_DATA_DIR`` on request or on publish.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rdflib import URIRef
from rdflib.namespace import RDF, RDFS

from backend.core.graph_store import PROMO, get_store
from backend.ontology.rdf_context import RdfContext

from .models import (
    AxisTermRecord,
    ClassificationAxisRecord,
    ConnectionRuleRecord,
    DomainRecord,
    EntityTypeRecord,
    IndexRecord,
    NetworkRecord,
    ScaleDimensionRecord,
    ScaleValueRecord,
    SaveRequest,
    TokenRecord,
    VariableRecord,
)

router = APIRouter()


# Predicates that define containment: deleting the object also deletes the
# subject (e.g. deleting an axis deletes its terms, deleting a domain deletes
# its subdomains, axes, and scale dimensions).
_CONTAINMENT_PREDICATES = (
    PROMO["parent"],     # subdomains, sub-tokens, sub-terms, sub-scale-values
    PROMO["hasAxis"],    # axis terms belong to their axis
    PROMO["hasScale"],   # scale values belong to their dimension
    PROMO["hasDomain"],  # axes and scale dimensions belong to their domain
)


def _cascade_delete(graph, subject: URIRef) -> None:
    """Remove subject, all contained descendants, and all incoming references.

    Contained descendants (linked via _CONTAINMENT_PREDICATES) are deleted
    recursively.  Any other triple pointing at the subject (e.g. a domain's
    hasToken link to a deleted token) is removed so no dangling references
    remain.
    """
    children = set()
    for pred in _CONTAINMENT_PREDICATES:
        children.update(graph.subjects(pred, subject))
    graph.remove((subject, None, None))   # outgoing triples
    graph.remove((None, None, subject))   # incoming references
    for child in children:
        _cascade_delete(graph, child)


def _variable_to_record(v) -> Dict[str, Any]:
    return {
        "iri": v.iri,
        "label": v.label,
        "network": v.network,
        "variable_class": getattr(v, "type", None),
        "classifications": getattr(v, "classifications", {}),
        "units": v.units.as_list(),
        "index_structures": v.index_structures,
        "internal_id": v.internal_id,
        "aliases": v.aliases,
        "doc": v.doc,
        "port_variable": v.port_variable,
        "tokens": v.tokens,
        "imported": getattr(v, "imported", False),
        "equations": getattr(v, "equations", {}),
        "compiled_lhs": getattr(v, "compiled_lhs", None),
        "memory": getattr(v, "memory", None),
        "created": getattr(v, "created", None),
        "modified": getattr(v, "modified", None),
    }


def _index_to_record(i) -> Dict[str, Any]:
    return {
        "iri": i.iri,
        "label": i.label,
        "network": i.network,
        "index_class": i.index_class,
        "internal_id": i.internal_id,
        "aliases": i.aliases,
        "token": i.token,
        "short_name": i.aliases.get("internal_code") or i.label[0]
        if i.label
        else None,
    }


class ContextResponse(BaseModel):
    variables: List[VariableRecord] = []
    indices: List[IndexRecord] = []
    network_tree: Dict[str, List[str]] = {}
    domains: List[DomainRecord] = []
    axes: List[ClassificationAxisRecord] = []
    scale_dimensions: List[ScaleDimensionRecord] = []
    entity_types: List[EntityTypeRecord] = []
    connection_rules: List[ConnectionRuleRecord] = []


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


@router.get("/context", response_model=ContextResponse)
def get_context() -> ContextResponse:
    """Return the current ontology context (variables, indices, domains, axes, entity types, connection rules)."""
    ctx = RdfContext(get_store())
    return ContextResponse(
        variables=[_variable_to_record(v) for v in ctx.variables().values()],
        indices=[_index_to_record(i) for i in ctx.indices().values()],
        network_tree=ctx.tree(),
        domains=_list_domain_records(ctx),
        axes=_list_axis_records(ctx),
        scale_dimensions=_list_scale_dimension_records(ctx),
        entity_types=_list_entity_type_records(ctx),
        connection_rules=_list_connection_rule_records(ctx),
    )


# ---------------------------------------------------------------------------
# Domains (new — two-branch tree)
# ---------------------------------------------------------------------------


@router.get("/domains", response_model=List[DomainRecord])
def list_domains() -> List[DomainRecord]:
    """List all domains with branch and token bindings."""
    ctx = RdfContext(get_store())
    return _list_domain_records(ctx)


@router.post("/domains", response_model=DomainRecord)
def create_domain(record: DomainRecord) -> DomainRecord:
    """Create or update a domain with branch and token bindings."""
    if not record.name or not record.name.strip():
        raise HTTPException(status_code=422, detail="Domain name must not be empty")
    store = get_store()
    if not record.iri:
        record.iri = str(store.mint_iri("http://example.org/ontology", f"domain_{record.name.strip()}"))
    store.add_domain(
        store.ontology_graph,
        record.name,
        iri=URIRef(record.iri),
        parent=record.parent,
        branch=record.branch,
        tokens=record.tokens or [],
    )
    return record


@router.delete("/domains/{iri:path}")
def delete_domain(iri: str) -> Dict[str, str]:
    """Delete a domain and all its subdomains from the ontology graph."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Domain not found")
    _cascade_delete(graph, subject)
    return {"deleted": iri}


# ---------------------------------------------------------------------------
# Networks (legacy — kept for backward compat)
# ---------------------------------------------------------------------------


@router.get("/networks", response_model=List[NetworkRecord])
def list_networks() -> List[NetworkRecord]:
    """List all networks as a flat list with parent/children references."""
    ctx = RdfContext(get_store())
    tree = ctx.tree()
    parent_of = ctx._parent_of
    records = []
    for name, children in tree.items():
        records.append(
            NetworkRecord(
                iri=f"http://example.org/ontology#network_{name}",
                name=name,
                parent=parent_of.get(name),
                children=children,
            )
        )
    return records


@router.post("/networks", response_model=NetworkRecord)
def create_network(record: NetworkRecord) -> NetworkRecord:
    """Create or update a network and its parent/children relationships."""
    store = get_store()
    store.add_network(
        store.ontology_graph,
        record.name,
        parent=record.parent,
        children=record.children or [],
    )
    return record


# ---------------------------------------------------------------------------
# Indices
# ---------------------------------------------------------------------------


@router.get("/indices", response_model=List[IndexRecord])
def list_indices() -> List[IndexRecord]:
    """List all indices in the ontology."""
    ctx = RdfContext(get_store())
    return [IndexRecord(**_index_to_record(i)) for i in ctx.indices().values()]


@router.post("/indices", response_model=IndexRecord)
def create_index(record: IndexRecord) -> IndexRecord:
    """Create a new index in the ontology graph."""
    if not record.label or not record.label.strip():
        raise HTTPException(status_code=422, detail="Index label must not be empty")
    store = get_store()
    if not record.iri:
        record.iri = str(store.mint_iri("http://example.org/ontology", record.internal_id or store.next_internal_id("I")))
    if not record.aliases.get("global_ID"):
        record.aliases["global_ID"] = store.next_internal_id("I")
    if not record.aliases.get("internal_code"):
        record.aliases["internal_code"] = record.short_name or (record.label[0] if record.label else "I")
    store.add_index_dict(store.ontology_graph, record.model_dump())
    return record


@router.delete("/indices/{iri:path}")
def delete_index(iri: str) -> Dict[str, str]:
    """Delete an index from the ontology graph."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Index not found")
    _cascade_delete(graph, subject)
    return {"deleted": iri}


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


@router.get("/tokens", response_model=List[TokenRecord])
def list_tokens() -> List[TokenRecord]:
    """List token types defined in the ontology."""
    store = get_store()
    graph = store.ontology_graph
    records = []
    for s in graph.subjects(RDF.type, PROMO["Token"]):
        label = graph.value(s, PROMO["label"]) or graph.value(s, RDFS.label)
        parent = graph.value(s, PROMO["parent"])
        records.append(
            TokenRecord(
                iri=str(s),
                label=str(label) if label else "",
                parent=str(parent) if parent else None,
            )
        )
    return records


@router.post("/tokens", response_model=TokenRecord)
def create_token(record: TokenRecord) -> TokenRecord:
    """Create or update a token type."""
    if not record.label or not record.label.strip():
        raise HTTPException(status_code=422, detail="Token label must not be empty")
    store = get_store()
    if not record.iri:
        fragment = record.label.strip().lower().replace(" ", "_")
        record.iri = str(store.mint_iri("http://example.org/ontology", f"token_{fragment}"))
    store.add_token(
        store.ontology_graph,
        URIRef(record.iri),
        record.label,
        parent=URIRef(record.parent) if record.parent else None,
    )
    return record


@router.delete("/tokens/{iri:path}")
def delete_token(iri: str) -> Dict[str, str]:
    """Delete a token type and all child tokens from the ontology graph."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Token not found")
    _cascade_delete(graph, subject)
    return {"deleted": iri}


# ---------------------------------------------------------------------------
# Classification axes
# ---------------------------------------------------------------------------


@router.get("/axes", response_model=List[ClassificationAxisRecord])
def list_axes() -> List[ClassificationAxisRecord]:
    """List all classification axes."""
    ctx = RdfContext(get_store())
    return _list_axis_records(ctx)


@router.post("/axes", response_model=ClassificationAxisRecord)
def create_axis(record: ClassificationAxisRecord) -> ClassificationAxisRecord:
    """Create or update a classification axis."""
    if not record.name or not record.name.strip():
        raise HTTPException(status_code=422, detail="Axis name must not be empty")
    store = get_store()
    if not record.iri:
        fragment = f"axis_{record.name.strip()}"
        record.iri = str(store.mint_iri("http://example.org/ontology", fragment))
    store.add_classification_axis(
        store.ontology_graph,
        URIRef(record.iri),
        record.domain,
        record.name,
        parent=record.parent,
    )
    return record


@router.delete("/axes/{iri:path}")
def delete_axis(iri: str) -> Dict[str, str]:
    """Delete a classification axis."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Axis not found")
    _cascade_delete(graph, subject)
    return {"deleted": iri}


@router.get("/axis-terms", response_model=List[AxisTermRecord])
def list_axis_terms() -> List[AxisTermRecord]:
    """List all axis terms."""
    store = get_store()
    graph = store.ontology_graph
    records = []
    for s in graph.subjects(RDF.type, PROMO["AxisTerm"]):
        label = graph.value(s, PROMO["label"])
        axis = graph.value(s, PROMO["hasAxis"])
        parent = graph.value(s, PROMO["parent"])
        records.append(
            AxisTermRecord(
                iri=str(s),
                axis=str(axis) if axis else "",
                label=str(label) if label else "",
                parent=str(parent) if parent else None,
            )
        )
    return records


@router.post("/axis-terms", response_model=AxisTermRecord)
def create_axis_term(record: AxisTermRecord) -> AxisTermRecord:
    """Create or update an axis term."""
    if not record.label or not record.label.strip():
        raise HTTPException(status_code=422, detail="Axis term label must not be empty")
    store = get_store()
    if not record.iri:
        fragment = f"term_{record.label.strip().lower().replace(' ', '_')}"
        record.iri = str(store.mint_iri("http://example.org/ontology", fragment))
    store.add_axis_term(
        store.ontology_graph,
        URIRef(record.iri),
        record.axis,
        record.label,
        parent=record.parent,
    )
    return record


@router.delete("/axis-terms/{iri:path}")
def delete_axis_term(iri: str) -> Dict[str, str]:
    """Delete an axis term and all its child terms."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Axis term not found")
    _cascade_delete(graph, subject)
    return {"deleted": iri}


# ---------------------------------------------------------------------------
# Scale dimensions + values
# ---------------------------------------------------------------------------


@router.get("/scale-dimensions", response_model=List[ScaleDimensionRecord])
def list_scale_dimensions() -> List[ScaleDimensionRecord]:
    """List all scale dimensions with their values."""
    ctx = RdfContext(get_store())
    return _list_scale_dimension_records(ctx)


@router.post("/scale-dimensions", response_model=ScaleDimensionRecord)
def create_scale_dimension(record: ScaleDimensionRecord) -> ScaleDimensionRecord:
    """Create or update a scale dimension."""
    if not record.name or not record.name.strip():
        raise HTTPException(status_code=422, detail="Scale dimension name must not be empty")
    store = get_store()
    if not record.iri:
        fragment = f"scale_{record.name.strip()}"
        record.iri = str(store.mint_iri("http://example.org/ontology", fragment))
    store.add_scale_dimension(
        store.ontology_graph,
        URIRef(record.iri),
        record.name,
        record.domain,
        parent=record.parent,
    )
    return record


@router.delete("/scale-dimensions/{iri:path}")
def delete_scale_dimension(iri: str) -> Dict[str, str]:
    """Delete a scale dimension."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Scale dimension not found")
    _cascade_delete(graph, subject)
    return {"deleted": iri}


@router.get("/scale-values", response_model=List[ScaleValueRecord])
def list_scale_values() -> List[ScaleValueRecord]:
    """List all scale values."""
    store = get_store()
    graph = store.ontology_graph
    records = []
    for s in graph.subjects(RDF.type, PROMO["ScaleValue"]):
        label = graph.value(s, PROMO["scaleValueLabel"])
        dimension = graph.value(s, PROMO["hasScale"])
        parent = graph.value(s, PROMO["parent"])
        records.append(
            ScaleValueRecord(
                iri=str(s),
                dimension=str(dimension) if dimension else "",
                label=str(label) if label else "",
                parent=str(parent) if parent else None,
            )
        )
    return records


@router.post("/scale-values", response_model=ScaleValueRecord)
def create_scale_value(record: ScaleValueRecord) -> ScaleValueRecord:
    """Create or update a scale value."""
    if not record.label or not record.label.strip():
        raise HTTPException(status_code=422, detail="Scale value label must not be empty")
    store = get_store()
    if not record.iri:
        fragment = f"sval_{record.label.strip().lower().replace(' ', '_')}"
        record.iri = str(store.mint_iri("http://example.org/ontology", fragment))
    store.add_scale_value(
        store.ontology_graph,
        URIRef(record.iri),
        record.dimension,
        record.label,
        parent=record.parent,
    )
    return record


@router.delete("/scale-values/{iri:path}")
def delete_scale_value(iri: str) -> Dict[str, str]:
    """Delete a scale value and all its child values."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Scale value not found")
    _cascade_delete(graph, subject)
    return {"deleted": iri}


# ---------------------------------------------------------------------------
# Entity types (CWA 17960)
# ---------------------------------------------------------------------------


@router.get("/entity-types", response_model=List[EntityTypeRecord])
def list_entity_types() -> List[EntityTypeRecord]:
    """List all entity types."""
    ctx = RdfContext(get_store())
    return _list_entity_type_records(ctx)


@router.post("/entity-types", response_model=EntityTypeRecord)
def create_entity_type(record: EntityTypeRecord) -> EntityTypeRecord:
    """Create or update an entity type."""
    if not record.label or not record.label.strip():
        raise HTTPException(status_code=422, detail="Entity type label must not be empty")
    store = get_store()
    if not record.iri:
        fragment = f"etype_{record.label.strip().lower().replace(' ', '_')}"
        record.iri = str(store.mint_iri("http://example.org/ontology", fragment))
    store.add_entity_type(
        store.ontology_graph,
        URIRef(record.iri),
        record.label,
        record.temporal_type,
        record.branch,
        spatial_type=record.spatial_type,
        spatial_size=record.spatial_size,
        description=record.description,
    )
    return record


@router.delete("/entity-types/{iri:path}")
def delete_entity_type(iri: str) -> Dict[str, str]:
    """Delete an entity type."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Entity type not found")
    _cascade_delete(graph, subject)
    return {"deleted": iri}


# ---------------------------------------------------------------------------
# Connection rules
# ---------------------------------------------------------------------------


@router.get("/connection-rules", response_model=List[ConnectionRuleRecord])
def list_connection_rules() -> List[ConnectionRuleRecord]:
    """List all connection rules."""
    ctx = RdfContext(get_store())
    return _list_connection_rule_records(ctx)


@router.post("/connection-rules", response_model=ConnectionRuleRecord)
def create_connection_rule(record: ConnectionRuleRecord) -> ConnectionRuleRecord:
    """Create or update a connection rule."""
    if not record.rule_type or not record.rule_type.strip():
        raise HTTPException(status_code=422, detail="Connection rule type must not be empty")
    store = get_store()
    if not record.iri:
        fragment = f"rule_{record.rule_type.strip()}"
        record.iri = str(store.mint_iri("http://example.org/ontology", fragment))
    store.add_connection_rule(
        store.ontology_graph,
        URIRef(record.iri),
        record.rule_type,
        direction=record.direction,
        source_domain=record.source_domain,
        target_domain=record.target_domain,
        shared_tokens=record.shared_tokens or [],
        description=record.description,
    )
    return record


@router.delete("/connection-rules/{iri:path}")
def delete_connection_rule(iri: str) -> Dict[str, str]:
    """Delete a connection rule."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Connection rule not found")
    _cascade_delete(graph, subject)
    return {"deleted": iri}


# ---------------------------------------------------------------------------
# Connection rule resolution (ancestor-aware matching)
# ---------------------------------------------------------------------------


def _domain_ancestor_chain(graph, iri: str) -> List[str]:
    """Return ``[iri, parent, grandparent, ...]`` walking the parent chain."""
    chain: List[str] = []
    seen = set()
    current = URIRef(iri)
    while current is not None and str(current) not in seen:
        seen.add(str(current))
        chain.append(str(current))
        current = graph.value(current, PROMO["parent"])
    return chain


def _rule_domain_match(rule: ConnectionRuleRecord,
                       src_chain: List[str],
                       tgt_chain: List[str]) -> bool:
    """Check a rule's domain constraints against ancestor chains.

    A constrained rule applies when its ``source_domain``/``target_domain``
    is the actual domain or one of its ancestors.  Bidirectional rules also
    match the swapped pair.
    """
    def ok(s_chain: List[str], t_chain: List[str]) -> bool:
        return (
            (not rule.source_domain or rule.source_domain in s_chain)
            and (not rule.target_domain or rule.target_domain in t_chain)
        )

    if ok(src_chain, tgt_chain):
        return True
    if rule.direction == "bidirectional":
        return ok(tgt_chain, src_chain)
    return False


@router.get("/resolve-connection")
def resolve_connection(source: str, target: str) -> Dict[str, Any]:
    """Return connection rules applicable to a source→target domain pair.

    Rules stay attached to the domain where they are defined; a rule applies
    to a pair when its domain constraints are ancestors (or self) of the
    actual endpoint domains.  Unconstrained rules are filtered by
    ``rule_type``: ``physical-same`` requires the endpoints to share a common
    ancestor domain, ``physical-cross`` requires they do not.  Results are
    ordered most-specific first (closest ancestor match wins).
    """
    store = get_store()
    graph = store.ontology_graph
    src_chain = _domain_ancestor_chain(graph, source)
    tgt_chain = _domain_ancestor_chain(graph, target)
    common = set(src_chain) & set(tgt_chain)

    ctx = RdfContext(store)
    scored = []
    for rule in _list_connection_rule_records(ctx):
        if not _rule_domain_match(rule, src_chain, tgt_chain):
            continue
        if rule.rule_type == "physical-same" and not common:
            continue
        if rule.rule_type == "physical-cross" and common:
            continue
        # Specificity: distance of the constrained domains up the chains.
        # Unconstrained rules sort last.
        spec = (
            src_chain.index(rule.source_domain)
            if rule.source_domain else len(src_chain)
        ) + (
            tgt_chain.index(rule.target_domain)
            if rule.target_domain else len(tgt_chain)
        )
        scored.append((spec, rule))
    scored.sort(key=lambda m: m[0])
    return {
        "source": source,
        "target": target,
        "rules": [r.model_dump() for _, r in scored],
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


@router.post("/save")
def save_ontology(req: SaveRequest) -> Dict[str, str]:
    """Serialise the current ontology to ``PROMO_DATA_DIR/filename``."""
    store = get_store()
    path = store.save(req.filename)
    return {"saved": str(path)}


# ---------------------------------------------------------------------------
# Helper functions for loading new entity types from the graph
# ---------------------------------------------------------------------------


def _list_domain_records(ctx) -> List[DomainRecord]:
    """Load domain records from the graph, resolving inherited tokens."""
    store = get_store()
    graph = store.ontology_graph

    def _own_tokens(iri: URIRef) -> List[str]:
        return [str(t) for t in graph.objects(iri, PROMO["hasToken"])]

    def _ancestor_tokens(iri: URIRef, visited: set) -> List[str]:
        """Collect tokens from all ancestors, avoiding cycles."""
        parent = graph.value(iri, PROMO["parent"])
        if parent is None or str(parent) in visited:
            return []
        visited.add(str(parent))
        return _own_tokens(parent) + _ancestor_tokens(parent, visited)

    records = []
    for s in graph.subjects(RDF.type, PROMO["Domain"]):
        name = graph.value(s, PROMO["name"])
        parent = graph.value(s, PROMO["parent"])
        branch = graph.value(s, PROMO["branch"])
        own = _own_tokens(s)
        inherited = [t for t in _ancestor_tokens(s, {str(s)}) if t not in own]
        records.append(
            DomainRecord(
                iri=str(s),
                name=str(name) if name else "",
                parent=str(parent) if parent else None,
                branch=str(branch) if branch else None,
                tokens=own,
                inherited_tokens=list(dict.fromkeys(inherited)),  # deduplicated, order preserved
            )
        )
    return records


def _list_axis_records(ctx) -> List[ClassificationAxisRecord]:
    """Load classification axes with their terms from the graph."""
    store = get_store()
    graph = store.ontology_graph
    records = []
    for s in graph.subjects(RDF.type, PROMO["ClassificationAxis"]):
        name = graph.value(s, PROMO["axisName"])
        domain = graph.value(s, PROMO["hasDomain"])
        parent = graph.value(s, PROMO["parent"])
        # Load terms for this axis
        terms = []
        for term_s in graph.subjects(PROMO["hasAxis"], s):
            term_label = graph.value(term_s, PROMO["label"]) or graph.value(term_s, RDFS.label)
            term_parent = graph.value(term_s, PROMO["parent"])
            terms.append(
                AxisTermRecord(
                    iri=str(term_s),
                    axis=str(s),
                    label=str(term_label) if term_label else "",
                    parent=str(term_parent) if term_parent else None,
                )
            )
        records.append(
            ClassificationAxisRecord(
                iri=str(s),
                domain=str(domain) if domain else "",
                name=str(name) if name else "",
                parent=str(parent) if parent else None,
                terms=terms,
            )
        )
    return records


def _list_scale_dimension_records(ctx) -> List[ScaleDimensionRecord]:
    """Load scale dimensions with their values from the graph."""
    store = get_store()
    graph = store.ontology_graph
    records = []
    for s in graph.subjects(RDF.type, PROMO["ScaleDimension"]):
        name = graph.value(s, PROMO["scaleName"])
        domain = graph.value(s, PROMO["hasDomain"])
        parent = graph.value(s, PROMO["parent"])
        # Load values for this dimension
        values = []
        for val_s in graph.subjects(PROMO["hasScale"], s):
            val_label = graph.value(val_s, PROMO["scaleValueLabel"])
            val_parent = graph.value(val_s, PROMO["parent"])
            values.append(
                ScaleValueRecord(
                    iri=str(val_s),
                    dimension=str(s),
                    label=str(val_label) if val_label else "",
                    parent=str(val_parent) if val_parent else None,
                )
            )
        records.append(
            ScaleDimensionRecord(
                iri=str(s),
                name=str(name) if name else "",
                domain=str(domain) if domain else "",
                parent=str(parent) if parent else None,
                values=values,
            )
        )
    return records


def _list_entity_type_records(ctx) -> List[EntityTypeRecord]:
    """Load entity types from the graph."""
    store = get_store()
    graph = store.ontology_graph
    records = []
    for s in graph.subjects(RDF.type, PROMO["EntityType"]):
        label = graph.value(s, PROMO["label"])
        temporal = graph.value(s, PROMO["temporalType"])
        spatial_type = graph.value(s, PROMO["spatialType"])
        spatial_size = graph.value(s, PROMO["spatialSize"])
        branch = graph.value(s, PROMO["branch"])
        doc = graph.value(s, PROMO["doc"])
        scale_values = [str(sv) for sv in graph.objects(s, PROMO["hasScaleValue"])]
        records.append(
            EntityTypeRecord(
                iri=str(s),
                label=str(label) if label else "",
                temporal_type=str(temporal) if temporal else "",
                spatial_type=str(spatial_type) if spatial_type else None,
                spatial_size=str(spatial_size) if spatial_size else None,
                branch=str(branch) if branch else "",
                scale_values=scale_values,
                description=str(doc) if doc else "",
            )
        )
    return records


def _list_connection_rule_records(ctx) -> List[ConnectionRuleRecord]:
    """Load connection rules from the graph."""
    store = get_store()
    graph = store.ontology_graph
    records = []
    for s in graph.subjects(RDF.type, PROMO["ConnectionRule"]):
        rule_type = graph.value(s, PROMO["ruleType"])
        direction = graph.value(s, PROMO["direction"])
        source = graph.value(s, PROMO["sourceDomain"])
        target = graph.value(s, PROMO["targetDomain"])
        tokens = [str(t) for t in graph.objects(s, PROMO["sharedTokens"])]
        doc = graph.value(s, PROMO["doc"])
        records.append(
            ConnectionRuleRecord(
                iri=str(s),
                rule_type=str(rule_type) if rule_type else "",
                source_domain=str(source) if source else None,
                target_domain=str(target) if target else None,
                shared_tokens=tokens,
                direction=str(direction) if direction else None,
                description=str(doc) if doc else "",
            )
        )
    return records
