"""Modeller model persistence — ADR-007.

The artefact graph (``?graph=``) is one model document.  ``GET`` reads
the flat topology + hierarchy + layout back into a ``ModelDocument``;
``PUT`` replaces the graph's model content wholesale (the reducer owns
whole-state, so document save/load — granular CRUD can come later).

RDF shape (see docs/ADR-007-model-persistence.md):

- ``promo:Model`` — one per graph: ``rootComposite``, ``nextTreeId``,
  ``arcCounter``.
- ``promo:ModelNode`` — ``entityType`` → entity-type IRI, label,
  ``internalID``.
- ``promo:ModelArc`` — ``source``/``target`` → ModelNode IRI,
  ``arcType`` → arc-type IRI, ``internalID``, and for token-flow arcs
  ``referenceFrom``/``referenceTo`` → ModelNode IRI: the §15 semantic
  reference direction (positive flow), independent of draw order.
- ``promo:Composite`` — ``internalID`` = tree id, label, ``parent`` →
  parent Composite (absent on root), ``children``/``layout``/
  ``knots``/``openArcs`` JSON literals.  Knots are per (view, arc):
  an arc renders differently on each GraphView.
- ``promo:speciesAlias`` — Component IRI → literal alias (§20): the
  model-local reading of an abstract species (``A`` :: ``H2O``).
  Statements about *external* subjects — the species artefact owns the
  vocabulary, the model owns its interpretation.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from fastapi import Depends
from pydantic import BaseModel, Field
from rdflib import RDF, RDFS, Literal, URIRef

from backend.core.graph_store import PROMO, get_store
from backend.ontology.service import editable_param, graph_param, resolve_graph

from . import router

_MODEL_TYPES = ("Model", "ModelNode", "ModelArc", "Composite")


# ---------------------------------------------------------------------------
# Document schema (mirrors the frontend's AppState, Maps → arrays)
# ---------------------------------------------------------------------------


class ModelNodeDoc(BaseModel):
    iri: str
    entityType: str = ""
    label: str = ""
    # §20 species placement (capability-gated in the modeller):
    speciesAllocation: Optional[str] = None  # reservoir → Allocation IRI
    reactions: List[str] = Field(default_factory=list)  # hosted Reaction IRIs


class ModelArcDoc(BaseModel):
    iri: str
    sourceIri: str = ""
    targetIri: str = ""
    arcType: str = ""
    # §15 reference direction (token-flow arcs only); absent = draw order
    referenceFrom: Optional[str] = None
    referenceTo: Optional[str] = None
    # §20 permeability (mass/species transport only): the species that
    # pass — absent = all pass (a strict subset = semipermeable wall).
    permeable: Optional[List[str]] = None  # Component IRIs


class ChildDoc(BaseModel):
    id: int
    iri: Optional[str] = None  # present → leaf referencing a ModelNode


class OpenArcDoc(BaseModel):
    iri: str
    externalIri: str = ""
    arcType: str = ""
    isSource: bool = False
    # §15: does the reference direction point toward the external node?
    # Boundary-relative so it survives the leaf→composite→leaf cycle.
    refToExternal: Optional[bool] = None


class CompositeDoc(BaseModel):
    treeId: int
    label: str = ""
    parentTreeId: Optional[int] = None
    children: List[ChildDoc] = Field(default_factory=list)
    layout: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    knots: Dict[str, List[Dict[str, float]]] = Field(default_factory=dict)
    openArcs: List[OpenArcDoc] = Field(default_factory=list)


class ModelDocument(BaseModel):
    nodes: List[ModelNodeDoc] = Field(default_factory=list)
    arcs: List[ModelArcDoc] = Field(default_factory=list)
    composites: List[CompositeDoc] = Field(default_factory=list)
    rootTreeId: int = 1
    nextTreeId: int = 1
    arcCounter: int = 1
    # §20 model-level species aliasing: Component IRI → local name.
    speciesAliases: Dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _composite_iri(graph, tree_id: int) -> URIRef:
    """Deterministic composite IRI — stable across save/load (ADR-007)."""
    return URIRef("%s/Composite_%d" % (str(graph.identifier).rstrip("/#"), tree_id))


def _model_iri(graph) -> URIRef:
    return URIRef("%s/Model" % str(graph.identifier).rstrip("/#"))


def _one(graph, s, p):
    v = graph.value(s, p)
    return str(v) if v is not None else None


def _json(graph, s, p, default):
    v = graph.value(s, p)
    if v is None:
        return default
    try:
        return json.loads(str(v))
    except (json.JSONDecodeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/model", response_model=ModelDocument)
def get_model(graph_iri: Optional[str] = Depends(graph_param)) -> ModelDocument:
    """Load the artefact graph's model document (empty doc if none)."""
    store = get_store()
    graph = resolve_graph(store, graph_iri)

    doc = ModelDocument()

    for s in graph.subjects(RDF.type, PROMO["ModelNode"]):
        doc.nodes.append(ModelNodeDoc(
            iri=str(s),
            entityType=_one(graph, s, PROMO["entityType"]) or "",
            label=_one(graph, s, RDFS.label) or "",
            speciesAllocation=_one(graph, s, PROMO["speciesAllocation"]),
            reactions=sorted(str(r) for r in
                             graph.objects(s, PROMO["hostsReaction"])),
        ))

    for s in graph.subjects(RDF.type, PROMO["ModelArc"]):
        doc.arcs.append(ModelArcDoc(
            iri=str(s),
            sourceIri=_one(graph, s, PROMO["source"]) or "",
            targetIri=_one(graph, s, PROMO["target"]) or "",
            arcType=_one(graph, s, PROMO["arcType"]) or "",
            referenceFrom=_one(graph, s, PROMO["referenceFrom"]),
            referenceTo=_one(graph, s, PROMO["referenceTo"]),
            permeable=(sorted(str(p) for p in
                              graph.objects(s, PROMO["permeable"]))
                       or None),
        ))

    # treeId <-> composite IRI both ways
    comp_by_iri: Dict[str, int] = {}
    for s in graph.subjects(RDF.type, PROMO["Composite"]):
        raw = _one(graph, s, PROMO["internalID"])
        if raw is not None:
            comp_by_iri[str(s)] = int(raw)

    for s in graph.subjects(RDF.type, PROMO["Composite"]):
        tree_id = comp_by_iri.get(str(s))
        if tree_id is None:
            continue
        parent_iri = _one(graph, s, PROMO["parent"])
        doc.composites.append(CompositeDoc(
            treeId=tree_id,
            label=_one(graph, s, RDFS.label) or "",
            parentTreeId=comp_by_iri.get(parent_iri) if parent_iri else None,
            children=[ChildDoc(**c) for c in
                      _json(graph, s, PROMO["children"], [])],
            layout=_json(graph, s, PROMO["layout"], {}),
            knots=_json(graph, s, PROMO["knots"], {}),
            openArcs=[OpenArcDoc(**o) for o in
                      _json(graph, s, PROMO["openArcs"], [])],
        ))

    model = _model_iri(graph)
    if (model, RDF.type, PROMO["Model"]) in graph:
        root = _one(graph, model, PROMO["rootComposite"])
        if root and root in comp_by_iri:
            doc.rootTreeId = comp_by_iri[root]
        for field, pred in (("nextTreeId", "nextTreeId"),
                            ("arcCounter", "arcCounter")):
            raw = _one(graph, model, PROMO[pred])
            if raw is not None:
                setattr(doc, field, int(raw))

    for comp, alias in graph.subject_objects(PROMO["speciesAlias"]):
        doc.speciesAliases[str(comp)] = str(alias)

    return doc


