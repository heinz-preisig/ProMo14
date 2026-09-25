"""Behaviour linker service — entity behaviour assignments.

Endpoints backing the behaviour linker
(``docs/behaviour-linker-design-discussion.md`` §8/§13):

- ``GET  /context``     — entity types, equations and variables of the
                          scoped var/expr graph, for the picker UI.
- ``POST /evaluate``    — run the closure engine on a selection and
                          return the full status report (drives the
                          UI's pick-by-pick feedback loop).
- ``GET  /assignment``  — read the stored assignment for an entity type.
- ``PUT  /assignment``  — persist a selection as the entity type's
                          assignment artefact (§13): an ``rdf:List``
                          equation sequence plus state/port/instantiated
                          role predicates in an ``Assignment`` graph.
- ``DELETE /assignment``— drop an entity type's assignment.

The assignment artefact lives in a derived named graph
``{var/expr graph}/assignments`` (``promo:Assignment`` type), created
lazily on first write and pinned to the graph's resolution scope.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from rdflib import BNode, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF, RDFS, XSD

from backend.core.graph_store import PROMO, get_store
from backend.equation.checker import INSTANTIATE_CLASSES
from backend.equation.compile_space import CompileSpace
from backend.equation.document import _rhs_latex, _var_symbol
from backend.core.deps import editable_param, graph_param
from backend.ontology.rdf_context import scoped_context

from .closure import EquationInfo, Selection, evaluate

router = APIRouter()

# Default home for assignments when no var/expr graph is scoped
# (legacy single-graph mode, where variables live in the ontology).
DEFAULT_ASSIGNMENT_GRAPH = "https://w3id.org/promo/assignments"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class EntityTypeOut(BaseModel):
    iri: str
    label: str
    branch: str = ""
    scale_values: List[str] = Field(default_factory=list)


class EquationOut(BaseModel):
    iri: str
    internal_id: Optional[str] = None
    lhs: str
    lhs_latex: Optional[str] = None
    rhs: str = ""
    rhs_latex: Optional[str] = None
    equation_class: Optional[str] = None
    network: Optional[str] = None
    incidence: List[str] = Field(default_factory=list)


class VariableOut(BaseModel):
    iri: str
    label: str
    network: str = "root"
    variable_class: str = "state"
    port_variable: bool = False
    tokens: List[str] = Field(default_factory=list)


class BehaviourContextResponse(BaseModel):
    entity_types: List[EntityTypeOut] = Field(default_factory=list)
    equations: List[EquationOut] = Field(default_factory=list)
    variables: List[VariableOut] = Field(default_factory=list)


class SelectionIn(BaseModel):
    """The user's current assignment state for one entity type."""

    entity_type: str
    sequence: List[str] = Field(default_factory=list)
    base_equation: Optional[str] = None
    instantiated: List[str] = Field(default_factory=list)
    ports: List[str] = Field(default_factory=list)


class AssignmentOut(BaseModel):
    entity_type: str
    sequence: List[str] = Field(default_factory=list)
    base_equation: Optional[str] = None
    state_variable: Optional[str] = None
    instantiated: List[str] = Field(default_factory=list)
    ports: List[str] = Field(default_factory=list)
    closed: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect(ctx):
    """Flatten the scoped context into the engine's input structures.

    Also derives the auto-instantiated set: variables that are
    instantiation endpoints by nature — bound-value classes
    (``INSTANTIATE_CLASSES``: constant/parameter) or carrying a
    pre-bound ``promo:value``.  The engine treats them as resolved
    without an explicit marking (hint/binding pattern).
    """
    variables: Dict[str, object] = {}
    equations: Dict[str, EquationInfo] = {}
    auto: set = set()
    for iri, var in ctx.variables().items():
        variables[iri] = var
        if (getattr(var, "type", None) in INSTANTIATE_CLASSES
                or getattr(var, "value", None) is not None):
            auto.add(iri)
        for eq in getattr(var, "equations", {}).values():
            equations[eq["iri"]] = EquationInfo(
                iri=eq["iri"],
                lhs=eq["lhs"],
                incidence=list(eq.get("incidence_list") or []),
            )
    return variables, equations, auto


def _labels(variables, equations) -> Dict[str, str]:
    """Display labels for every IRI the report can mention."""
    labels: Dict[str, str] = {}
    for iri, var in variables.items():
        labels[iri] = getattr(var, "label", iri)
    for iri, eq in equations.items():
        labels[iri] = iri
    return labels


