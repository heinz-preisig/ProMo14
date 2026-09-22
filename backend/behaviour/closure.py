"""Behaviour-linker closure engine.

Pure-Python evaluation of an entity-behaviour selection against the
var/expr bipartite graph — the mechanics of
``docs/behaviour-linker-design-discussion.md`` §8/§12/§13:

- The user picks a **base (state-defining) equation**, then resolves
  each RHS variable recursively: another equation defines it, it is
  marked **to-be-instantiated**, or it is declared an **external
  input** (port).  The subgraph is *closed* when every RHS variable
  is resolved.
- The only permitted dependency cycle runs through the **state
  variable** (the integrator loop).  Any other cycle is an error the
  user must break by instantiating the variable or declaring it a
  port.
- The selection order *is* the computation sequence (§13): every
  non-base equation's inputs must be state, earlier-defined,
  instantiated, or port — the lower-triangular property.

No rdflib/FastAPI imports: the service layer adapts store data into
the plain structures this module consumes, so the semantics are
testable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class EquationInfo:
    """The slice of an equation the closure mechanics need."""

    iri: str
    lhs: str                              # variable IRI it defines
    incidence: List[str] = field(default_factory=list)  # RHS var IRIs


@dataclass
class Selection:
    """The user's current assignment state for one entity type."""

    # Ordered selected equation IRIs — the computation sequence.
    sequence: List[str] = field(default_factory=list)
    # The state-defining equation (must head the sequence); None for
    # stateless entities such as transport systems (§8).
    base_equation: Optional[str] = None
    # Variables marked to-be-instantiated (parameter endpoints).
    instantiated: Set[str] = field(default_factory=set)
    # Variables declared external inputs (port endpoints).
    ports: Set[str] = field(default_factory=set)


@dataclass
class UnresolvedVar:
    """An RHS variable with no resolution yet."""

    variable: str
    candidates: List[str] = field(default_factory=list)  # eq IRIs


@dataclass
class Conflict:
    """A structural inconsistency in the selection."""

    kind: str
    variable: Optional[str] = None
    equation: Optional[str] = None
    detail: str = ""


@dataclass
class OrderViolation:
    """A non-base equation consuming a variable defined too late."""

    equation: str
    variable: str
    defined_by: str
    detail: str = ""


@dataclass
class ClosureReport:
    """The evaluation result the UI renders after every pick."""

    state_variable: Optional[str]
    defined: Dict[str, str]                     # variable -> equation
    unresolved: List[UnresolvedVar]
    cycles: List[List[str]]                     # equation-IRI paths
    conflicts: List[Conflict]
    order_violations: List[OrderViolation]
    warnings: List[str]
    closed: bool


