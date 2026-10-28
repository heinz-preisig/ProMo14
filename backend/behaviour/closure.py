"""Behaviour-linker closure engine.

Pure-Python evaluation of an entity-behaviour selection against the
var/expr bipartite graph — the mechanics of
``docs/behaviour-linker-design-discussion.md`` §8/§12/§13/§21:

- The user picks a **base equation**, then resolves each RHS variable
  recursively: another equation defines it, it is marked
  **to-be-instantiated**, or it is declared an **external input**
  (port).  The subgraph is *closed* when every RHS variable is
  resolved and every declared **output** is defined.
- A selected base equation makes its LHS variable the state of the
  entity.  Which equation is chosen is a user decision; ``lhs_class``
  is only a UI hint, not a semantic rule.  The state variable owns the
  only permitted dependency cycle (the integrator loop).  Choosing no
  base equation yields a stateless, acyclic entity.
- §21: the selection is a **lower-triangular sequence maintained by
  moves**, not edits — ``apply_move`` computes the minimal
  invariant-restoring sequence change for each gesture (pick /
  exchange, delete, mark / unmark, reorder, pick / unpick base).
  Every expression may only reference variables bound at an earlier
  slot or endpoints; an equation survives only inside the cone of a
  root — the base equation or a declared output.

Endpoints (§21): **state** (the base equation's LHS), **instantiated**
(bound value), **port** (external input across a model arc) and
**output** (external sink — computed for observation; its definer is a
reachability root alongside the base).

No rdflib/FastAPI imports: the service layer adapts store data into
the plain structures this module consumes, so the semantics are
testable in isolation.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class EquationInfo:
    """The slice of an equation the closure mechanics need."""

    iri: str
    lhs: str                              # variable IRI it defines
    lhs_class: str = "state"              # variable class of LHS
    incidence: List[str] = field(default_factory=list)  # RHS var IRIs


@dataclass
class Selection:
    """The user's current assignment state for one entity type."""

    # Ordered selected equation IRIs — the computation sequence.
    sequence: List[str] = field(default_factory=list)
    # The state-defining equation (must close the sequence); None for
    # stateless entities such as transport systems (§8).
    base_equation: Optional[str] = None
    # Variables marked to-be-instantiated (parameter endpoints).
    instantiated: Set[str] = field(default_factory=set)
    # Variables declared external inputs (port endpoints).
    ports: Set[str] = field(default_factory=set)
    # Variables declared external sinks (output endpoints, §21) —
    # their defining equations are reachability roots.
    outputs: Set[str] = field(default_factory=set)


@dataclass
class UnresolvedVar:
    """An RHS variable (or demanded output) with no resolution yet."""

    variable: str
    candidates: List[str] = field(default_factory=list)  # eq IRIs
    as_output: bool = False               # demanded by an output mark


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
    """The evaluation result the UI renders after every move."""

    state_variable: Optional[str]
    defined: Dict[str, str]                     # variable -> equation
    unresolved: List[UnresolvedVar]
    auto_instantiated: List[UnresolvedVar]      # bound-value endpoints
    frontier: List[str]                         # valid next equations
    cycles: List[List[str]]                     # equation-IRI paths
    conflicts: List[Conflict]
    order_violations: List[OrderViolation]
    warnings: List[str]
    closed: bool
    outputs: List[str] = field(default_factory=list)
    # Defined, non-state variables nothing consumes and no output
    # claims — candidate dead code / pending output marks (§21).
    unconsumed: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Shared mechanics
# ---------------------------------------------------------------------------

def _effective_auto(auto_instantiated: Optional[Set[str]],
                    selection: Selection,
                    defined_by: Dict[str, str]) -> Set[str]:
    """Bound-value endpoints minus anything explicitly resolved —
    a defining equation, an instantiated/port marking, or an output
    demand all override the class hint."""
    return ((auto_instantiated or set())
            - set(defined_by) - selection.instantiated
            - selection.ports - selection.outputs)


def _consumed(equations: Dict[str, EquationInfo],
              sequence: List[str]) -> Set[str]:
    """Variables referenced by any selected equation's incidence."""
    out: Set[str] = set()
    for eq_iri in sequence:
        eq = equations.get(eq_iri)
        if eq is not None:
            out.update(eq.incidence)
    return out


