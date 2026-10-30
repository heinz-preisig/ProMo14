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
- ``promo:usesSpecies`` — pin on the graph IRI naming the species
  artefact (§20).  Artefact-level metadata, not model content: the
  wipe below skips the graph IRI so type marker, label and pins
  survive a document save.
- ``promo:refersTo`` — on a Composite: the referenced model artefact
  IRI (§22 referenced composite; children stay empty).  ``promo:
  overrides`` — JSON literal override map (pin kind → artefact IRI).
- ``promo:usesModel`` — derived pin set on the graph IRI listing all
  referenced model artefacts; rewritten from ``refersTo`` on each save
  so referrer queries stay cheap.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from rdflib import RDF, RDFS, Literal, URIRef

from backend.behaviour.service import _read_assignment
from backend.core.gestures import violations as gesture_violations
from backend.core.graph_store import PROMO, get_store
from backend.core.deps import editable_param, graph_param, resolve_graph
from backend.instantiate.satisfy import port_satisfaction
from backend.instantiate.service import (
    _assignments_collect,
    _model_dependencies,
    _token_taxonomy,
    _vars_collect,
)
from backend.ontology.service import resolve_connection

from . import router
from .references import reference_cycles, reference_dag

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
    # ADR-008 layer 2: promo:fix marks — variable IRIs bound to values
    # at this node occurrence.
    fixes: List[str] = Field(default_factory=list)


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
    # §22: the external node's entity type — the terminal's declared
    # interface for host-side resolve-connection adjudication.
    externalEntityType: Optional[str] = None


class CompositeDoc(BaseModel):
    treeId: int
    label: str = ""
    parentTreeId: Optional[int] = None
    children: List[ChildDoc] = Field(default_factory=list)
    layout: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    knots: Dict[str, List[Dict[str, float]]] = Field(default_factory=dict)
    openArcs: List[OpenArcDoc] = Field(default_factory=list)
    # §22 referenced composite: artefact IRI this occurrence points at
    # (children stay empty) + per-occurrence override map (pin kind →
    # artefact IRI, e.g. {"species": ..., "values": ...}).
    refersTo: Optional[str] = None
    overrides: Dict[str, str] = Field(default_factory=dict)
    # §22 dissolve provenance: artefact IRI this composite was inlined
    # from (one-way — the link is severed).
    dissolvedFrom: Optional[str] = None


class ModelDocument(BaseModel):
    nodes: List[ModelNodeDoc] = Field(default_factory=list)
    arcs: List[ModelArcDoc] = Field(default_factory=list)
    composites: List[CompositeDoc] = Field(default_factory=list)
    rootTreeId: int = 1
    nextTreeId: int = 1
    arcCounter: int = 1
    # §20 model-level species aliasing: Component IRI → local name.
    speciesAliases: Dict[str, str] = Field(default_factory=dict)
    # §20 species-artefact pin(s) on the graph IRI (artefact metadata).
    usesSpecies: List[str] = Field(default_factory=list)
    # §22 derived index: every model artefact referenced by a composite
    # in this document.  Ignored on PUT — recomputed from refersTo.
    usesModel: List[str] = Field(default_factory=list)


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


@router.get("/behaviour-entity-types", response_model=List[str])
def behaviour_entity_types(
    graph_iri: Optional[str] = Depends(graph_param),
) -> List[str]:
    store = get_store()
    model_iri = URIRef(graph_iri) if graph_iri else None
    model_graph = store.dataset.graph(model_iri) if model_iri else None
    entity_types = set()
    assignment_iris = (
        model_graph.objects(model_iri, PROMO["usesAssignment"])
        if model_graph is not None else []
    )
    for assignment_iri in assignment_iris:
        assignments = store.dataset.graph(assignment_iri)
        for resource in assignments.subjects(
            RDF.type, PROMO["BehaviourAssignment"]
        ):
            assignment = _read_assignment(assignments, resource)
            if assignment and assignment.closed and assignment.entity_type:
                entity_types.add(assignment.entity_type)
    return sorted(entity_types)


