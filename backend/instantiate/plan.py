"""Codegen plan — the target-agnostic intermediate between the
§19 instantiation report and the language emitters.

``plan()`` lowers the report + schedule into pure data:

- **states** — the flat integrator layout: one slot per
  (entity type, state variable), ``offset``/``size`` into the state
  vector, elements in index order;
- **gathers** — port bindings as index maps: ``port[i] =
  peer[map[i]]`` over the port's bound elements (identity for
  arc-indexed peer vars, arc→node select for node-indexed);
- **matrices** — incidence bindings as sparse literals, *restricted
  to the entity type's bound element sets* (the global ``F[N,A]``
  loses the rows/cols the type doesn't own — stateless-node rows
  drop out);
- **params** / **inputs** — bound-value slots (constants carry
  ``value``) and unbound external inputs;
- **levels** — the schedule's equation blocks with their RHS text
  and the lhs's bound element sets, ready for per-target rendering.

Emitters (NumPy / Julia / Matlab) consume a ``CodePlan`` plus a
``CompileSpace`` — they parse+check each block's ``rhs`` and render
in schedule order.  The plan itself is inspectable and serialisable
— it is the natural shape of the deferred instantiation artefact.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .builder import (
    EqInfo,
    IndexInfo,
    Instantiation,
    VarBinding,
    _arc_like,
    _node_like,
)
from .fbuilder import IncidenceReport
from .scheduler import Schedule


@dataclass
class StateSlot:
    """One state variable's slice of the flat integrator vector."""

    var: str
    instance: str
    entity_type: str
    name: str = ""                        # emitted identifier
    indices: Dict[str, List[str]] = field(default_factory=dict)
    offset: int = 0
    size: int = 0


@dataclass
class Gather:
    """A bound port as an index map into the peer's element list."""

    var: str                            # port var IRI
    instance: str                       # port var's instance name
    peer_instance: str                  # peer var's instance name
    name: str = ""                      # emitted identifier
    peer_name: str = ""
    elements: List[str] = field(default_factory=list)   # port elems
    map: List[int] = field(default_factory=list)        # peer pos.
    scalar: bool = False                # no bound indices → select


@dataclass
class MatrixLit:
    """An incidence binding as a sparse COO literal, restricted to
    the entity type's bound rows/cols."""

    instance: str
    name: str = ""                      # emitted identifier
    rows: List[str] = field(default_factory=list)
    cols: List[str] = field(default_factory=list)
    entries: List[Tuple[int, int, int]] = field(default_factory=list)


@dataclass
class ParamSlot:
    """A bound-value slot (constant/parameter) or external input."""

    var: str
    instance: str
    kind: str                           # constant|parameter|input
    name: str = ""                      # emitted identifier
    value: Optional[str] = None


@dataclass
class PlanBlock:
    """One equation block in evaluation order."""

    entity_type: str
    equation: str
    lhs: str                            # var IRI
    lhs_instance: str
    lhs_name: str = ""                  # emitted identifier
    lhs_indices: Dict[str, List[str]] = field(default_factory=dict)
    inputs: List[str] = field(default_factory=list)     # var IRIs
    rhs: str = ""
    loop: int = -1


@dataclass
class CodePlan:
    """The target-agnostic codegen plan."""

    states: List[StateSlot] = field(default_factory=list)
    gathers: List[Gather] = field(default_factory=list)
    matrices: List[MatrixLit] = field(default_factory=list)
    params: List[ParamSlot] = field(default_factory=list)
    inputs: List[ParamSlot] = field(default_factory=list)
    levels: List[List[PlanBlock]] = field(default_factory=list)
    loops: List[List[Tuple[str, str]]] = field(default_factory=list)
    #: entity_type → var IRI → emitted identifier (the renderer's
    #: name override — per-type instance names, not bare ids).
    names: Dict[str, Dict[str, str]] = field(default_factory=dict)