@router.put("/model", response_model=ModelDocument)
def put_model(
    doc: ModelDocument,
    graph_iri: Optional[str] = Depends(editable_param),
) -> ModelDocument:
    """Replace the artefact graph's model content with ``doc``."""
    store = get_store()
    graph = resolve_graph(store, graph_iri)

    # wipe existing model triples
    for t in _MODEL_TYPES:
        for s in list(graph.subjects(RDF.type, PROMO[t])):
            graph.remove((s, None, None))
    # speciesAlias subjects are external Component IRIs — not caught by
    # the typed-subject wipe above; clear them explicitly.
    graph.remove((None, PROMO["speciesAlias"], None))

    for n in doc.nodes:
        s = URIRef(n.iri)
        graph.add((s, RDF.type, PROMO["ModelNode"]))
        if n.entityType:
            graph.set((s, PROMO["entityType"], URIRef(n.entityType)))
        if n.label:
            graph.set((s, RDFS.label, Literal(n.label)))
        if n.speciesAllocation:
            graph.set((s, PROMO["speciesAllocation"],
                       URIRef(n.speciesAllocation)))
        for r in n.reactions:
            graph.add((s, PROMO["hostsReaction"], URIRef(r)))
        graph.set((s, PROMO["internalID"],
                   Literal(n.iri.rsplit("/", 1)[-1])))

    for a in doc.arcs:
        s = URIRef(a.iri)
        graph.add((s, RDF.type, PROMO["ModelArc"]))
        if a.sourceIri:
            graph.set((s, PROMO["source"], URIRef(a.sourceIri)))
        if a.targetIri:
            graph.set((s, PROMO["target"], URIRef(a.targetIri)))
        if a.arcType:
            graph.set((s, PROMO["arcType"], URIRef(a.arcType)))
        if a.referenceFrom:
            graph.set((s, PROMO["referenceFrom"], URIRef(a.referenceFrom)))
        if a.referenceTo:
            graph.set((s, PROMO["referenceTo"], URIRef(a.referenceTo)))
        for p in a.permeable or []:
            graph.add((s, PROMO["permeable"], URIRef(p)))
        graph.set((s, PROMO["internalID"],
                   Literal(a.iri.rsplit("/", 1)[-1])))

    for c in doc.composites:
        s = _composite_iri(graph, c.treeId)
        graph.add((s, RDF.type, PROMO["Composite"]))
        graph.set((s, PROMO["internalID"], Literal(c.treeId)))
        if c.label:
            graph.set((s, RDFS.label, Literal(c.label)))
        if c.parentTreeId is not None:
            graph.set((s, PROMO["parent"],
                       _composite_iri(graph, c.parentTreeId)))
        if c.children:
            graph.set((s, PROMO["children"],
                       Literal(json.dumps(
                           [ch.model_dump() for ch in c.children]))))
        if c.layout:
            graph.set((s, PROMO["layout"], Literal(json.dumps(c.layout))))
        if c.knots:
            graph.set((s, PROMO["knots"], Literal(json.dumps(c.knots))))
        if c.openArcs:
            graph.set((s, PROMO["openArcs"],
                       Literal(json.dumps(
                           [o.model_dump() for o in c.openArcs]))))

    model = _model_iri(graph)
    graph.add((model, RDF.type, PROMO["Model"]))
    graph.set((model, PROMO["rootComposite"],
               _composite_iri(graph, doc.rootTreeId)))
    graph.set((model, PROMO["nextTreeId"], Literal(doc.nextTreeId)))
    graph.set((model, PROMO["arcCounter"], Literal(doc.arcCounter)))

    for comp, alias in doc.speciesAliases.items():
        if alias:
            graph.set((URIRef(comp), PROMO["speciesAlias"],
                       Literal(alias)))

    return doc