# ---------------------------------------------------------------------------
# §13/§14 Port satisfaction — connect-time adjudication
# ---------------------------------------------------------------------------


class PortDemandOut(BaseModel):
    var: str
    label: str = ""
    tokens: List[str] = Field(default_factory=list)
    #: satisfied|ambiguous|unbound|unlicensed|unreachable
    status: str
    candidates: List[str] = Field(default_factory=list)
    state_hidden: bool = False


class PortSideOut(BaseModel):
    entity_type: str
    has_assignment: bool = True
    ports: List[PortDemandOut] = Field(default_factory=list)
    unsatisfied: List[str] = Field(default_factory=list)


class PortSatisfactionOut(BaseModel):
    source: PortSideOut
    target: PortSideOut
    carrier: Optional[str] = None
    #: None = token licensing not applicable (domains unresolved)
    matched_tokens: Optional[List[str]] = None


def _etype_domain(store, model_graph, entity_type: str) -> Optional[str]:
    """The top-level domain IRI for an entity type's ``branch`` label —
    the IRI ``resolve-connection`` matches rules against."""
    et = URIRef(entity_type)
    branch: Optional[str] = None
    for giri in store.resolution_scope(model_graph.identifier):
        g = store.dataset.graph(giri)
        b = g.value(et, PROMO["branch"])
        if b is not None:
            branch = str(b)
            break
    if branch is None:
        return None
    for giri in store.resolution_scope(model_graph.identifier):
        g = store.dataset.graph(giri)
        for d in g.subjects(RDF.type, PROMO["Domain"]):
            if str(g.value(d, PROMO["branch"])) == branch:
                return str(d)
    return None


@router.get("/port-satisfaction", response_model=PortSatisfactionOut)
def port_satisfaction_endpoint(
    source: str,
    target: str,
    arc_type: Optional[str] = None,
    vars: Optional[str] = None,
    graph_iri: Optional[str] = Depends(graph_param),
) -> PortSatisfactionOut:
    """Adjudicate a proposed ``source``↔``target`` entity-type
    connection: which of each side's BL port demands an arc would feed
    (§13 connect-time check; advisory — never blocks the gesture).

    ``arc_type`` (an ``promo:ArcType/<carrier>`` IRI or a bare carrier
    fragment) narrows token licensing to that rule's carrier; absent,
    every rule licensed for the pair contributes.  Ports whose tokens
    no carried token can satisfy report ``unlicensed``; the remaining
    statuses mirror instantiation's ``bound|ambiguous|unbound``.
    """
    store = get_store()
    model_graph = resolve_graph(store, graph_iri)
    library, assignment_graph = _model_dependencies(model_graph, vars)
    variables, equations, _idx, var_labels, _c = _vars_collect(
        store, library)
    assignments = _assignments_collect(
        store, assignment_graph, var_labels)
    token_parents, _kinds = _token_taxonomy(store, model_graph)

    carrier = arc_type.rsplit("/", 1)[-1] if arc_type else None
    matched = None
    unidirectional = False
    src_dom = _etype_domain(store, model_graph, source)
    tgt_dom = _etype_domain(store, model_graph, target)
    if src_dom and tgt_dom:
        res = resolve_connection(
            src_dom, tgt_dom,
            graph_iri=str(model_graph.identifier))
        rules = res["rules"]
        if carrier:
            rules = [r for r in rules if r.get("carrier") == carrier]
        matched = {t for r in rules for t in r.get("matched_tokens", [])}
        # §14: a signal/reference arc is unidirectional — only the
        # target side's ports can be fed.  Applies when every
        # contributing rule is unidirectional (mixed sets keep the
        # bidirectional adjudication).
        unidirectional = bool(rules) and all(
            r.get("direction") == "unidirectional" for r in rules)

    src_side, tgt_side = port_satisfaction(
        source, target, assignments, variables, equations,
        token_parents, matched_tokens=matched,
        unidirectional=unidirectional)

    def _out(side) -> PortSideOut:
        return PortSideOut(
            entity_type=side.entity_type,
            has_assignment=side.has_assignment,
            ports=[PortDemandOut(**p.__dict__) for p in side.ports],
            unsatisfied=side.unsatisfied)

    return PortSatisfactionOut(
        source=_out(src_side), target=_out(tgt_side),
        carrier=carrier,
        matched_tokens=(sorted(matched) if matched is not None
                        else None))