def plan(report: Instantiation, sched: Schedule,
         incidence: IncidenceReport,
         equations: Dict[str, EqInfo],
         indices: Dict[str, IndexInfo]) -> CodePlan:
    """Lower an instantiation report + schedule into a CodePlan."""
    out = CodePlan()

    bindings: Dict[Tuple[str, str], VarBinding] = {}
    for e in report.entity_types:
        for v in e.variables:
            bindings[(e.entity_type, v.var)] = v

    node_type = {n: e.entity_type for e in report.entity_types
                 for n in e.nodes}

    # Emitted identifiers: the internal_id, suffixed with the entity
    # type's fragment when several types share the variable (a port
    # var and its peer are the same IRI — without the suffix their
    # instances collide).
    counts = Counter(v.instance.split("@")[0] for v in bindings.values())

    def emit_name(vb: VarBinding) -> str:
        base, _, frag = vb.instance.partition("@")
        n = re.sub(r"\W", "_", base)
        if counts[base] > 1:
            n += "_" + re.sub(r"\W", "_", frag).removeprefix("etype_")
        return n

    names: Dict[str, Dict[str, str]] = {}
    for (et, var), vb in bindings.items():
        names.setdefault(et, {})[var] = emit_name(vb)
    out.names = names

    # -- states -------------------------------------------------------------
    offset = 0
    for e in report.entity_types:
        if not e.state_variable:
            continue
        vb = bindings.get((e.entity_type, e.state_variable))
        if vb is None:
            continue
        size = 1
        for els in vb.indices.values():
            size *= max(1, len(els or []))
        out.states.append(StateSlot(
            var=vb.var, instance=vb.instance,
            entity_type=e.entity_type, indices=vb.indices,
            name=names[e.entity_type][vb.var],
            offset=offset, size=size))
        offset += size

    # -- matrices (incidence bindings, restricted to bound elements) --------
    matrices_by_index = {incidence.base.index: incidence.base}
    matrices_by_index.update(
        {m.index: m for m in incidence.sub_indices})
    for e in report.entity_types:
        for v in e.variables:
            if v.binding != "incidence" or not v.matrix:
                continue
            inc = matrices_by_index.get(v.matrix)
            if inc is None:
                continue
            rows = _bound_elements(v, indices, _node_like)
            cols = _bound_elements(v, indices, _arc_like)
            rmap = {n: i for i, n in enumerate(rows)}
            cmap = {a: i for i, a in enumerate(cols)}
            entries = [(rmap[n], cmap[a], s)
                       for n, a, s in
                       ((inc.nodes[r], inc.arcs[c], s)
                        for r, c, s in inc.entries)
                       if n in rmap and a in cmap]
            out.matrices.append(MatrixLit(
                instance=v.instance, name=names[e.entity_type][v.var],
                rows=rows, cols=cols, entries=entries))

    # -- params / inputs ------------------------------------------------------
    for e in report.entity_types:
        for v in e.variables:
            if v.binding in ("constant", "parameter"):
                out.params.append(ParamSlot(
                    var=v.var, instance=v.instance,
                    kind=v.binding, value=v.value,
                    name=names[e.entity_type][v.var]))
            elif v.binding == "input":
                out.inputs.append(ParamSlot(
                    var=v.var, instance=v.instance, kind="input",
                    name=names[e.entity_type][v.var]))

    # -- gathers (bound ports → peer element positions) ----------------------
    # Port vars are type-level: group a var's contacts across all of
    # the type's nodes into one gather over its bound elements.
    by_type: Dict[Tuple[str, str], list] = {}
    for p in report.ports:
        if p.status == "bound" and p.peer_node and p.peer_var:
            et = node_type.get(p.node)
            if et:
                by_type.setdefault((et, p.var), []).append(p)
    for (et, var), pbs in sorted(by_type.items()):
        vb = bindings.get((et, var))
        peer_type = node_type.get(pbs[0].peer_node or "")
        peer_vb = bindings.get(
            (peer_type or "", pbs[0].peer_var or ""))
        if vb is None or peer_vb is None:
            continue
        peer_elements = _all_elements(peer_vb)
        pos = {el: i for i, el in enumerate(peer_elements)}
        arc_elements = _bound_elements(vb, indices, _arc_like)
        if arc_elements:
            # Arc-indexed port: one entry per bound arc that resolved.
            by_arc = {b.arc: b for b in pbs if b.arc}
            elements = [a for a in arc_elements if a in by_arc]
            gmap = [pos.get(by_arc[a].element or "", -1)
                    for a in elements]
        else:
            # Scalar port: the peer element itself is the element.
            elements = [b.element or "" for b in pbs]
            gmap = [pos.get(b.element or "", -1) for b in pbs]
        out.gathers.append(Gather(
            var=var, instance=vb.instance,
            peer_instance=peer_vb.instance,
            name=names[et][var],
            peer_name=names.get(peer_type or "", {}).get(
                pbs[0].peer_var or "", peer_vb.instance),
            elements=elements, map=gmap,
            scalar=not vb.indices))

    # -- blocks in schedule order ---------------------------------------------
    for lvl in sched.levels:
        out_lvl: List[PlanBlock] = []
        for b in lvl:
            vb = bindings.get((b.entity_type, b.lhs))
            eq = equations.get(b.equation)
            out_lvl.append(PlanBlock(
                entity_type=b.entity_type,
                equation=b.equation,
                lhs=b.lhs,
                lhs_instance=vb.instance if vb else b.lhs,
                lhs_name=(names.get(b.entity_type, {}).get(b.lhs)
                          or (vb.instance if vb else b.lhs)),
                lhs_indices=vb.indices if vb else {},
                inputs=list(eq.inputs) if eq else [],
                rhs=eq.rhs if eq else "",
                loop=b.loop))
        out.levels.append(out_lvl)
    out.loops = sched.loops
    return out


def _bound_elements(v: VarBinding, indices: Dict[str, IndexInfo],
                    pred) -> List[str]:
    """The bound element list of a var's index matching ``pred``
    (``_node_like``/``_arc_like`` — they follow ``sub_index_of``
    ancestry, so a sub-index of an arc index counts as arc)."""
    for iri, els in v.indices.items():
        if pred(indices.get(iri), indices):
            return els or []
    return []


def _all_elements(v: VarBinding) -> List[str]:
    """All bound elements of a var, in index-declaration order."""
    out: List[str] = []
    for els in v.indices.values():
        out.extend(els or [])
    return out
