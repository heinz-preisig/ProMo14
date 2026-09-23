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

``GET /model?graph=&vars=`` assembles the §19 instantiation report:
per entity type, the behaviour assignment's equation sequence with
every variable bound — local (index structures → model element sets),
parameter, constant, port (resolved per contact across arcs), or
incidence (``[N,A]``-indexed vars → the numeric ``F`` matrices).
``vars`` selects the var/expr artefact (default: dataset-wide scope
and the default assignment graph).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from rdflib import RDF, RDFS, URIRef

from backend.behaviour.service import (
    _assignment_graph_iri,
    _read_assignment,
)
from backend.core.graph_store import PROMO, get_store
from backend.ontology.service import (
    graph_param,
    resolve_graph,
    scoped_context,
)

from backend.equation.compile_space import CompileSpace
from backend.equation.errors import VarError
from backend.equation.parser import ParseError

from . import router
from .builder import (
    AssignmentInfo,
    EqInfo,
    IndexInfo,
    Problem,
    VarInfo,
    _frag,
)
from .builder import build as build_model
from .emit_julia import emit_julia
from .emit_matlab import emit_matlab
from .emit_python import emit_python
from .fbuilder import build
from .distribute import (
    Reaction,
    SpeciesArc,
    SpeciesArtefact,
    SpeciesDistribution,
    SpeciesNode,
    distribute,
)
from .plan import plan
from .scheduler import schedule
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


class VarBindingOut(BaseModel):
    """One variable's binding within an entity-type instantiation."""

    var: str
    role: str                            # state|defined|port|parameter|input
    binding: str                         # local|port|parameter|constant|incidence
    instance: str
    indices: Dict[str, Optional[List[str]]] = Field(default_factory=dict)
    matrix: Optional[str] = None         # incidence: arc index IRI
    value: Optional[str] = None          # constant: pre-bound value


class EqBindingOut(BaseModel):
    equation: str
    lhs: str
    inputs: List[str] = Field(default_factory=list)


class EntityInstantiationOut(BaseModel):
    entity_type: str
    nodes: List[str] = Field(default_factory=list)
    has_assignment: bool = False
    closed: bool = False
    state_variable: Optional[str] = None
    variables: List[VarBindingOut] = Field(default_factory=list)
    equations: List[EqBindingOut] = Field(default_factory=list)


class PortBindingOut(BaseModel):
    node: str
    var: str
    status: str                          # bound|unbound|ambiguous
    arc: Optional[str] = None
    peer_node: Optional[str] = None
    peer_var: Optional[str] = None
    element: Optional[str] = None
    candidates: List[List[str]] = Field(default_factory=list)


class ProblemOut(BaseModel):
    kind: str
    message: str
    node: Optional[str] = None
    entity_type: Optional[str] = None


class SchedBlockOut(BaseModel):
    """One equation block in the evaluation plan."""

    entity_type: str
    equation: str
    lhs: str
    loop: int = -1                       # algebraic-loop id, or -1


class ScheduleOut(BaseModel):
    """Evaluation order: levels of independent blocks + SCC loops."""

    levels: List[List[SchedBlockOut]] = Field(default_factory=list)
    loops: List[List[List[str]]] = Field(default_factory=list)


class CodeOut(BaseModel):
    """Generated source for one target."""

    ok: bool
    target: str
    source: str = ""
    error: Optional[str] = None
    problems: List[str] = Field(default_factory=list)


class InstantiationReportOut(BaseModel):
    """The assembled model equation-set report (§19)."""

    model: str
    vars_graph: Optional[str] = None
    indices: Dict[str, List[str]] = Field(default_factory=dict)
    entity_types: List[EntityInstantiationOut] = Field(default_factory=list)
    ports: List[PortBindingOut] = Field(default_factory=list)
    incidence: IncidenceReportOut
    schedule: ScheduleOut = Field(default_factory=ScheduleOut)
    problems: List[ProblemOut] = Field(default_factory=list)
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