@router.get("/references")
def get_references(
    graph_iri: Optional[str] = Depends(graph_param),
):
    """§22 reference DAG: ``usesModel`` pins reachable from the artefact,
    plus ``reference-cycle`` loops (transitive self-references)."""
    store = get_store()
    graph = resolve_graph(store, graph_iri)
    dag = reference_dag(store, str(graph.identifier))
    return {"dag": dag,
            "cycles": reference_cycles(dag, str(graph.identifier))}


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
            fixes=sorted(str(f) for f in
                         graph.objects(s, PROMO["fix"])),
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
            refersTo=_one(graph, s, PROMO["refersTo"]),
            overrides=_json(graph, s, PROMO["overrides"], {}),
            dissolvedFrom=_one(graph, s, PROMO["dissolvedFrom"]),
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

    doc.usesSpecies = sorted(
        str(o) for o in graph.objects(graph.identifier,
                                      PROMO["usesSpecies"]))
    doc.usesModel = sorted(
        str(o) for o in graph.objects(graph.identifier,
                                      PROMO["usesModel"]))

    return doc


@router.put("/model", response_model=ModelDocument)
def put_model(
    doc: ModelDocument,
    graph_iri: Optional[str] = Depends(editable_param),
) -> ModelDocument:
    """Replace the artefact graph's model content with ``doc``."""
    store = get_store()
    graph = resolve_graph(store, graph_iri)

    # §20 gesture admissibility (ontology capability gates): a rejected
    # document leaves the graph untouched — validate before the wipe.
    problems = gesture_violations(
        store, graph.identifier,
        nodes=[(n.iri, n.entityType or None, n.speciesAllocation,
                list(n.reactions)) for n in doc.nodes],
        arcs=[(a.iri, a.sourceIri or None, a.targetIri or None,
               a.permeable) for a in doc.arcs])
    if problems:
        raise HTTPException(status_code=422,
                            detail="inadmissible species gestures: "
                                   + "; ".join(problems))

    # wipe existing model triples — but never the graph IRI itself:
    # it is typed promo:Model by create_artefact_graph and carries the
    # artefact's self-description (type marker, label, pins).
    for t in _MODEL_TYPES:
        for s in list(graph.subjects(RDF.type, PROMO[t])):
            if s == graph.identifier:
                continue
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
        for f in n.fixes:
            graph.add((s, PROMO["fix"], URIRef(f)))
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
        if c.refersTo:
            graph.set((s, PROMO["refersTo"], URIRef(c.refersTo)))
        if c.overrides:
            graph.set((s, PROMO["overrides"],
                       Literal(json.dumps(c.overrides))))
        if c.dissolvedFrom:
            graph.set((s, PROMO["dissolvedFrom"],
                       URIRef(c.dissolvedFrom)))

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

    # §20 species pin — replace the artefact's usesSpecies set with the
    # document's (whole-document semantics).
    graph.remove((graph.identifier, PROMO["usesSpecies"], None))
    for pin in doc.usesSpecies:
        graph.add((graph.identifier, PROMO["usesSpecies"], URIRef(pin)))

    # §22 derived usesModel index — recomputed from refersTo, never
    # trusted from the document.
    graph.remove((graph.identifier, PROMO["usesModel"], None))
    for ref in sorted({c.refersTo for c in doc.composites if c.refersTo}):
        graph.add((graph.identifier, PROMO["usesModel"], URIRef(ref)))
    doc.usesModel = sorted(
        str(o) for o in graph.objects(graph.identifier,
                                      PROMO["usesModel"]))

    return doc


# ---------------------------------------------------------------------------
# §22 Extract to submodel — move a subtree into a new model artefact
# ---------------------------------------------------------------------------


