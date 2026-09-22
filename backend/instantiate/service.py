"""Instantiation service — resolves a model artefact's topology.

``GET /arc-indices?graph=`` runs the §16 membership resolution over the
model graph's ``ModelNode``/``ModelArc`` resources: each token-flow arc
is assigned to every arc sub-index whose ``selector`` entity type
matches an incident node's type or one of its ``promo:parent``
ancestors.  Entity types and indices are read across the artefact's
resolution scope (itself + ``usesOntology`` pins).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import Depends
from pydantic import BaseModel, Field
from rdflib import RDF, URIRef

from backend.core.graph_store import PROMO, get_store
from backend.ontology.service import graph_param, resolve_graph

from . import router
from .resolver import (
    ArcInfo,
    NodeInfo,
    SubIndexInfo,
    arc_carrier,
    by_sub_index,
    resolve,
)


class ArcMembershipOut(BaseModel):
    arc: str
    carrier: Optional[str] = None
    sub_indices: List[str] = Field(default_factory=list)
    touches: List[str] = Field(default_factory=list)
    reference_from: Optional[str] = None
    reference_to: Optional[str] = None


class ArcIndexReport(BaseModel):
    arcs: List[ArcMembershipOut] = Field(default_factory=list)
    by_sub_index: Dict[str, List[str]] = Field(default_factory=dict)
    labels: Dict[str, str] = Field(default_factory=dict)


def _collect(store, model_graph):
    """Adapt the model graph + its resolution scope into resolver input."""
    nodes: Dict[str, NodeInfo] = {}
    arcs: Dict[str, ArcInfo] = {}
    for s in model_graph.subjects(RDF.type, PROMO["ModelNode"]):
        et = model_graph.value(s, PROMO["entityType"])
        nodes[str(s)] = NodeInfo(
            iri=str(s), entity_type=str(et) if et else None)
    for s in model_graph.subjects(RDF.type, PROMO["ModelArc"]):
        src = model_graph.value(s, PROMO["source"])
        tgt = model_graph.value(s, PROMO["target"])
        at = model_graph.value(s, PROMO["arcType"])
        rf = model_graph.value(s, PROMO["referenceFrom"])
        rt = model_graph.value(s, PROMO["referenceTo"])
        arcs[str(s)] = ArcInfo(
            iri=str(s),
            source=str(src) if src else None,
            target=str(tgt) if tgt else None,
            carrier=arc_carrier(str(at) if at else None),
            reference_from=str(rf) if rf else None,
            reference_to=str(rt) if rt else None,
        )

    # Ontology side: entity-type parent chain + arc sub-index selectors,
    # read across the artefact's resolution scope.
    parents: Dict[str, str] = {}
    sub_indices: Dict[str, SubIndexInfo] = {}
    labels: Dict[str, str] = {}
    scope = store.resolution_scope(model_graph.identifier)
    for graph_iri in scope:
        g = store.dataset.graph(graph_iri)
        for et in g.subjects(RDF.type, PROMO["EntityType"]):
            parent = g.value(et, PROMO["parent"])
            if parent is not None:
                parents.setdefault(str(et), str(parent))
        for idx in g.subjects(RDF.type, PROMO["Index"]):
            base = g.value(idx, PROMO["subIndexOf"])
            sel = g.value(idx, PROMO["selector"])
            if base is None or sel is None:
                continue
            iri = str(idx)
            if iri in sub_indices:
                continue
            sub_indices[iri] = SubIndexInfo(
                iri=iri,
                sub_index_of=str(base),
                selector=str(sel),
                short_name=str(
                    g.value(idx, PROMO["shortName"]) or ""),
            )
    return nodes, arcs, sub_indices, parents, labels


@router.get("/arc-indices", response_model=ArcIndexReport)
def arc_indices(
    graph_iri: Optional[str] = Depends(graph_param),
) -> ArcIndexReport:
    """Sub-index membership for every arc in the model artefact."""
    store = get_store()
    model_graph = resolve_graph(store, graph_iri)
    nodes, arcs, sub_indices, parents, labels = _collect(
        store, model_graph)
    memberships = resolve(nodes, arcs, sub_indices, parents)
    return ArcIndexReport(
        arcs=[ArcMembershipOut(
            arc=m.arc, carrier=m.carrier,
            sub_indices=m.sub_indices, touches=m.touches,
            reference_from=m.reference_from, reference_to=m.reference_to)
            for m in memberships],
        by_sub_index=by_sub_index(memberships),
        labels=labels,
    )