def _entity_capabilities(store, model_graph) -> Dict[str, Set[str]]:
    """entity-type IRI → capability fragments, resolved through
    ``promo:parent`` ancestry (a subtype grants what its parents do)."""
    direct: Dict[str, Set[str]] = {}
    parents: Dict[str, str] = {}
    for gi in store.resolution_scope(model_graph.identifier):
        g = store.dataset.graph(gi)
        for et in g.subjects(RDF.type, PROMO["EntityType"]):
            acc = direct.setdefault(str(et), set())
            for c in g.objects(et, PROMO["capability"]):
                frag = str(c).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
                acc.add(frag[4:] if frag.startswith("cap_") else frag)
            p = g.value(et, PROMO["parent"])
            if p is not None:
                parents[str(et)] = str(p)
    out: Dict[str, Set[str]] = {}
    for et in direct:
        acc, cur, seen = set(), et, set()
        while cur and cur not in seen:
            seen.add(cur)
            acc |= direct.get(cur, set())
            cur = parents.get(cur)
        out[et] = acc
    return out


def _species_index_iri(store, model_graph) -> Optional[str]:
    """The index carrying the ``promo:species`` token."""
    for gi in store.resolution_scope(model_graph.identifier):
        g = store.dataset.graph(gi)
        for idx in g.subjects(RDF.type, PROMO["Index"]):
            if str(g.value(idx, PROMO["token"]) or "") == str(
                    PROMO["species"]):
                return str(idx)
    return None


def _species_pin(model_graph) -> Optional[str]:
    """The model artefact's ``promo:usesSpecies`` pin (first), if any —
    the persistent form of the ``?species=`` param (§20)."""
    pin = model_graph.value(model_graph.identifier, PROMO["usesSpecies"])
    return str(pin) if pin is not None else None


def _species_distribution(store, model_graph, species_graph_iri
                          ) -> Optional[SpeciesDistribution]:
    """Run the §20 distribution for a model against a species artefact.

    Reads the species placements off the model graph (reservoir
    ``speciesAllocation``, ``hostsReaction``, arc ``permeable``) and the
    vocabulary off the species artefact (components, allocations,
    reactions).  ``carries_species`` is set on arcs touching a
    species-transport-capable node (mass/species transport).
    """
    if not species_graph_iri:
        return None
    caps = _entity_capabilities(store, model_graph)
    sp_transport = {et for et, c in caps.items()
                    if "species_transport" in c}

    snodes: List[SpeciesNode] = []
    node_is_transport: Dict[str, bool] = {}
    for s in model_graph.subjects(RDF.type, PROMO["ModelNode"]):
        et = model_graph.value(s, PROMO["entityType"])
        alloc = model_graph.value(s, PROMO["speciesAllocation"])
        rxns = [str(r) for r in
                model_graph.objects(s, PROMO["hostsReaction"])]
        snodes.append(SpeciesNode(
            iri=str(s),
            allocation=str(alloc) if alloc else None,
            reactions=rxns))
        node_is_transport[str(s)] = (
            str(et) in sp_transport if et else False)

    sarcs: List[SpeciesArc] = []
    for s in model_graph.subjects(RDF.type, PROMO["ModelArc"]):
        src = model_graph.value(s, PROMO["source"])
        tgt = model_graph.value(s, PROMO["target"])
        perm = sorted(str(p) for p in
                      model_graph.objects(s, PROMO["permeable"]))
        carries = bool(node_is_transport.get(str(src))
                       or node_is_transport.get(str(tgt)))
        sarcs.append(SpeciesArc(
            iri=str(s),
            source=str(src) if src else None,
            target=str(tgt) if tgt else None,
            carries_species=carries,
            permeable=set(perm) if perm else None))

    sg = resolve_graph(store, species_graph_iri)
    artefact = SpeciesArtefact(
        species=[str(c) for c in sg.subjects(RDF.type, PROMO["Component"])],
        allocations={
            str(a): [str(m) for m in sg.objects(a, PROMO["member"])]
            for a in sg.subjects(RDF.type, PROMO["Allocation"])},
        reactions={
            str(r): Reaction(
                str(r),
                {str(x) for x in sg.objects(r, PROMO["reactant"])},
                {str(x) for x in sg.objects(r, PROMO["product"])})
            for r in sg.subjects(RDF.type, PROMO["Reaction"])})
    return distribute(snodes, sarcs, artefact)