class ExtractSubmodelRequest(BaseModel):
    """Move ``treeNodeIds`` (subtree roots) out of the host document
    into a new model artefact; the host gets a referenced composite
    (``refersTo``) in their place and boundary arcs become open arcs
    on both sides (§22, move semantics — copy rejected)."""
    iri: str                      # new artefact IRI
    treeNodeIds: List[int]        # subtree roots to move
    label: Optional[str] = None   # label for artefact + host composite


def _subtree_ids(doc: ModelDocument, roots: List[int]) -> set:
    """All tree ids in the selected subtrees (composites + leaf ids)."""
    by_id = {c.treeId: c for c in doc.composites}
    ids: set = set()
    stack = list(roots)
    while stack:
        tid = stack.pop()
        if tid in ids:
            continue
        ids.add(tid)
        comp = by_id.get(tid)
        if comp is None:
            continue
        # nested composites are found via parentTreeId, leaves via
        # children entries
        stack.extend(ch.id for ch in comp.children)
        stack.extend(c.treeId for c in doc.composites
                     if c.parentTreeId == tid)
    return ids


@router.post("/extract-submodel")
def extract_submodel(
    req: ExtractSubmodelRequest,
    graph_iri: Optional[str] = Depends(editable_param),
):
    store = get_store()
    graph = resolve_graph(store, graph_iri)
    host = get_model(graph_iri=str(graph.identifier))

    by_id = {c.treeId: c for c in host.composites}
    roots = [t for t in req.treeNodeIds if t != host.rootTreeId]
    if not roots:
        raise HTTPException(422, "selection must exclude the root composite")
    if any(t not in by_id for t in roots):
        raise HTTPException(422, "selection must be composite tree nodes")
    moved = _subtree_ids(host, roots)
    if host.rootTreeId in moved:
        raise HTTPException(422, "selection must exclude the root composite")

    # -- partition the document -------------------------------------------
    moved_comps = [c for c in host.composites if c.treeId in moved]
    moved_node_iris = {
        ch.iri for c in moved_comps for ch in c.children if ch.iri}
    kept_comps = [c for c in host.composites if c.treeId not in moved]

    def _is_boundary(a: ModelArcDoc) -> bool:
        return ((a.sourceIri in moved_node_iris)
                != (a.targetIri in moved_node_iris))

    boundary = [a for a in host.arcs if _is_boundary(a)]
    sub_arcs = [a for a in host.arcs
                if a.sourceIri in moved_node_iris
                and a.targetIri in moved_node_iris]
    host.arcs = [a for a in host.arcs
                 if a not in sub_arcs]  # boundary arcs stay in the host
    sub_nodes = [n for n in host.nodes if n.iri in moved_node_iris]
    host.nodes = [n for n in host.nodes if n.iri not in moved_node_iris]

    # -- new artefact: pins inherited from the host -----------------------
    gid = graph.identifier
    pins = {p: [str(o) for o in graph.objects(gid, PROMO[p])]
            for p in ("usesOntology", "usesLibrary", "usesAssignment",
                      "usesSpecies")}
    try:
        new_iri = store.create_artefact_graph(
            req.iri, "Model", label=req.label,
            uses=pins["usesOntology"],
            uses_library=pins["usesLibrary"],
            uses_assignment=pins["usesAssignment"],
            uses_species=pins["usesSpecies"])
    except ValueError as exc:
        raise HTTPException(409, str(exc))

    # -- renumber the moved subtree into a standalone document ------------
    # New root (treeId 0) parents the selection roots; all other tree ids
    # are renumbered sequentially, remapping children/parent/layout keys.
    ordered = [t for t in _subtree_ids(host, roots) if t in by_id]
    leaf_ids = sorted(i for i in moved if i not in by_id)
    remap: Dict[int, int] = {}
    next_id = 1
    for t in ordered:
        remap[t] = next_id
        next_id += 1
    for t in leaf_ids:
        remap[t] = next_id
        next_id += 1

    sub_composites = [CompositeDoc(
        treeId=0, label=req.label or "Root", parentTreeId=None,
        children=[ChildDoc(id=remap[t]) for t in roots],
        layout={}, knots={},
        openArcs=[_sub_open_arc(a, moved_node_iris, host.nodes)
                  for a in boundary],
    )]
    for c in moved_comps:
        sub_composites.append(CompositeDoc(
            treeId=remap[c.treeId], label=c.label,
            parentTreeId=(remap[c.parentTreeId]
                          if c.parentTreeId in moved else 0),
            children=[ChildDoc(id=remap[ch.id], iri=ch.iri)
                      for ch in c.children],
            layout={str(remap[int(k)]): v for k, v in c.layout.items()
                    if int(k) in remap},
            knots=c.knots, openArcs=c.openArcs,
            refersTo=c.refersTo, overrides=c.overrides))

    sub_doc = ModelDocument(
        nodes=sub_nodes, arcs=sub_arcs + boundary,
        composites=sub_composites,
        rootTreeId=0, nextTreeId=next_id, arcCounter=host.arcCounter,
        speciesAliases=host.speciesAliases, usesSpecies=host.usesSpecies)
    put_model(sub_doc, graph_iri=str(new_iri))

    # -- host: referenced composite in place of the selection -------------
    new_comp_id = host.nextTreeId
    # attach under the (shared) parent of the first selection root
    parents = {by_id[r].parentTreeId for r in roots}
    parent_id = parents.pop() if len(parents) == 1 else host.rootTreeId

    entity_of = {n.iri: n.entityType for n in host.nodes}
    host_open = [OpenArcDoc(
        iri=a.iri,
        externalIri=(a.sourceIri if a.targetIri in moved_node_iris
                     else a.targetIri),
        arcType=a.arcType,
        isSource=a.sourceIri in moved_node_iris,
        refToExternal=((a.referenceTo not in moved_node_iris)
                       if a.referenceTo else None),
        externalEntityType=entity_of.get(
            a.sourceIri if a.targetIri in moved_node_iris
            else a.targetIri),
    ) for a in boundary]

    for c in kept_comps:
        # centroid BEFORE filtering — it averages the removed children
        spot = _centroid(c, moved) if c.treeId == parent_id else None
        c.children = [ch for ch in c.children if ch.id not in moved]
        c.layout = {k: v for k, v in c.layout.items()
                    if int(k) not in moved}
        if spot is not None:
            c.children.append(ChildDoc(id=new_comp_id))
            c.layout[str(new_comp_id)] = spot

    kept_comps.append(CompositeDoc(
        treeId=new_comp_id,
        label=req.label or "Submodel",
        parentTreeId=parent_id,
        children=[], layout={}, knots={},
        openArcs=host_open,
        refersTo=req.iri))
    host.composites = kept_comps
    host.nextTreeId += 1

    put_model(host, graph_iri=str(graph.identifier))

    return {"iri": str(new_iri), "compositeTreeId": new_comp_id,
            "movedNodes": len(sub_nodes),
            "boundaryArcs": len(boundary)}