def _reachability_roots(equations: Dict[str, EquationInfo],
                        selection: Selection,
                        defined_by: Dict[str, str]) -> Set[str]:
    """Equations whose cone is legitimately in the subgraph (§21):
    the base equation, definers of declared outputs, and — for
    stateless selections — the tips (equations whose LHS nothing
    consumes: the frontier the user is growing toward a root)."""
    roots: Set[str] = set()
    if selection.base_equation in equations \
            and selection.base_equation in selection.sequence:
        roots.add(selection.base_equation)
    for var in selection.outputs:
        dep = defined_by.get(var)
        if dep is not None:
            roots.add(dep)
    if selection.base_equation is None:
        consumed = _consumed(equations, selection.sequence)
        for eq_iri in selection.sequence:
            eq = equations.get(eq_iri)
            if eq is not None and eq.lhs not in consumed:
                roots.add(eq_iri)                      # stateless tip
    return roots


def _cone(equations: Dict[str, EquationInfo],
          defined_by: Dict[str, str],
          roots: Set[str]) -> Set[str]:
    """All equations reachable from the roots via defined inputs."""
    reachable: Set[str] = set()
    stack = list(roots)
    while stack:
        cur = stack.pop()
        if cur in reachable or cur not in equations:
            continue
        reachable.add(cur)
        for var in equations[cur].incidence:
            dep = defined_by.get(var)
            if dep is not None and dep not in reachable:
                stack.append(dep)
    return reachable


def _order(equations: Dict[str, EquationInfo],
           selection: Selection,
           hints: Dict[str, float]) -> List[str]:
    """Stable lower-triangular sort of the kept equations.

    Edges run definer -> consumer; edges into the state variable are
    exempt — the integrator supplies it, and the base is pinned last
    by convention.  ``hints`` is a position score (smaller = earlier)
    preserving the user's ordering wherever the dependencies allow.
    Equations trapped in a non-state cycle are appended in hint order;
    ``evaluate`` reports the cycle.
    """
    defined_by: Dict[str, str] = {}
    for eq_iri in selection.sequence:
        eq = equations.get(eq_iri)
        if eq is not None:
            defined_by[eq.lhs] = eq_iri
    state_var = (equations[selection.base_equation].lhs
                 if selection.base_equation in equations else None)

    keep = [e for e in selection.sequence if e in equations]
    deps: Dict[str, Set[str]] = {e: set() for e in keep}
    consumers: Dict[str, Set[str]] = {e: set() for e in keep}
    for eq_iri in keep:
        if eq_iri == selection.base_equation:
            continue                              # pinned last
        for var in equations[eq_iri].incidence:
            if var == state_var:
                continue                          # integrator loop
            dep = defined_by.get(var)
            if dep is not None and dep != eq_iri and dep in deps:
                deps[eq_iri].add(dep)
                consumers[dep].add(eq_iri)

    body = [e for e in keep if e != selection.base_equation]
    heap = [(hints.get(e, float("inf")), e) for e in body
            if not deps[e]]
    heapq.heapify(heap)
    out: List[str] = []
    while heap:
        _h, eq_iri = heapq.heappop(heap)
        out.append(eq_iri)
        for con in consumers[eq_iri]:
            deps[con].discard(eq_iri)
            if not deps[con]:
                heapq.heappush(heap, (hints.get(con, float("inf")), con))
    leftovers = [e for e in body if e not in out]   # non-state cycles
    out.extend(sorted(leftovers,
                      key=lambda e: hints.get(e, float("inf"))))
    if selection.base_equation in equations \
            and selection.base_equation in selection.sequence:
        out.append(selection.base_equation)
    return out


def _auto_pull(equations: Dict[str, EquationInfo],
               selection: Selection,
               auto_instantiated: Optional[Set[str]]) -> List[str]:
    """Resolve every uniquely-definable open variable.

    A variable with exactly one candidate equation offers no choice —
    the move pulls the definer in.  Repeats to a fixpoint (a pull may
    itself open new variables); bounded by the equation count.
    Variables with zero or several candidates stay open.
    """
    pulled: List[str] = []
    for _ in range(len(equations) + 1):
        defined_by = {equations[e].lhs: e for e in selection.sequence
                      if e in equations}
        auto = _effective_auto(auto_instantiated, selection, defined_by)
        endpoints = (set(defined_by) | selection.instantiated
                     | selection.ports | auto)
        state_var = (equations[selection.base_equation].lhs
                     if selection.base_equation in equations else None)
        if state_var:
            endpoints.add(state_var)
        open_vars: Set[str] = (
            _consumed(equations, selection.sequence)
            | selection.outputs) - endpoints
        singles: List[str] = []
        for var in sorted(open_vars):
            cands = [e.iri for e in equations.values()
                     if e.lhs == var and e.iri not in selection.sequence]
            if len(cands) == 1:
                singles.append(cands[0])
        if not singles:
            break
        # Insert after the currently-last non-base equation; the
        # ordering pass places each where it belongs.
        at = (len(selection.sequence) - 1
              if selection.base_equation is not None
              else len(selection.sequence))
        for cand in singles:
            if cand not in selection.sequence:
                selection.sequence.insert(at, cand)
                at += 1
                pulled.append(cand)
    return pulled