class SpeciesDistributionOut(BaseModel):
    """§20 readout: species present per node / carried per arc, and
    the active reaction set per node (the ``Q`` index's elements)."""
    species: Optional[str] = None   # resolved species artefact IRI
    nodes: Dict[str, List[str]] = {}
    arcs: Dict[str, List[str]] = {}
    reactions: Dict[str, List[str]] = {}


@router.get("/species-distribution", response_model=SpeciesDistributionOut)
def species_distribution(
    graph_iri: Optional[str] = Depends(graph_param),
    species: Optional[str] = None,
) -> SpeciesDistributionOut:
    """Which species occupy each node and arc (§20).

    ``?species=`` overrides the model artefact's ``usesSpecies`` pin;
    with neither, the maps come back empty.  This is the live readout
    the modeller shows while placements are edited — the same engine
    that binds ``S`` at instantiation.
    """
    if not graph_iri:
        raise HTTPException(
            status_code=400,
            detail="graph= (model artefact IRI) is required")
    store = get_store()
    model_graph = resolve_graph(store, graph_iri)
    sg_iri = species or _species_pin(model_graph)
    dist = _species_distribution(store, model_graph, sg_iri)
    if dist is None:
        return SpeciesDistributionOut(species=sg_iri)
    return SpeciesDistributionOut(
        species=sg_iri,
        nodes={k: sorted(v) for k, v in dist.nodes.items()},
        arcs={k: sorted(v) for k, v in dist.arcs.items()},
        reactions={k: sorted(v) for k, v in dist.reactions.items()})


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


# ---------------------------------------------------------------------------
# §19 model instantiation
# ---------------------------------------------------------------------------


def _incidence_out(report, labels) -> IncidenceReportOut:
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


def _token_taxonomy(store, model_graph):
    """Token parent chain + kinds, read across the model's scope."""
    parents: Dict[str, str] = {}
    kinds: Dict[str, str] = {}
    for graph_iri in store.resolution_scope(model_graph.identifier):
        g = store.dataset.graph(graph_iri)
        for t in g.subjects(RDF.type, PROMO["Token"]):
            p = g.value(t, PROMO["parent"])
            if p is not None:
                parents.setdefault(str(t), str(p))
            k = g.value(t, PROMO["tokenKind"])
            if k is not None:
                kinds.setdefault(str(t), str(k))
    return parents, kinds


def _vars_collect(store, vars_graph: Optional[str]):
    """Variables, equations and indices from the var/expr scope."""
    ctx = scoped_context(store, vars_graph)
    variables: Dict[str, VarInfo] = {}
    equations: Dict[str, EqInfo] = {}
    labels: Dict[str, str] = {}
    for iri, v in ctx.variables().items():
        variables[iri] = VarInfo(
            iri=iri,
            label=v.label,
            internal_id=v.internal_id,
            index_structures=list(v.index_structures),
            tokens=list(v.tokens),
            value=v.value,
            var_class=v.type,
            port_variable=v.port_variable,
        )
        labels[iri] = v.label
        for eq in getattr(v, "equations", {}).values():
            equations[eq["iri"]] = EqInfo(
                iri=eq["iri"],
                lhs=eq["lhs"],
                inputs=list(eq.get("incidence_list") or []),
                internal_id=eq.get("internal_id"),
                rhs=eq.get("rhs") or "",
            )
    indices: Dict[str, IndexInfo] = {}
    for iri, idx in ctx.indices().items():
        indices[iri] = IndexInfo(
            iri=iri,
            source=idx.aliases.get("index_source", ""),
            sub_index_of=idx.sub_index_of,
            short_name=idx.aliases.get("internal_code", ""),
        )
        labels[iri] = idx.aliases.get("internal_code", idx.label)
    return variables, equations, indices, labels