def _sub_open_arc(a: ModelArcDoc, inside: set,
                  node_docs: List["ModelNodeDoc"]) -> OpenArcDoc:
    """The submodel's view of a boundary arc: the surviving end is the
    *internal* node; the open (missing) end faces the host.  The
    declared interface also carries the internal node's entity type
    so a host-side connect gesture can run resolve-connection."""
    internal = a.sourceIri if a.sourceIri in inside else a.targetIri
    entity_of = {n.iri: n.entityType for n in node_docs}
    return OpenArcDoc(
        iri=a.iri, externalIri=internal, arcType=a.arcType,
        isSource=a.sourceIri not in inside,
        refToExternal=((a.referenceTo in inside)
                       if a.referenceTo else None),
        externalEntityType=entity_of.get(internal))


def _centroid(parent: CompositeDoc, moved: set) -> Dict[str, float]:
    """Position for the new referenced composite: mean of the removed
    children's layout positions, else a sensible default."""
    pts = [v for k, v in parent.layout.items() if int(k) in moved]
    if not pts:
        return {"x": 0.0, "y": 0.0}
    return {"x": sum(p["x"] for p in pts) / len(pts),
            "y": sum(p["y"] for p in pts) / len(pts)}


# ---------------------------------------------------------------------------
# §22 Dissolve — flatten a referenced composite to inline content
# ---------------------------------------------------------------------------