def evaluate(equations: Dict[str, EquationInfo],
             selection: Selection) -> ClosureReport:
    """Evaluate a selection against the var/expr graph.

    ``equations`` is every equation in scope (selected or not) keyed by
    IRI; ``selection`` is the user's current assignment state.
    """
    conflicts: List[Conflict] = []
    warnings: List[str] = []
    order_violations: List[OrderViolation] = []

    # -- definition map: variable -> its selected defining equation ------
    defined_by: Dict[str, str] = {}
    position: Dict[str, int] = {}
    for i, eq_iri in enumerate(selection.sequence):
        eq = equations.get(eq_iri)
        if eq is None:
            conflicts.append(Conflict(
                "unknown_equation", equation=eq_iri,
                detail="selected equation is not in scope"))
            continue
        position[eq_iri] = i
        if eq.lhs in defined_by:
            conflicts.append(Conflict(
                "duplicate_definition", variable=eq.lhs, equation=eq_iri,
                detail="variable already defined by %s"
                       % defined_by[eq.lhs]))
        else:
            defined_by[eq.lhs] = eq_iri

    # -- state variable ---------------------------------------------------
    state_var: Optional[str] = None
    if selection.base_equation is not None:
        base = equations.get(selection.base_equation)
        if base is None:
            conflicts.append(Conflict(
                "unknown_equation", equation=selection.base_equation,
                detail="base equation is not in scope"))
        else:
            state_var = base.lhs
            if (not selection.sequence
                    or selection.sequence[0] != selection.base_equation):
                order_violations.append(OrderViolation(
                    equation=selection.base_equation, variable=state_var,
                    defined_by=selection.base_equation,
                    detail="base equation must head the sequence"))

    # -- role conflicts ----------------------------------------------------
    for var in sorted(selection.instantiated & set(defined_by)):
        conflicts.append(Conflict(
            "defined_and_instantiated", variable=var,
            equation=defined_by[var],
            detail="variable is both defined and marked instantiated"))
    for var in sorted(selection.ports & set(defined_by)):
        conflicts.append(Conflict(
            "defined_and_port", variable=var, equation=defined_by[var],
            detail="variable is both defined and declared a port"))
    for var in sorted(selection.instantiated & selection.ports):
        conflicts.append(Conflict(
            "instantiated_and_port", variable=var,
            detail="variable is both instantiated and a port"))

    # -- unresolved inputs --------------------------------------------------
    unresolved: List[UnresolvedVar] = []
    seen: Set[str] = set()
    referenced: Set[str] = set()
    for eq_iri in selection.sequence:
        eq = equations.get(eq_iri)
        if eq is None:
            continue
        for var in eq.incidence:
            referenced.add(var)
            if (var in defined_by or var in selection.instantiated
                    or var in selection.ports or var in seen):
                continue
            seen.add(var)
            candidates = [e.iri for e in equations.values()
                          if e.lhs == var and e.iri not in position]
            unresolved.append(
                UnresolvedVar(variable=var, candidates=candidates))

    for var in sorted((selection.instantiated | selection.ports)
                      - referenced):
        warnings.append(
            "marked variable %s is not referenced by any selected "
            "equation" % var)

    # -- cycle check (§8): only the loop through the state variable is
    #    allowed; every other back-edge is an unwanted cycle --------------
    _WHITE, _GRAY, _BLACK = 0, 1, 2
    color = {e: _WHITE for e in selection.sequence if e in equations}
    cycles: List[List[str]] = []

    def visit(eq_iri: str, path: List[str]) -> None:
        color[eq_iri] = _GRAY
        for var in equations[eq_iri].incidence:
            if var == state_var:
                continue                  # the integrator loop — allowed
            dep = defined_by.get(var)
            if dep is None:
                continue                  # endpoint: param/port/unresolved
            if color[dep] == _GRAY:
                cycles.append(path + [eq_iri, dep])
            elif color[dep] == _WHITE:
                visit(dep, path + [eq_iri])
        color[eq_iri] = _BLACK

    for eq_iri in selection.sequence:
        if color.get(eq_iri) == _WHITE:
            visit(eq_iri, [])

    # -- reachability: everything selected must hang off the base cone ----
    if selection.base_equation in equations:
        reachable: Set[str] = set()
        stack = [selection.base_equation]
        while stack:
            cur = stack.pop()
            if cur in reachable:
                continue
            reachable.add(cur)
            for var in equations[cur].incidence:
                dep = defined_by.get(var)
                if dep is not None and dep not in reachable:
                    stack.append(dep)
        for eq_iri in selection.sequence:
            if eq_iri in equations and eq_iri not in reachable:
                warnings.append(
                    "equation %s is not reachable from the base equation"
                    % eq_iri)

    # -- lower-triangular order check (§13) --------------------------------
    for eq_iri in selection.sequence:
        if eq_iri == selection.base_equation:
            continue                      # integrator reads the whole loop
        eq = equations.get(eq_iri)
        if eq is None:
            continue
        i = position[eq_iri]
        for var in eq.incidence:
            if var == state_var:
                continue                  # state comes from the integrator
            dep = defined_by.get(var)
            if dep is not None and position[dep] > i:
                order_violations.append(OrderViolation(
                    equation=eq_iri, variable=var, defined_by=dep,
                    detail="input is defined later in the sequence"))

    closed = (bool(selection.sequence)
              and not unresolved and not cycles and not conflicts
              and not order_violations)
    return ClosureReport(
        state_variable=state_var,
        defined=defined_by,
        unresolved=unresolved,
        cycles=cycles,
        conflicts=conflicts,
        order_violations=order_violations,
        warnings=warnings,
        closed=closed,
    )