def _assignments_collect(store, vars_graph: Optional[str],
                         labels: Dict[str, str]) -> Dict[str, AssignmentInfo]:
    """All §13 behaviour assignments in the artefact's assignment graph."""
    out: Dict[str, AssignmentInfo] = {}
    ag = store.dataset.graph(URIRef(_assignment_graph_iri(vars_graph)))
    for res in ag.subjects(RDF.type, PROMO["BehaviourAssignment"]):
        a = _read_assignment(ag, res)
        if a is None or not a.entity_type:
            continue
        out[a.entity_type] = AssignmentInfo(
            entity_type=a.entity_type,
            sequence=list(a.sequence),
            base_equation=a.base_equation,
            state_variable=a.state_variable,
            instantiated=list(a.instantiated),
            ports=list(a.ports),
            closed=a.closed,
        )
    return out


@router.get("/model", response_model=InstantiationReportOut)
def model_instantiation(
    graph_iri: Optional[str] = Depends(graph_param),
    vars: Optional[str] = None,
    species: Optional[str] = None,
) -> InstantiationReportOut:
    """§19 instantiation report for a model artefact.

    ``graph`` is the model artefact (required); ``vars`` the var/expr
    artefact supplying variables, equations and the assignment graph
    (default: dataset-wide scope + the default assignment graph);
    ``species`` the species artefact supplying the §20 distribution
    vocabulary (optional — without it species indices stay symbolic).
    """
    if not graph_iri:
        raise HTTPException(
            status_code=400,
            detail="graph= (model artefact IRI) is required")
    store = get_store()
    model_graph = resolve_graph(store, graph_iri)
    nodes, arcs, sub_indices, parents, labels = _collect(
        store, model_graph)
    memberships = resolve(nodes, arcs, sub_indices, parents)
    inc = build(nodes, arcs, memberships, sub_indices)

    variables, equations, indices, var_labels = _vars_collect(store, vars)
    labels.update(var_labels)
    token_parents, token_kinds = _token_taxonomy(store, model_graph)
    assignments = _assignments_collect(store, vars, labels)

    # §20 species distribution → bind the species index.  The
    # ?species= param overrides the artefact's usesSpecies pin.
    dist = _species_distribution(
        store, model_graph, species or _species_pin(model_graph))
    species_index = _species_index_iri(store, model_graph) \
        if dist is not None else None

    # Entity-type labels for display.
    for graph in store.resolution_scope(model_graph.identifier):
        g = store.dataset.graph(graph)
        for et in g.subjects(RDF.type, PROMO["EntityType"]):
            lbl = g.value(et, RDFS.label)
            if lbl is not None:
                labels.setdefault(str(et), str(lbl))

    report = build_model(
        nodes, arcs, memberships, sub_indices, indices,
        assignments, variables, equations,
        token_parents, token_kinds,
        species=dist, species_index=species_index)
    sched = schedule(report)
    for i, scc in enumerate(sched.loops):
        report.problems.append(Problem(
            kind="algebraic-loop",
            message=(f"algebraic loop {i}: "
                     + ", ".join(_frag(q) for _t, q in scc))))

    return InstantiationReportOut(
        model=str(model_graph.identifier),
        vars_graph=vars,
        indices=report.indices,
        entity_types=[EntityInstantiationOut(
            entity_type=e.entity_type,
            nodes=e.nodes,
            has_assignment=e.has_assignment,
            closed=e.closed,
            state_variable=e.state_variable,
            variables=[VarBindingOut(
                var=v.var, role=v.role, binding=v.binding,
                instance=v.instance, indices=v.indices,
                matrix=v.matrix, value=v.value)
                for v in e.variables],
            equations=[EqBindingOut(
                equation=q.equation, lhs=q.lhs, inputs=q.inputs)
                for q in e.equations])
            for e in report.entity_types],
        ports=[PortBindingOut(
            node=p.node, var=p.var, status=p.status,
            arc=p.arc, peer_node=p.peer_node, peer_var=p.peer_var,
            element=p.element,
            candidates=[list(c) for c in p.candidates])
            for p in report.ports],
        incidence=_incidence_out(inc, labels),
        schedule=ScheduleOut(
            levels=[[SchedBlockOut(
                entity_type=b.entity_type, equation=b.equation,
                lhs=b.lhs, loop=b.loop) for b in lvl]
                for lvl in sched.levels],
            loops=[[[t, q] for t, q in scc] for scc in sched.loops]),
        problems=[ProblemOut(
            kind=p.kind, message=p.message,
            node=p.node, entity_type=p.entity_type)
            for p in report.problems],
        labels=labels,
    )


