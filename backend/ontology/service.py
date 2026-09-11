"""Ontology editor FastAPI service.

CRUD endpoints for networks, variables, indices, tokens, and equations.  All
state lives in the shared ``RdfStore``; the ontology graph is saved to
``PROMO_DATA_DIR`` on request or on publish.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.graph_store import get_store
from backend.ontology.rdf_context import RdfContext

from .models import (
    EquationRecord,
    IndexRecord,
    NetworkRecord,
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
        "variable_class": v.type,
        "units": v.units.as_list(),
        "index_structures": v.index_structures,
        "internal_id": v.internal_id,
        "aliases": v.aliases,
        "doc": v.doc,
        "port_variable": v.port_variable,
        "tokens": v.tokens,
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
    variables: List[Dict[str, Any]] = []
    indices: List[Dict[str, Any]] = []
    network_tree: Dict[str, List[str]] = {}


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


@router.get("/context", response_model=ContextResponse)
def get_context() -> ContextResponse:
    """Return the current ontology context (variables, indices, network tree)."""
    ctx = RdfContext(get_store())
    return ContextResponse(
        variables=[_variable_to_record(v) for v in ctx.variables().values()],
        indices=[_index_to_record(i) for i in ctx.indices().values()],
        network_tree=ctx.tree(),
    )


# ---------------------------------------------------------------------------
# Networks
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
# Variables
# ---------------------------------------------------------------------------


@router.get("/variables", response_model=List[VariableRecord])
def list_variables() -> List[VariableRecord]:
    """List all variables in the ontology."""
    ctx = RdfContext(get_store())
    return [VariableRecord(**_variable_to_record(v)) for v in ctx.variables().values()]


@router.post("/variables", response_model=VariableRecord)
def create_variable(record: VariableRecord) -> VariableRecord:
    """Create a new variable in the ontology graph."""
    store = get_store()
    if not record.iri:
        # Mint a stable IRI in the ontology namespace.
        record.iri = str(store.mint_iri("http://example.org/ontology", record.internal_id or store.next_internal_id("V")))
    if not record.internal_id:
        record.internal_id = store.next_internal_id("V")

    var = record.model_dump()
    var["type"] = var.pop("variable_class", "state")
    store.add_variable_dict(store.ontology_graph, var)
    return record


@router.put("/variables/{iri:path}", response_model=VariableRecord)
def update_variable(iri: str, record: VariableRecord) -> VariableRecord:
    """Replace a variable in the ontology graph."""
    store = get_store()
    graph = store.ontology_graph
    from rdflib import URIRef

    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Variable not found")

    # Remove the old triples for this variable but keep its identity.
    graph.remove((subject, None, None))
    record.iri = iri
    store.add_variable_dict(graph, record.model_dump())
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


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


@router.get("/tokens", response_model=List[TokenRecord])
def list_tokens() -> List[TokenRecord]:
    """List token types defined in the ontology."""
    store = get_store()
    graph = store.ontology_graph
    from rdflib import URIRef
    from rdflib.namespace import RDF
    from backend.core.graph_store import PROMO

    records = []
    for s in graph.subjects(RDF.type, PROMO["Token"]):
        label = graph.value(s, PROMO["label"]) or graph.value(s, "http://www.w3.org/2000/01/rdf-schema#label")
        parent = graph.value(s, PROMO["parent"])
        records.append(
            TokenRecord(
                iri=str(s),
                label=str(label) if label else "",
                parent=str(parent) if parent else None,
            )
        )
    return records


# ---------------------------------------------------------------------------
# Equations
# ---------------------------------------------------------------------------


@router.get("/equations", response_model=List[EquationRecord])
def list_equations() -> List[EquationRecord]:
    """List equations (stub — full query over named graphs is future work)."""
    return []


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


@router.post("/save")
def save_ontology(req: SaveRequest) -> Dict[str, str]:
    """Serialise the current ontology to ``PROMO_DATA_DIR/filename``."""
    store = get_store()
    path = store.save(req.filename)
    return {"saved": str(path)}