class DissolveRequest(BaseModel):
    """Replace the referenced composite ``treeNodeId`` with an inline
    composite containing a copy of the referenced artefact's content.
    Boundary arcs remap onto the copied terminals; the link is severed
    (``dissolvedFrom`` keeps provenance).  One-way — §22."""
    treeNodeId: int


@router.post("/dissolve")
def dissolve(
    req: DissolveRequest,
    graph_iri: Optional[str] = Depends(editable_param),
):
    store = get_store()
    graph = resolve_graph(store, graph_iri)
    host = get_model(graph_iri=str(graph.identifier))

    comp = next((c for c in host.composites
                 if c.treeId == req.treeNodeId), None)
    if comp is None or not comp.refersTo:
        raise HTTPException(422,
                            "composite is not a referenced composite")
    sub = get_model(graph_iri=comp.refersTo)
    if not sub.composites:
        raise HTTPException(422,
                            f"referenced artefact has no content: "
                            f"{comp.refersTo}")

    # -- tree id remap: the referenced root IS this composite --------------
    sub_by_id = {c.treeId: c for c in sub.composites}
    sub_root = sub_by_id.get(sub.rootTreeId)
    if sub_root is None:
        raise HTTPException(422, "referenced artefact has no root")
    all_ids = _subtree_ids(sub, [sub.rootTreeId])
    remap: Dict[int, int] = {sub.rootTreeId: comp.treeId}
    next_id = host.nextTreeId
    for t in sorted(all_ids - {sub.rootTreeId}):
        remap[t] = next_id
        next_id += 1

    # -- merge content -----------------------------------------------------
    have_nodes = {n.iri for n in host.nodes}
    host.nodes.extend(n for n in sub.nodes if n.iri not in have_nodes)
    have_arcs = {a.iri for a in host.arcs}
    host.arcs.extend(a for a in sub.arcs if a.iri not in have_arcs)

    # composite takes over the referenced root's view
    boundary_iris = {o.iri for o in comp.openArcs}
    comp.children = [ChildDoc(id=remap[ch.id], iri=ch.iri)
                     for ch in sub_root.children]
    comp.layout = {str(remap[int(k)]): v
                   for k, v in sub_root.layout.items()
                   if int(k) in remap}
    comp.knots = sub_root.knots
    comp.openArcs = []
    source = comp.refersTo
    comp.refersTo = None
    comp.overrides = {}
    comp.dissolvedFrom = source

    for c in sub.composites:
        if c.treeId == sub.rootTreeId:
            continue
        host.composites.append(CompositeDoc(
            treeId=remap[c.treeId], label=c.label,
            parentTreeId=remap.get(c.parentTreeId, comp.treeId),
            children=[ChildDoc(id=remap[ch.id], iri=ch.iri)
                      for ch in c.children],
            layout={str(remap[int(k)]): v
                    for k, v in c.layout.items() if int(k) in remap},
            knots=c.knots,
            openArcs=[o for o in c.openArcs
                      if o.iri not in boundary_iris],
            refersTo=c.refersTo, overrides=c.overrides,
            dissolvedFrom=c.dissolvedFrom))

    # parent views: boundary arcs are no longer open — drop their knots
    # and any openArc entries elsewhere in the host
    for c in host.composites:
        c.knots = {k: v for k, v in c.knots.items()
                   if k not in boundary_iris}
        if c.treeId != comp.treeId:
            c.openArcs = [o for o in c.openArcs
                          if o.iri not in boundary_iris]

    host.nextTreeId = next_id
    # override folding: the inlined content's species vocabulary joins
    # the host's pin set (artefact pins can't live on a composite)
    host.usesSpecies = sorted(set(host.usesSpecies) | set(sub.usesSpecies))

    put_model(host, graph_iri=str(graph.identifier))
    return {"dissolved": source, "compositeTreeId": comp.treeId,
            "addedNodes": len(sub.nodes),
            "remappedArcs": len(boundary_iris)}