def _code_space(store, vars_graph: Optional[str]) -> CompileSpace:
    """A CompileSpace over the var/expr scope for RHS rendering —
    every variable's network is accessible so unqualified labels
    resolve."""
    ctx = scoped_context(store, vars_graph)
    variables = ctx.variables()
    return CompileSpace(
        variables, ctx.indices(),
        variable_definition_network="",
        expression_definition_network="",
        accessible_networks={v.network for v in variables.values()})


_EMITTERS = {"python": emit_python, "julia": emit_julia,
             "matlab": emit_matlab}


@router.get("/code", response_model=CodeOut)
def model_code(
    graph_iri: Optional[str] = Depends(graph_param),
    vars: Optional[str] = None,
    target: str = "python",
    species: Optional[str] = None,
) -> CodeOut:
    """§19 codegen: emit the model's derivative function.

    Same assembly as ``/model`` (report + schedule + incidence),
    then ``plan()`` lowers it to a ``CodePlan`` and the target
    emitter renders the source.  ``target`` is ``python`` or
    ``julia`` (matlab pending)."""
    if not graph_iri:
        raise HTTPException(
            status_code=400,
            detail="graph= (model artefact IRI) is required")
    if target not in _EMITTERS:
        raise HTTPException(
            status_code=400,
            detail="target must be one of %s" % sorted(_EMITTERS))
    store = get_store()
    model_graph = resolve_graph(store, graph_iri)
    nodes, arcs, sub_indices, parents, labels = _collect(
        store, model_graph)
    memberships = resolve(nodes, arcs, sub_indices, parents)
    inc = build(nodes, arcs, memberships, sub_indices)

    variables, equations, indices, var_labels = _vars_collect(
        store, vars)
    labels.update(var_labels)
    token_parents, token_kinds = _token_taxonomy(store, model_graph)
    assignments = _assignments_collect(store, vars, labels)

    # §20 species distribution → bind the species index.  The
    # ?species= param overrides the artefact's usesSpecies pin.
    dist = _species_distribution(
        store, model_graph, species or _species_pin(model_graph))
    species_index = _species_index_iri(store, model_graph) \
        if dist is not None else None

    report = build_model(
        nodes, arcs, memberships, sub_indices, indices,
        assignments, variables, equations,
        token_parents, token_kinds,
        species=dist, species_index=species_index)
    sched = schedule(report)
    cp = plan(report, sched, inc, equations, indices)
    try:
        source = _EMITTERS[target](cp, _code_space(store, vars))
    except (ParseError, VarError) as e:
        return CodeOut(ok=False, target=target, error=str(e),
                       problems=[p.kind for p in report.problems])
    return CodeOut(ok=True, target=target, source=source,
                   problems=[p.kind for p in report.problems])