def _assignment_graph_iri(graph_iri: Optional[str]) -> str:
    if graph_iri:
        return graph_iri.rstrip("/") + "/assignments"
    return DEFAULT_ASSIGNMENT_GRAPH


def _assignment_res(graph_iri: Optional[str], entity_type: str) -> URIRef:
    frag = entity_type.split("#")[-1].split("/")[-1]
    return URIRef(_assignment_graph_iri(graph_iri)
                  + "#assignment_" + frag)


def _assignment_graph(store, graph_iri: Optional[str]):
    """The assignment artefact graph, created on first use."""
    iri = _assignment_graph_iri(graph_iri)
    g = store.dataset.graph(URIRef(iri))
    if not len(g):
        uses = ([str(i) for i in store.resolution_scope(graph_iri)]
                if graph_iri else [str(store.ONTOLOGY_GRAPH_IRI)])
        store.create_artefact_graph(iri, "Assignment", uses=uses)
        g = store.dataset.graph(URIRef(iri))
    return g


def _drop_list(graph, head) -> None:
    """Remove every cons cell of an rdf:List (they are bnodes — a plain
    ``remove`` on the head would leave the tail orphaned)."""
    while isinstance(head, BNode):
        nxt = graph.value(head, RDF.rest)
        graph.remove((head, None, None))
        head = nxt