def _reclose(equations: Dict[str, EquationInfo],
             selection: Selection,
             hints: Optional[Dict[str, float]] = None,
             auto_instantiated: Optional[Set[str]] = None,
             auto_pull: bool = False) -> dict:
    """Restore the §21 invariant after a move; mutates ``selection``.

    Steps: drop unknown/dangling equations; a defining equation wins
    over instantiated/port marks on its LHS (mark moves remove the
    definer explicitly beforehand); prune the cone to the
    reachability roots; pull uniquely-definable open variables;
    re-order lower-triangularly against the position hints.
    """
    pulled: List[str] = []
    pruned: List[str] = []

    # Unknown equations cannot be kept.
    kept: List[str] = []
    for eq_iri in selection.sequence:
        if eq_iri in equations:
            kept.append(eq_iri)
        else:
            pruned.append(eq_iri)
    selection.sequence = kept

    # Duplicate definitions: first occurrence wins.
    seen_lhs: Set[str] = set()
    deduped: List[str] = []
    for eq_iri in selection.sequence:
        lhs = equations[eq_iri].lhs
        if lhs in seen_lhs:
            pruned.append(eq_iri)
            continue
        seen_lhs.add(lhs)
        deduped.append(eq_iri)
    selection.sequence = deduped

    defined_by = {equations[e].lhs: e for e in selection.sequence}

    # A selected definer beats an instantiated/port mark on the same
    # variable (mark moves drop the definer before reclosing, so this
    # only reconciles loaded/legacy state).
    selection.instantiated -= set(defined_by)
    selection.ports -= set(defined_by)

    # Prune everything outside the root cone — unreachable is a
    # transient the move completes or prunes (§21).
    roots = _reachability_roots(equations, selection, defined_by)
    if roots:
        keep = _cone(equations, defined_by, roots)
        for eq_iri in list(selection.sequence):
            if eq_iri not in keep:
                pruned.append(eq_iri)
        selection.sequence = [e for e in selection.sequence
                              if e in keep]
    # With no roots at all the whole selection would be dead code;
    # keeping it lets the report surface the problem (unmatched
    # outputs / cycles) instead of silently wiping the work.

    if auto_pull:
        pulled.extend(_auto_pull(equations, selection, auto_instantiated))

    # Position hints: preserve current order where none were given.
    pos = dict(hints) if hints else {}
    for i, e in enumerate(selection.sequence):
        pos.setdefault(e, float(i))
    selection.sequence = _order(equations, selection, pos)
    return {"pulled": pulled, "pruned": pruned}


# ---------------------------------------------------------------------------
# Moves (§21)
# ---------------------------------------------------------------------------

# Move kinds that pull in uniquely-definable definers automatically.
_PULL_KINDS = {"pick", "mark"}


