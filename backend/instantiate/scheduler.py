"""Evaluation scheduling for the §19 instantiation report.

The builder assembles *what* computes; the scheduler derives *when*.
Nodes of the dependency DAG are ``(entity_type, equation)`` pairs —
the vectorized equation blocks codegen will emit.  An edge
``A → B`` means B consumes a variable A defines:

- **intra-type** — B's input is the lhs of another equation in the
  same entity type (the assignment's lower-triangular structure);
- **cross-type** — B's input is a *bound* port variable; the edge
  goes to the equation defining the peer variable in the peer's
  entity type (the port binding's ``peer_node`` → its type).

**States are sources**: a state variable's value comes from the
integrator, not from its balance equation (which yields the
*derivative*).  So consuming a state creates no edge — this is what
breaks the differential cycle and leaves only *algebraic* loops.

**Constants, parameters, incidence matrices, unbound ports and
unmarked inputs** create no edges — they are bound data or already
reported problems.

Output: ``Schedule.levels`` — blocks grouped by dependency depth
(same level = independent, parallelisable); ``Schedule.loops`` —
SCCs of size > 1 (or self-dependent equations), the algebraic loops
that need iterative solution (``fsolve``) or tearing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from .builder import Instantiation

#: A DAG node: (entity type IRI, equation IRI).
_Node = Tuple[str, str]


@dataclass
class SchedBlock:
    """One equation block in the evaluation plan."""

    entity_type: str
    equation: str
    lhs: str
    loop: int = -1                    # loop id, or -1 if acyclic


@dataclass
class Schedule:
    """The evaluation plan for an instantiated model."""

    levels: List[List[SchedBlock]] = field(default_factory=list)
    loops: List[List[_Node]] = field(default_factory=list)


def schedule(report: Instantiation) -> Schedule:
    """Derive the evaluation order from an instantiation report."""
    node_type: Dict[str, str] = {
        n: e.entity_type for e in report.entity_types for n in e.nodes}

    # (type, var) → defining equation; the state var is excluded —
    # its value is the integrator's, not the balance equation's.
    defines: Dict[Tuple[str, str], str] = {}
    lhs_of: Dict[_Node, str] = {}
    for e in report.entity_types:
        for q in e.equations:
            node = (e.entity_type, q.equation)
            lhs_of[node] = q.lhs
            if q.lhs != e.state_variable:
                defines[(e.entity_type, q.lhs)] = q.equation

    # Bound ports: (node, port var) → (peer node, peer var).
    port_peer: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for p in report.ports:
        if p.status == "bound" and p.peer_node and p.peer_var:
            port_peer[(p.node, p.var)] = (p.peer_node, p.peer_var)

    # Edges: dep → consumer (dep must evaluate first).
    succ: Dict[_Node, Set[_Node]] = {n: set() for n in lhs_of}
    for e in report.entity_types:
        for q in e.equations:
            consumer = (e.entity_type, q.equation)
            for v in q.inputs:
                dep_eq = defines.get((e.entity_type, v))
                if dep_eq is not None:
                    if dep_eq != q.equation:
                        succ[(e.entity_type, dep_eq)].add(consumer)
                    continue
                # Cross-type via bound ports on any node of this type.
                for n in e.nodes:
                    peer = port_peer.get((n, v))
                    if peer is None:
                        continue
                    peer_type = node_type.get(peer[0])
                    if peer_type is None:
                        continue
                    dep_eq = defines.get((peer_type, peer[1]))
                    if dep_eq is not None:
                        succ[(peer_type, dep_eq)].add(consumer)
                    break   # same var, same peer var — one edge suffices

    loops = _sccs(succ)
    loop_id = {n: i for i, scc in enumerate(loops) for n in scc}

    # Condensation DAG: each SCC collapses to one node so its members
    # share a level; level = longest path from a source.
    def rep(n: _Node):
        lid = loop_id.get(n, -1)
        return ("loop", lid) if lid >= 0 else n

    cpreds: Dict[object, Set[object]] = {}
    for dep, consumers in succ.items():
        for c in consumers:
            rd, rc = rep(dep), rep(c)
            if rd != rc:
                cpreds.setdefault(rc, set()).add(rd)
                cpreds.setdefault(rd, set())

    level_cache: Dict[object, int] = {}

    def level(r: object) -> int:
        if r not in level_cache:
            level_cache[r] = 1 + max(
                (level(p) for p in cpreds.get(r, ())), default=-1)
        return level_cache[r]

    by_level: Dict[int, List[_Node]] = {}
    for n in lhs_of:
        by_level.setdefault(level(rep(n)), []).append(n)

    out = Schedule()
    for lvl in sorted(by_level):
        out.levels.append([
            SchedBlock(entity_type=t, equation=q, lhs=lhs_of[(t, q)],
                       loop=loop_id.get((t, q), -1))
            for t, q in sorted(by_level[lvl])])
    out.loops = [sorted(scc) for scc in loops]
    return out


def _sccs(succ: Dict[_Node, Set[_Node]]) -> List[List[_Node]]:
    """Tarjan SCCs, iterative.  Returns only non-trivial components:
    size > 1, or a singleton with a self-edge."""
    index: Dict[_Node, int] = {}
    low: Dict[_Node, int] = {}
    on_stack: Set[_Node] = set()
    stack: List[_Node] = []
    result: List[List[_Node]] = []
    counter = 0

    for root in succ:
        if root in index:
            continue
        work: List[Tuple[_Node, object]] = [(root, iter(succ[root]))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, it = work[-1]
            advanced = False
            for m in it:                    # type: ignore[union-attr]
                if m not in index:
                    index[m] = low[m] = counter
                    counter += 1
                    stack.append(m)
                    on_stack.add(m)
                    work.append((m, iter(succ[m])))
                    advanced = True
                    break
                if m in on_stack:
                    low[node] = min(low[node], index[m])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                scc: List[_Node] = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    scc.append(w)
                    if w == node:
                        break
                if len(scc) > 1 or node in succ[node]:
                    result.append(scc)
    return result