def _read_assignment(graph, res: URIRef) -> Optional[AssignmentOut]:
    if (res, RDF.type, PROMO["BehaviourAssignment"]) not in graph:
        return None
    head = graph.value(res, PROMO["hasEquationSequence"])
    sequence = [str(i) for i in Collection(graph, head)] if head else []
    base = graph.value(res, PROMO["hasBaseEquation"])
    state = graph.value(res, PROMO["hasStateVariable"])
    closed = graph.value(res, PROMO["closed"])
    return AssignmentOut(
        entity_type=str(graph.value(res, PROMO["forEntityType"]) or ""),
        sequence=sequence,
        base_equation=str(base) if base else None,
        state_variable=str(state) if state else None,
        instantiated=[str(v) for v in
                      graph.objects(res, PROMO["hasInstantiatedVariable"])],
        ports=[str(v) for v in
               graph.objects(res, PROMO["hasPortVariable"])],
        closed=bool(closed) if closed is not None else False,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/context", response_model=BehaviourContextResponse)
def context_endpoint(
    graph_iri: Optional[str] = Depends(graph_param),
) -> BehaviourContextResponse:
    """Entity types plus the scoped var/expr graph for the picker UI."""
    store = get_store()
    ctx = scoped_context(store, graph_iri)
    variables, equations, _auto = _collect(ctx)

    entity_types = []
    for et in ctx.entity_types():
        scale_values = [str(sv) for sv in ctx.graph.objects(
            URIRef(et["iri"]), PROMO["hasScaleValue"])]
        entity_types.append(EntityTypeOut(
            iri=et["iri"], label=et["label"], branch=et["branch"],
            scale_values=scale_values))

    # Symbol rendering only needs index aliases — same CompileSpace
    # shortcut as document.build_document.
    space = CompileSpace(
        ctx.variables(), ctx.indices(),
        variable_definition_network="",
        expression_definition_network="",
    )

    return BehaviourContextResponse(
        entity_types=entity_types,
        equations=[EquationOut(
            iri=e["iri"],
            internal_id=e.get("internal_id"),
            lhs=e["lhs"],
            lhs_latex=_var_symbol(var, space),
            rhs=e.get("rhs") or "",
            rhs_latex=_rhs_latex(e, var, ctx),
            equation_class=e.get("equation_class"),
            network=e.get("network"),
            incidence=list(e.get("incidence_list") or []),
        ) for iri, var in ctx.variables().items()
          for e in getattr(var, "equations", {}).values()],
        variables=[VariableOut(
            iri=iri,
            label=getattr(v, "label", iri),
            network=getattr(v, "network", "root"),
            variable_class=getattr(v, "type", "state"),
            port_variable=getattr(v, "port_variable", False),
            tokens=list(getattr(v, "tokens", []) or []),
        ) for iri, v in variables.items()],
    )


@router.post("/evaluate")
def evaluate_endpoint(
    selection: SelectionIn,
    graph_iri: Optional[str] = Depends(graph_param),
) -> dict:
    """Evaluate a selection — the UI calls this after every pick."""
    store = get_store()
    ctx = scoped_context(store, graph_iri)
    variables, equations, auto = _collect(ctx)
    report = evaluate(equations, Selection(
        sequence=list(selection.sequence),
        base_equation=selection.base_equation,
        instantiated=set(selection.instantiated),
        ports=set(selection.ports),
    ), auto_instantiated=auto)
    out = asdict(report)
    out["labels"] = _labels(variables, equations)
    return out


@router.get("/assignments", response_model=List[AssignmentOut])
def list_assignments(
    graph_iri: Optional[str] = Depends(graph_param),
) -> List[AssignmentOut]:
    """All stored assignments in the scope's assignment graph."""
    store = get_store()
    g = store.dataset.graph(URIRef(_assignment_graph_iri(graph_iri)))
    out = []
    for res in g.subjects(RDF.type, PROMO["BehaviourAssignment"]):
        found = _read_assignment(g, res)
        if found is not None:
            out.append(found)
    return out


@router.get("/assignment", response_model=AssignmentOut)
def get_assignment(
    entity_type: str,
    graph_iri: Optional[str] = Depends(graph_param),
) -> AssignmentOut:
    """Read the stored assignment for an entity type (404 if none)."""
    store = get_store()
    g = store.dataset.graph(URIRef(_assignment_graph_iri(graph_iri)))
    found = _read_assignment(g, _assignment_res(graph_iri, entity_type))
    if found is None:
        raise HTTPException(
            status_code=404,
            detail="no assignment for entity type %s" % entity_type)
    return found


@router.put("/assignment", response_model=AssignmentOut)
def put_assignment(
    selection: SelectionIn,
    graph_iri: Optional[str] = Depends(editable_param),
) -> AssignmentOut:
    """Persist a selection as the entity type's assignment artefact.

    The selection is evaluated first; the resulting ``closed`` flag is
    stamped on the resource so consumers can tell a finished assignment
    from work in progress.
    """
    store = get_store()
    ctx = scoped_context(store, graph_iri)
    variables, equations, auto = _collect(ctx)
    report = evaluate(equations, Selection(
        sequence=list(selection.sequence),
        base_equation=selection.base_equation,
        instantiated=set(selection.instantiated),
        ports=set(selection.ports),
    ), auto_instantiated=auto)

    g = _assignment_graph(store, graph_iri)
    res = _assignment_res(graph_iri, selection.entity_type)

    # Replace semantics: drop the old list cells before the resource's
    # own triples so no orphaned cons cells survive.
    old_head = g.value(res, PROMO["hasEquationSequence"])
    if old_head is not None:
        _drop_list(g, old_head)
    g.remove((res, None, None))

    g.add((res, RDF.type, PROMO["BehaviourAssignment"]))
    g.add((res, PROMO["forEntityType"], URIRef(selection.entity_type)))
    if selection.base_equation:
        g.add((res, PROMO["hasBaseEquation"],
               URIRef(selection.base_equation)))
    if report.state_variable:
        g.add((res, PROMO["hasStateVariable"],
               URIRef(report.state_variable)))
    head = BNode()
    Collection(g, head, [URIRef(e) for e in selection.sequence])
    g.add((res, PROMO["hasEquationSequence"], head))
    for var in selection.instantiated:
        g.add((res, PROMO["hasInstantiatedVariable"], URIRef(var)))
    for var in selection.ports:
        g.add((res, PROMO["hasPortVariable"], URIRef(var)))
    g.add((res, PROMO["closed"],
           Literal(report.closed, datatype=XSD.boolean)))
    store.declare_vocabulary(g)

    return AssignmentOut(
        entity_type=selection.entity_type,
        sequence=list(selection.sequence),
        base_equation=selection.base_equation,
        state_variable=report.state_variable,
        instantiated=list(selection.instantiated),
        ports=list(selection.ports),
        closed=report.closed,
    )


@router.delete("/assignment", status_code=204)
def delete_assignment(
    entity_type: str,
    graph_iri: Optional[str] = Depends(editable_param),
) -> None:
    """Drop an entity type's assignment (404 if none)."""
    store = get_store()
    g = store.dataset.graph(URIRef(_assignment_graph_iri(graph_iri)))
    res = _assignment_res(graph_iri, entity_type)
    if (res, RDF.type, PROMO["BehaviourAssignment"]) not in g:
        raise HTTPException(
            status_code=404,
            detail="no assignment for entity type %s" % entity_type)
    old_head = g.value(res, PROMO["hasEquationSequence"])
    if old_head is not None:
        _drop_list(g, old_head)
    g.remove((res, None, None))