def apply_move(equations: Dict[str, EquationInfo],
               selection: Selection,
               kind: str,
               variable: Optional[str] = None,
               equation: Optional[str] = None,
               sequence: Optional[List[str]] = None,
               role: Optional[str] = None,
               auto_instantiated: Optional[Set[str]] = None
               ) -> dict:
    """Apply one §21 move and re-close the selection.

    ``kind`` is one of:

    - ``pick_base`` — select/unselect the state-defining equation
      (``equation``; ``None`` unpicks).  The equation stays in the
      sequence on unpick; the now-ordinary integrator loop surfaces as
      a reported cycle until deleted.
    - ``pick`` — choose ``equation`` as the definer of ``variable``.
      Replaces a previous definer (exchange) and clears
      instantiated/port marks on the variable; an output mark survives
      (the variable must be computed).  Uniquely-definable inputs of
      the new expression are pulled in recursively.
    - ``delete`` — drop ``equation`` (and its exclusive cone);
      consumers reopen as unresolved.
    - ``mark`` — declare ``variable`` an endpoint of ``role``
      (``instantiated`` | ``ports`` | ``outputs``).  Endpoint marks
      are exclusive; marking instantiated/port drops the variable's
      defining equation.
    - ``unmark`` — remove ``variable`` from all endpoint sets; a
      dropped output re-runs pruning over its cone.
    - ``reorder`` — ``sequence`` is a desired permutation used purely
      as position hints; the result is the closest legal order.

    Returns ``{"selection": Selection, "pulled": [...],
    "pruned": [...]}`` — the re-closed selection plus the equations
    the move added/removed on the user's behalf.
    """
    sel = Selection(sequence=list(selection.sequence),
                    base_equation=selection.base_equation,
                    instantiated=set(selection.instantiated),
                    ports=set(selection.ports),
                    outputs=set(selection.outputs))
    hints: Optional[Dict[str, float]] = None

    if kind == "pick_base":
        sel.base_equation = equation
        if equation is not None and equation not in sel.sequence:
            sel.sequence.append(equation)   # ordering pins it last
    elif kind == "pick":
        if variable is None or equation is None:
            raise ValueError("pick needs variable and equation")
        eq = equations.get(equation)
        if eq is None or eq.lhs != variable:
            raise ValueError(
                "equation %s does not define %s" % (equation, variable))
        sel.instantiated.discard(variable)
        sel.ports.discard(variable)
        old = next((e for e in sel.sequence
                    if equations[e].lhs == variable), None)
        if old is not None and old != equation:
            sel.sequence.remove(old)                    # exchange
        if equation not in sel.sequence:
            # Position hint: just before the earliest non-base
            # consumer of the variable — the ordering pass settles it.
            at = next((i for i, e in enumerate(sel.sequence)
                       if e != sel.base_equation
                       and variable in equations[e].incidence),
                      len(sel.sequence))
            sel.sequence.insert(at, equation)
    elif kind == "delete":
        if equation is None:
            raise ValueError("delete needs equation")
        if equation == sel.base_equation:
            sel.base_equation = None
        if equation in sel.sequence:
            sel.sequence.remove(equation)
    elif kind == "mark":
        if variable is None or role not in (
                "instantiated", "ports", "outputs"):
            raise ValueError(
                "mark needs variable and role "
                "(instantiated|ports|outputs)")
        if role == "outputs":
            sel.instantiated.discard(variable)
            sel.ports.discard(variable)
            sel.outputs.add(variable)
        else:
            target = (sel.instantiated if role == "instantiated"
                      else sel.ports)
            other = (sel.ports if role == "instantiated"
                     else sel.instantiated)
            other.discard(variable)
            sel.outputs.discard(variable)
            target.add(variable)
            # The mark ends computation: drop the definer so its cone
            # can prune.
            definer = next((e for e in sel.sequence
                            if equations[e].lhs == variable), None)
            if definer is not None:
                sel.sequence.remove(definer)
                if definer == sel.base_equation:
                    sel.base_equation = None
    elif kind == "unmark":
        if variable is None:
            raise ValueError("unmark needs variable")
        sel.instantiated.discard(variable)
        sel.ports.discard(variable)
        sel.outputs.discard(variable)
    elif kind == "reorder":
        desired = [e for e in (sequence or []) if e in sel.sequence]
        hints = {e: float(i) for i, e in enumerate(desired)}
    else:
        raise ValueError("unknown move kind %r" % kind)

    result = _reclose(equations, sel, hints=hints,
                      auto_instantiated=auto_instantiated,
                      auto_pull=kind in _PULL_KINDS)
    return {"selection": sel, **result}


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(equations: Dict[str, EquationInfo],
             selection: Selection,
             auto_instantiated: Optional[Set[str]] = None
             ) -> ClosureReport:
    """Evaluate a selection against the var/expr graph.

    ``equations`` is every equation in scope (selected or not) keyed by
    IRI; ``selection`` is the user's current assignment state.
    ``auto_instantiated`` lists variables that are instantiation
    endpoints by nature — bound-value classes (constant/parameter) or
    carrying a pre-bound ``promo:value``.  They terminate the subgraph
    search without an explicit marking; selecting a defining equation
    or marking them instantiated/port/output overrides the hint
    (hint/binding pattern, §6–7).
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
                    or selection.sequence[-1] != selection.base_equation):
                order_violations.append(OrderViolation(
                    equation=selection.base_equation,
                    variable=state_var,
                    defined_by=selection.base_equation,
                    detail="base equation must close the sequence"))

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
    for var in sorted(selection.outputs & selection.instantiated):
        conflicts.append(Conflict(
            "output_and_instantiated", variable=var,
            detail="output is also marked instantiated"))
    for var in sorted(selection.outputs & selection.ports):
        conflicts.append(Conflict(
            "output_and_port", variable=var,
            detail="output is also declared a port"))

    # -- unresolved inputs --------------------------------------------------
    # Effective auto endpoints: the class/value hint loses to any explicit
    # resolution — a selected defining equation, an instantiated marking,
    # a port declaration, or an output demand.
    auto = _effective_auto(auto_instantiated, selection, defined_by)
    unresolved: List[UnresolvedVar] = []
    auto_refs: List[UnresolvedVar] = []
    seen: Set[str] = set()
    seen_auto: Set[str] = set()
    referenced: Set[str] = set()
    for eq_iri in selection.sequence:
        eq = equations.get(eq_iri)
        if eq is None:
            continue
        for var in eq.incidence:
            referenced.add(var)
            if var in auto and var not in seen_auto:
                seen_auto.add(var)
                auto_refs.append(UnresolvedVar(
                    variable=var,
                    candidates=[e.iri for e in equations.values()
                                if e.lhs == var and e.iri not in position]))
            if (var in defined_by or var in selection.instantiated
                    or var in selection.ports or var in auto
                    or var in seen):
                continue
            seen.add(var)
            candidates = [e.iri for e in equations.values()
                          if e.lhs == var and e.iri not in position]
            unresolved.append(
                UnresolvedVar(variable=var, candidates=candidates))

    # Declared outputs are demands: an undefined output joins the
    # unresolved set so the picker offers its definers (§21 — all four
    # endpoint kinds must be matched).
    defined_output_vars = {v for v in selection.outputs
                           if v in defined_by}
    for var in sorted(selection.outputs - defined_output_vars):
        if var in seen:
            continue
        seen.add(var)
        unresolved.append(UnresolvedVar(
            variable=var, as_output=True,
            candidates=[e.iri for e in equations.values()
                        if e.lhs == var and e.iri not in position]))

    # An instantiated variable may sit unreferenced on purpose — it
    # declares a bound value the entity provides outward (e.g. an
    # environment fixing a boundary variable).  An unreferenced port is
    # always suspect: it promises an input nothing consumes.
    for var in sorted(selection.ports - referenced):
        warnings.append(
            "declared port %s is not referenced by any selected "
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

    # -- reachability: everything selected must hang off a root cone —
    #    the base equation or a declared output (§21).  Stateless
    #    selections add their tips as roots. ------------------------------
    roots = _reachability_roots(equations, selection, defined_by)
    if roots:
        reachable = _cone(equations, defined_by, roots)
        for eq_iri in selection.sequence:
            if eq_iri in equations and eq_iri not in reachable:
                warnings.append(
                    "equation %s is not reachable from a root "
                    "(base equation or declared output)" % eq_iri)

    # -- unconsumed defined variables: dead-code / output-mark hints ------
    consumed = _consumed(equations, selection.sequence)
    unconsumed = sorted(
        v for v, e in defined_by.items()
        if v != state_var and v not in consumed
        and v not in selection.outputs)

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

    # -- frontier: equations that resolve an open variable and are
    #    reachable from the selected root cone -----------------------------
    full_reachable: Set[str] = set()
    stack: List[str] = []
    if selection.base_equation in equations:
        stack.append(selection.base_equation)
    else:
        stack.extend(selection.sequence)
    for var in selection.outputs:
        dep = defined_by.get(var)
        if dep is not None:
            stack.append(dep)
    while stack:
        cur = stack.pop()
        if cur in full_reachable or cur not in equations:
            continue
        full_reachable.add(cur)
        for var in equations[cur].incidence:
            if (var in selection.instantiated or var in selection.ports
                    or var in auto):
                continue
            for e in equations.values():
                if e.lhs == var and e.iri not in full_reachable:
                    stack.append(e.iri)

    # Output demands reach their definers unconditionally: the output
    # itself is the root being grown.
    unresolved_eqs = {c for uv in unresolved for c in uv.candidates}
    output_cands = {c for uv in unresolved if uv.as_output
                    for c in uv.candidates}
    frontier = sorted(
        eq_iri for eq_iri in unresolved_eqs
        if eq_iri not in position
        and (eq_iri in full_reachable or eq_iri in output_cands))

    has_work = (bool(selection.sequence)
                or bool(selection.instantiated)
                or bool(selection.ports)
                or bool(selection.outputs))
    closed = (has_work
              and not unresolved and not cycles and not conflicts
              and not order_violations and not unconsumed)
    return ClosureReport(
        state_variable=state_var,
        defined=defined_by,
        unresolved=unresolved,
        auto_instantiated=auto_refs,
        frontier=frontier,
        cycles=cycles,
        conflicts=conflicts,
        order_violations=order_violations,
        warnings=warnings,
        closed=closed,
        outputs=sorted(selection.outputs),
        unconsumed=unconsumed,
    )
