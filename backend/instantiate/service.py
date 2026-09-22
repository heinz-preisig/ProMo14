"""Instantiation service — resolves a model artefact's topology.

``GET /arc-indices?graph=`` runs the §16 membership resolution over the
model graph's ``ModelNode``/``ModelArc`` resources: each token-flow arc
is assigned to every arc sub-index whose ``selector`` entity type
matches an incident node's type or one of its ``promo:parent``
ancestors.  Entity types and indices are read across the artefact's
resolution scope (itself + ``usesOntology`` pins).

``GET /incidence?graph=`` builds the §15 signed incidence matrices
``F[N,A]`` — the base matrix over all token-flow arcs plus one per
declared arc sub-index — from membership + reference directions.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import Depends
from pydantic import BaseModel, Field
from rdflib import RDF, RDFS, URIRef

from backend.core.graph_store import PROMO, get_store
from backend.ontology.service import graph_param, resolve_graph

from . import router
from .fbuilder import build
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


class IncidenceOut(BaseModel):
    """One ``F[N,A]`` matrix — sparse COO ``(row, col, ±1)`` entries."""

    index: str = ""
    short_name: str = ""
    nodes: List[str] = Field(default_factory=list)
    arcs: List[str] = Field(default_factory=list)
    entries: List[List[int]] = Field(default_factory=list)


class IncidenceReportOut(BaseModel):
    base: IncidenceOut
    sub_indices: List[IncidenceOut] = Field(default_factory=list)
    skipped: List[str] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)


def _collect(store, model_graph):
    """Adapt the model graph + its resolution scope into resolver input."""
    nodes: Dict[str, NodeInfo] = {}
    arcs: Dict[str, ArcInfo] = {}
    labels: Dict[str, str] = {}
    for s in model_graph.subjects(RDF.type, PROMO["ModelNode"]):
        et = model_graph.value(s, PROMO["entityType"])
        nodes[str(s)] = NodeInfo(
            iri=str(s), entity_type=str(et) if et else None)
        lbl = model_graph.value(s, RDFS.label)
        if lbl is not None:
            labels[str(s)] = str(lbl)
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
            short_name = str(g.value(idx, PROMO["shortName"]) or "")
            sub_indices[iri] = SubIndexInfo(
                iri=iri,
                sub_index_of=str(base),
                selector=str(sel),
                short_name=short_name,
            )
            if short_name:
                labels[iri] = short_name
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


@router.get("/incidence", response_model=IncidenceReportOut)
def incidence(
    graph_iri: Optional[str] = Depends(graph_param),
) -> IncidenceReportOut:
    """§15 signed incidence matrices F[N,A] for the model artefact.

    ``base`` covers every token-flow arc; ``sub_indices`` carries one
    matrix per declared arc sub-index (columns = member arcs).  All
    matrices share the same row space (``nodes``).  Entries are sparse
    ``[row, col, ±1]`` triples: +1 at the ``reference_to`` end, −1 at
    ``reference_from`` — ``F·f`` = net inflow per node.
    """
    store = get_store()
    model_graph = resolve_graph(store, graph_iri)
    nodes, arcs, sub_indices, parents, labels = _collect(
        store, model_graph)
    memberships = resolve(nodes, arcs, sub_indices, parents)
    report = build(nodes, arcs, memberships, sub_indices)

    def out(m) -> IncidenceOut:
        return IncidenceOut(
            index=m.index, short_name=m.short_name,
            nodes=m.nodes, arcs=m.arcs,
            entries=[list(e) for e in m.entries])

    return IncidenceReportOut(
        base=out(report.base),
        sub_indices=[out(m) for m in report.sub_indices],
        skipped=report.skipped,
        labels=labels,
    )
