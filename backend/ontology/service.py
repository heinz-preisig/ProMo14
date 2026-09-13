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
    store = get_store()
    if not record.iri:
        record.iri = str(store.mint_iri("http://example.org/ontology", f"domain_{record.name}"))
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
    """Delete a domain from the ontology graph."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Domain not found")
    graph.remove((subject, None, None))
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
    graph.remove((subject, None, None))
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
    store = get_store()
    if not record.iri:
        fragment = record.label.lower().replace(" ", "_")
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
    """Delete a token type from the ontology graph."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Token not found")
    graph.remove((subject, None, None))
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
    store = get_store()
    if not record.iri:
        fragment = f"axis_{record.name}"
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
    graph.remove((subject, None, None))
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
    store = get_store()
    if not record.iri:
        fragment = f"term_{record.label.lower().replace(' ', '_')}"
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
    """Delete an axis term."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Axis term not found")
    graph.remove((subject, None, None))
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
    store = get_store()
    if not record.iri:
        fragment = f"scale_{record.name}"
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
    graph.remove((subject, None, None))
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
    store = get_store()
    if not record.iri:
        fragment = f"sval_{record.label.lower().replace(' ', '_')}"
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
    """Delete a scale value."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Scale value not found")
    graph.remove((subject, None, None))
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
    store = get_store()
    if not record.iri:
        fragment = f"etype_{record.label.lower().replace(' ', '_')}"
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
    graph.remove((subject, None, None))
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
    store = get_store()
    if not record.iri:
        fragment = f"rule_{record.rule_type}"
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
    graph.remove((subject, None, None))
    return {"deleted": iri}


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
    """Load domain records from the graph."""
    store = get_store()
    graph = store.ontology_graph
    records = []
    for s in graph.subjects(RDF.type, PROMO["Domain"]):
        name = graph.value(s, PROMO["name"])
        parent = graph.value(s, PROMO["parent"])
        branch = graph.value(s, PROMO["branch"])
        tokens = [str(t) for t in graph.objects(s, PROMO["hasToken"])]
        records.append(
            DomainRecord(
                iri=str(s),
                name=str(name) if name else "",
                parent=str(parent) if parent else None,
                branch=str(branch) if branch else None,
                tokens=tokens,
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
