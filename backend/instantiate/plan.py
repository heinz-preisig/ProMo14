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
from itertools import product
from typing import Any, Dict, List, Optional, Tuple

from .builder import (
    EqInfo,
    IndexInfo,
    Instantiation,
    Problem,
    VarBinding,
    VarInfo,
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
    #: §22 owning occurrence path (``""`` = host).
    occurrence: str = ""
    #: How x0 is supplied at t=0: ``cells`` (literal pin),
    #: ``initialise`` (an init equation determines it — solver
    #: unknown) or ``par`` (caller-supplied ``par["ic0_<name>"]``).
    ic_source: str = "par"
    #: The expanded value-cell table when ``ic_source == "cells"``.
    ic_values: Optional[List[Any]] = None


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
    indices: Dict[str, List[str]] = field(default_factory=dict)
    #: §22 owning occurrence path (``""`` = host).
    occurrence: str = ""


@dataclass
class MatrixLit:
    """An incidence binding as a sparse COO literal, restricted to
    the entity type's bound rows/cols."""

    instance: str
    name: str = ""                      # emitted identifier
    rows: List[str] = field(default_factory=list)
    cols: List[str] = field(default_factory=list)
    entries: List[Tuple[int, int, int]] = field(default_factory=list)
    indices: Dict[str, List[str]] = field(default_factory=dict)
    #: §22 owning occurrence path (``""`` = host).
    occurrence: str = ""


@dataclass
class ParamSlot:
    """A bound-value slot (constant/parameter) or external input."""

    var: str
    instance: str
    kind: str                           # constant|parameter|input
    name: str = ""                      # emitted identifier
    value: Optional[str] = None
    indices: Dict[str, List[str]] = field(default_factory=dict)
    #: §22 owning occurrence path (``""`` = host).
    occurrence: str = ""
    #: §20 ν channel: the var's stored value cells expanded over the
    #: bound element sets, flat in C (row-major) order; ``None``
    #: entries are missing cells (emitters render them as NaN).
    #: ``None`` = no table — the emitter falls back to a par lookup.
    values: Optional[List[Any]] = None


@dataclass
class OutputSlot:
    """A §21 output sink — a defined variable computed for
    observation.  Its value already exists as an emitted local inside
    the derivative; the slot names it for the dialect's output
    channel (``out`` arg / ``outs`` struct / multi-return)."""

    var: str
    instance: str
    entity_type: str
    name: str = ""                        # emitted identifier
    indices: Dict[str, List[str]] = field(default_factory=dict)
    #: §22 owning occurrence path (``""`` = host).
    occurrence: str = ""


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
    #: The entity type's bound element extent per index IRI — lets
    #: the emitter size-check a rhs whose index set differs from the
    #: lhs's (positional binding is legal; a size gap is not).
    bound: Dict[str, List[str]] = field(default_factory=dict)
    #: §32 bound-typing: var IRI → bound index IRIs, for vars whose
    #: bound index set differs from the declared
    #: ``index_structures`` (a node-declared port var on an
    #: event-dynamic entity is typed by its contact arcs).  The
    #: RHS check must run against this binding context — the
    #: declared form would green-light ``p_mech * F_conv`` as an
    #: N-contraction, which is the wrong math.
    var_bound: Dict[str, List[str]] = field(default_factory=dict)
    #: The lhs needs an initial guess (a ``SolveRoot`` body in the
    #: canonical RHS) — emitters seed the nested solve with it.
    guess: bool = False
    #: §22 occurrence path this block lives in — `""` = the host
    #: artefact's own content; non-empty = a `comp/inner` instance
    #: path.  Emission grouping only — scheduling stays global.
    occurrence: str = ""


@dataclass
class CodePlan:
    """The target-agnostic codegen plan."""

    states: List[StateSlot] = field(default_factory=list)
    gathers: List[Gather] = field(default_factory=list)
    matrices: List[MatrixLit] = field(default_factory=list)
    params: List[ParamSlot] = field(default_factory=list)
    inputs: List[ParamSlot] = field(default_factory=list)
    outputs: List[OutputSlot] = field(default_factory=list)
    levels: List[List[PlanBlock]] = field(default_factory=list)
    #: SCC members as (occurrence, entity_type, equation) triples.
    loops: List[List[Tuple[str, str, str]]] = field(default_factory=list)
    #: t=0 layer: the ``initialise``-class equation blocks (one
    #: residual each inside the emitted ``initial`` solve).
    initials: List[PlanBlock] = field(default_factory=list)
    constraints: List[PlanBlock] = field(default_factory=list)
    #: occurrence → entity_type → var IRI → emitted identifier (the
    #: renderer's name override — per-instance names, not bare ids).
    names: Dict[str, Dict[str, Dict[str, str]]] = field(
        default_factory=dict)
    #: §22 referenced-composite occurrences in this plan, ordered
    #: host-first.  Each entry: ``{path, comp, refersTo,
    #: overrides}`` — the keys emitters group blocks by when
    #: emitting call-style per-artefact functions.
    occurrences: List[Dict[str, Any]] = field(default_factory=list)


def name_map(cp: "CodePlan", occurrence: str,
             entity_type: str) -> Dict[str, str]:
    """A block's emitted-name map — ``names[occurrence][etype][var]``.

    §22 Option A: the same var IRI has a distinct emitted name per
    occurrence, so the renderer must look names up in the block's
    own (occurrence, entity type) context.
    """
    return cp.names.get(occurrence, {}).get(entity_type, {})


def plan(report: Instantiation, sched: Schedule,
         incidence: IncidenceReport,
         equations: Dict[str, EqInfo],
         indices: Dict[str, IndexInfo],
         values: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None,
         canonicals: Optional[Dict[str, Any]] = None,
         occurrences: Optional[List[Dict[str, Any]]] = None,
         variables: Optional[Dict[str, VarInfo]] = None
         ) -> CodePlan:
    """Lower an instantiation report + schedule into a CodePlan.

    ``values`` maps ``(occurrence_path, var_iri)`` to a stored
    value-cell table (``{coordinate_key: scalar}`` — the §20 ν
    channel); parameter and input slots carrying a table emit as
    literals instead of runtime ``par`` lookups.  An occurrence's
    own cells key coordinates by the *submodel's* element IRIs —
    ``_value_table`` retries each lookup with the occurrence prefix
    stripped so the submodel's defaults apply while the host's
    occurrence-qualified cells take precedence.  ``canonicals``
    (eq IRI → canonical Expression) flags ``SolveRoot`` bodies on
    plan blocks — their lhs needs an initial guess in the emitted
    ``initial`` solve."""
    from backend.equation.canonical import ic_targets

    out = CodePlan()
    out.occurrences = [
        {"path": o.get("path", ""), "comp": o.get("comp", ""),
         "refersTo": o.get("refersTo", ""),
         "overrides": o.get("overrides", {}),
         "pins": o.get("pins", {})}
        for o in (occurrences or []) if not o.get("cycle")]
    canonicals = canonicals or {}
    # element-class selectors: sub-index IRI → its element set, so a
    # fill-pattern segment can name a sub-index and match the members
    # (docs/value-fill.md).
    subsets = {inc.index: set(inc.arcs)
               for inc in incidence.sub_indices}

    bindings: Dict[Tuple[str, str, str], VarBinding] = {}
    for e in report.entity_types:
        for v in e.variables:
            bindings[(e.occurrence, e.entity_type, v.var)] = v

    node_inst = {n: (e.occurrence, e.entity_type)
                 for e in report.entity_types for n in e.nodes}

    # Occurrence tag for emitted identifiers — the composite local
    # names along the path (``Composite_1/…/Composite_7`` →
    # ``Composite_1_Composite_7``), so names stay short and readable.
    def occ_tag(path: str) -> str:
        if not path:
            return ""
        chain = sorted(
            (o for o in out.occurrences
             if o.get("path") and path.startswith(o["path"])),
            key=lambda o: len(o["path"]))
        return "_".join(
            o["comp"].rsplit("/", 1)[-1] for o in chain if o.get("comp"))

    # Emitted identifiers: occurrence tag + internal_id, suffixed
    # with the entity type's fragment when several types share the
    # variable in one occurrence (a port var and its peer are the
    # same IRI — without the suffix their instances collide).
    counts = Counter(v.instance.split("@")[0] for v in bindings.values())

    def emit_name(vb: VarBinding) -> str:
        base, _, frag = vb.instance.partition("@")
        stem = base.rsplit("/", 1)[-1]
        tag = occ_tag(vb.occurrence)
        n = re.sub(r"\W", "_", (tag + "_" if tag else "") + stem)
        if counts[base] > 1:
            n += "_" + re.sub(r"\W", "_", frag).removeprefix("etype_")
        return n

    names: Dict[str, Dict[str, Dict[str, str]]] = {}
    for (o, et, var), vb in bindings.items():
        names.setdefault(o, {}).setdefault(et, {})[var] = emit_name(vb)
    out.names = names

    # -- states -------------------------------------------------------------
    offset = 0
    for e in report.entity_types:
        if not e.state_variable:
            continue
        vb = bindings.get((e.occurrence, e.entity_type,
                           e.state_variable))
        if vb is None:
            continue
        size = 1
        for els in vb.indices.values():
            size *= max(1, len(els or []))
        ic_values = _value_table(vb, values or {}, report.problems,
                                 subsets)
        ic_values = _filled_table(vb, ic_values, report.problems,
                                  "IC")
        init_lhs = {q.lhs for q in e.initial_equations}
        ic_source = ("cells" if ic_values is not None
                     else "initialise" if vb.var in init_lhs
                     else "par")
        out.states.append(StateSlot(
            var=vb.var, instance=vb.instance,
            entity_type=e.entity_type, indices=vb.indices,
            name=names[e.occurrence][e.entity_type][vb.var],
            offset=offset, size=size,
            ic_source=ic_source, ic_values=ic_values,
            occurrence=e.occurrence))
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
                instance=v.instance,
                name=names[v.occurrence][e.entity_type][v.var],
                rows=rows, cols=cols, entries=entries,
                indices=v.indices, occurrence=v.occurrence))

    # -- params / inputs ------------------------------------------------------
    for e in report.entity_types:
        for v in e.variables:
            if v.binding in ("constant", "parameter") \
                    or (v.binding == "fixed" and v.value is not None):
                # A fixed var carrying promo:value inlines like a
                # constant; without one it becomes an input slot below.
                out.params.append(ParamSlot(
                    var=v.var, instance=v.instance,
                    kind="constant" if v.binding == "fixed" else v.binding,
                    value=v.value,
                    indices=v.indices,
                    values=_filled_table(
                        v, _value_table(v, values or {}, report.problems,
                                        subsets), report.problems),
                    name=names[v.occurrence][e.entity_type][v.var],
                    occurrence=v.occurrence))
            elif v.binding in ("input", "fixed"):
                out.inputs.append(ParamSlot(
                    var=v.var, instance=v.instance, kind="input",
                    indices=v.indices,
                    values=_filled_table(
                        v, _value_table(v, values or {}, report.problems,
                                        subsets), report.problems),
                    name=names[v.occurrence][e.entity_type][v.var],
                    occurrence=v.occurrence))

    # -- gathers (bound ports → peer element positions) ----------------------
    # Port vars are instance-level: group a var's contacts across all
    # of the instance's nodes into one gather over its bound elements.
    by_type: Dict[Tuple[str, str, str], list] = {}
    for p in report.ports:
        if p.status == "bound" and p.peer_node and p.peer_var:
            key = node_inst.get(p.node)
            if key:
                by_type.setdefault((key[0], key[1], p.var), []).append(p)
    for (occ, et, var), pbs in sorted(by_type.items()):
        vb = bindings.get((occ, et, var))
        if vb is None:
            continue
        # One gather piece per run of contacts sharing a peer — a
        # port's contacts may resolve to DIFFERENT peers (upstream
        # vs downstream efforts).  Sibling pieces sharing an instance
        # concatenate at emit, in contact order.
        arc_elements = _bound_elements(vb, indices, _arc_like)
        if arc_elements:
            # Arc-indexed port: contacts ordered by bound arc.
            by_arc = {b.arc: b for b in pbs if b.arc}
            contacts = [by_arc[a] for a in arc_elements if a in by_arc]
        else:
            contacts = list(pbs)
        run: list = []
        run_peer: Optional[Tuple] = None

        def _flush() -> None:
            if not run:
                return
            (peer_occ, peer_type), peer_vb = run_peer
            pos = {el: i for i, el in
                   enumerate(_all_elements(peer_vb))}
            out.gathers.append(Gather(
                var=var, instance=vb.instance,
                peer_instance=peer_vb.instance,
                name=names[occ][et][var],
                peer_name=names.get(peer_occ, {}).get(
                    peer_type, {}).get(
                    run[0].peer_var or "", peer_vb.instance),
                elements=[b.arc if arc_elements else (b.element or "")
                          for b in run],
                map=[pos.get(b.element or "", -1) for b in run],
                scalar=not vb.indices, indices=vb.indices,
                occurrence=occ))
            run.clear()

        for b in contacts:
            peer_key = node_inst.get(b.peer_node or "")
            peer_vb = (bindings.get((peer_key[0], peer_key[1],
                                     b.peer_var or ""))
                       if peer_key else None)
            if peer_vb is None:
                continue
            if (run_peer is not None
                    and run_peer[1].instance != peer_vb.instance):
                _flush()
            run_peer = (peer_key, peer_vb)
            run.append(b)
        _flush()

    # Coverage: a bound port var should gather exactly one value per
    # bound element — contacts fill slots positionally, so several
    # contacts on the same slot is an ambiguous (over-bound) binding.
    supplied: Dict[str, int] = {}
    sizes: Dict[str, int] = {}
    gname: Dict[str, str] = {}
    gvar: Dict[str, str] = {}
    for g in out.gathers:
        supplied[g.instance] = (supplied.get(g.instance, 0)
                                + len(g.elements))
        gname[g.instance] = g.name or g.instance
        gvar[g.instance] = g.var
        n = 1
        for els in (g.indices or {}).values():
            n *= max(1, len(els or []))
        sizes[g.instance] = n
    for inst, count in supplied.items():
        if count != sizes[inst]:
            over = count > sizes[inst]
            report.problems.append(Problem(
                kind="port-coverage",
                var=gvar[inst],
                message=("%s gathers %d peer element(s) into %d "
                         "bound slot(s) — %s"
                         % (gname[inst], count, sizes[inst],
                            "contacts over-cover the slots"
                            if over else "slots left unbound"))))

    # -- outputs (§21 observation sinks) -------------------------------------
    for e in report.entity_types:
        for v_iri in e.outputs:
            vb = bindings.get((e.occurrence, e.entity_type, v_iri))
            if vb is None:
                continue
            out.outputs.append(OutputSlot(
                var=v_iri, instance=vb.instance,
                entity_type=e.entity_type, indices=vb.indices,
                name=names[e.occurrence][e.entity_type][v_iri],
                occurrence=e.occurrence))

    # -- blocks in schedule order ---------------------------------------------
    # Every entity type's bound element extent per index IRI —
    # ``render_rhs`` uses it to tell a sanctioned positional
    # residual (same flat size, different index set) from a rhs the
    #: lhs genuinely can't hold.
    et_bound: Dict[Tuple[str, str], Dict[str, List[str]]] = {}
    for (o, et, _v), vb in bindings.items():
        m = et_bound.setdefault((o, et), {})
        for iri, els in (vb.indices or {}).items():
            m.setdefault(iri, els or [])
    # §32 bound-typing: vars whose BOUND index set differs from the
    # declared ``index_structures`` — the emit-time check must see
    # the bound form (a node-declared port var on an event-dynamic
    # entity types by its contact arcs).
    et_var_bound: Dict[Tuple[str, str], Dict[str, List[str]]] = {}
    for (o, et, v_iri), vb in bindings.items():
        var = (variables or {}).get(v_iri)
        bound_keys = [k for k, els in (vb.indices or {}).items()
                      if els is not None]
        if (var is not None
                and set(bound_keys) != set(var.index_structures)):
            et_var_bound.setdefault((o, et), {})[v_iri] = bound_keys
    prescribed = {(e.occurrence, e.entity_type, q.equation)
                  for e in report.entity_types
                  for q in e.equations if q.constraint}
    for lvl in sched.levels:
        out_lvl: List[PlanBlock] = []
        for b in lvl:
            vb = bindings.get((b.occurrence, b.entity_type, b.lhs))
            eq = equations.get(b.equation)
            canon = canonicals.get(b.equation)
            needs_guess = canon is not None and any(
                kind == "guess" for _, kind in ic_targets(canon, b.lhs))
            out_lvl.append(PlanBlock(
                entity_type=b.entity_type,
                equation=b.equation,
                lhs=b.lhs,
                lhs_instance=vb.instance if vb else b.lhs,
                lhs_name=(names.get(b.occurrence, {}).get(
                          b.entity_type, {}).get(b.lhs)
                          or (vb.instance if vb else b.lhs)),
                lhs_indices=vb.indices if vb else {},
                inputs=list(eq.inputs) if eq else [],
                rhs=eq.rhs if eq else "",
                loop=b.loop,
                bound=et_bound.get((b.occurrence, b.entity_type), {}),
                var_bound=et_var_bound.get(
                    (b.occurrence, b.entity_type), {}),
                guess=needs_guess,
                # §22 Option A: ownership is the instantiation's, not
                # element-inferred — a bound boundary arc (host-IRI)
                # stays inside the occurrence's extent.
                occurrence=b.occurrence))
        out.constraints.extend(
            b for b in out_lvl
            if (b.occurrence, b.entity_type, b.equation) in prescribed)
        out.levels.append(
            [b for b in out_lvl
             if (b.occurrence, b.entity_type, b.equation)
             not in prescribed])
    out.loops = sched.loops

    # -- t0 layer: initialise-class equation blocks -------------------------
    for e in report.entity_types:
        for q in e.initial_equations:
            vb = bindings.get((e.occurrence, e.entity_type, q.lhs))
            eq = equations.get(q.equation)
            out.initials.append(PlanBlock(
                entity_type=e.entity_type,
                equation=q.equation,
                lhs=q.lhs,
                lhs_instance=vb.instance if vb else q.lhs,
                lhs_name=(names.get(e.occurrence, {}).get(
                          e.entity_type, {}).get(q.lhs)
                          or (vb.instance if vb else q.lhs)),
                lhs_indices=vb.indices if vb else {},
                inputs=list(eq.inputs) if eq else list(q.inputs),
                rhs=eq.rhs if eq else "",
                bound=et_bound.get((e.occurrence, e.entity_type), {}),
                var_bound=et_var_bound.get(
                    (e.occurrence, e.entity_type), {}),
                occurrence=e.occurrence))
    return out


def _filled_table(v: VarBinding, table: Optional[List[Any]],
                  problems: Optional[List[Problem]],
                  what: str = "value") -> Optional[List[Any]]:
    """Reject a partially filled table: ``None`` cells can't be a
    numeric literal — an ``unfilled-cells`` problem is recorded and
    the caller falls back to the ``par`` lookup instead of emitting
    a ``None`` that crashes the emitted solver."""
    if table is None:
        return None
    if any(cell is None for cell in table):
        if problems is not None:
            problems.append(Problem(
                kind="unfilled-cells", var=v.var,
                message=("%s cells for %s are not all filled — "
                         "falling back to a par lookup"
                         % (what, v.instance))))
        return None
    return table


def _value_table(v: VarBinding,
                 values: Dict[Tuple[str, str], Dict[str, Any]],
                 problems: Optional[List[Problem]] = None,
                 subsets: Optional[Dict[str, set]] = None,
                 ) -> Optional[List[Any]]:
    """A var's stored value cells + fill rules expanded over its
    bound element sets — flat in C order (last index varies fastest;
    convention: docs/value-cells.md), ``None`` for unfilled cells.
    ``None`` when the var carries no table or one of its indices is
    unbound (symbolic extent).

    ``values`` is keyed ``(occurrence, var)`` — each occurrence
    binding consults its own table.  The coordinate key joins
    element IRIs in ``indexStructure`` order — the same order
    ``v.indices`` is built in — so the product of the bound element
    sets enumerates every cell exactly once.  An occurrence's bound
    elements carry its path prefix; a lookup that misses retries
    with the prefix stripped, so cells authored inside the submodel
    (unqualified element IRIs) apply while host pins written
    against qualified coordinates win by exact match.

    Keys containing a ``*`` segment are fill rules (docs/value-fill.md):
    a cell takes the exact key first, else the most specific matching
    fill; equal-score overlaps append a ``fill-conflict`` problem —
    never a silent winner.  ``subsets`` maps a sub-index IRI to its
    element set so a pattern segment can select an element *class*.

    Per-axis match weight: concrete element 2, sub-index 1, ``*`` 0 —
    a pattern's score is the axis sum."""
    cells = (values.get((v.occurrence, v.var))
             # var-keyed tables tolerated — direct callers without
             # occurrence context (never authoritative in service
             # assembly, which always keys per occurrence).
             or values.get(v.var))
    if not cells:
        return None
    axes: List[List[str]] = []
    for els in v.indices.values():
        if els is None:
            return None
        axes.append(els)
    subsets = subsets or {}
    exact: Dict[str, Any] = {}
    fills: List[Tuple[Tuple[str, ...], Any]] = []
    for key, val in cells.items():
        segs = tuple(s for s in str(key).split("|") if s)
        # '*' or a sub-index segment marks a fill pattern — an exact
        # key is all concrete elements (docs/value-fill.md).
        if "*" in segs or any(s in subsets for s in segs):
            fills.append((segs, val))
        else:
            exact[key] = val
    # deterministic order: pattern string sort — a conflict's pick
    # must not depend on dict insertion order.
    fills.sort(key=lambda f: f[0])
    n_bad = 0
    n_conflict = 0
    first_conflict = ""

    def _resolve(coord: Tuple[str, ...]) -> Any:
        nonlocal n_bad, n_conflict, first_conflict
        key = "|".join(coord)
        if key in exact:
            return exact[key]
        best_spec, best = -1, []
        for pat, val in fills:
            if len(pat) != len(coord):
                n_bad += 1
                continue
            score = 0
            for p, c in zip(pat, coord):
                if p == c:
                    score += 2
                elif p == "*":
                    pass
                elif c in subsets.get(p, ()):
                    score += 1
                else:
                    break
            else:
                if score > best_spec:
                    best_spec, best = score, [(pat, val)]
                elif score == best_spec:
                    best.append((pat, val))
        if len(best) > 1:
            n_conflict += 1
            if not first_conflict:
                first_conflict = key
        return best[0][1] if best else None

    # §22: an occurrence's bound elements are path-qualified; cells
    # authored inside the submodel key unqualified coordinates, so a
    # miss retries with the occurrence prefix stripped from every
    # segment.  Exact/fill matching runs against whichever form the
    # table actually carries.
    occ = v.occurrence

    def _resolve_any(coord: Tuple[str, ...]) -> Any:
        if not occ:
            return _resolve(coord)
        out = _resolve(coord)
        if out is not None:
            return out
        stripped = tuple(
            s[len(occ):] if s.startswith(occ) else s for s in coord)
        if stripped == coord:
            return None
        return _resolve(stripped)

    out = [_resolve_any(coord) for coord in product(*axes)]
    if problems is not None:
        if n_bad:
            problems.append(Problem(
                kind="bad-fill", var=v.var,
                message=("%d fill pattern(s) with the wrong axis count "
                         "ignored" % n_bad)))
        if n_conflict:
            problems.append(Problem(
                kind="fill-conflict", var=v.var,
                message=("%d cell(s) covered by equal-specificity fill "
                         "patterns (first: %s) — resolve explicitly"
                         % (n_conflict, first_conflict))))
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


def sub_plan_slice(cp: CodePlan, path: str) -> CodePlan:
    """The per-occurrence slice of a merged plan (§22).

    Slots and blocks owned *directly* by ``path`` — nested
    occurrences own their own content, so deeper prefixes are
    excluded.  Loops survive only when every member sits inside the
    slice (a boundary-crossing coupling loop belongs to the host).
    The nested-occurrence registry carries over so deeper slices
    nest naturally.  Ownership is the explicit ``occurrence``
    field each slot and block carries (§22 Option A).
    """
    sub = CodePlan()
    sub.occurrences = [dict(o) for o in cp.occurrences
                       if o.get("path", "").startswith(path + "/")]

    sub.states = [s for s in cp.states if s.occurrence == path]
    sub.params = [p for p in cp.params if p.occurrence == path]
    sub.inputs = [p for p in cp.inputs if p.occurrence == path]
    sub.gathers = [g for g in cp.gathers if g.occurrence == path]
    sub.matrices = [m for m in cp.matrices if m.occurrence == path]
    sub.outputs = [o for o in cp.outputs if o.occurrence == path]
    members = {(b.occurrence, b.entity_type, b.equation)
               for lvl in cp.levels for b in lvl
               if b.occurrence == path}
    sub.levels = [lvl for lvl in
                  ([b for b in lvl if b.occurrence == path]
                   for lvl in cp.levels) if lvl]
    sub.initials = [b for b in cp.initials if b.occurrence == path]
    sub.loops = [scc for scc in cp.loops if set(scc) <= members]
    sub.constraints = [b for b in cp.constraints
                       if b.occurrence == path]
    sub.names = {o: {et: dict(m) for et, m in mm.items()}
                 for o, mm in cp.names.items()}
    return sub


# ---------------------------------------------------------------------------
# Deserialisation — a persisted promo:Instantiation's promo:plan JSON
# ---------------------------------------------------------------------------

def _mk(cls, d: Dict[str, Any]):
    """Construct a dataclass from a JSON dict, ignoring unknown keys."""
    return cls(**{k: v for k, v in d.items()
                  if k in cls.__dataclass_fields__})


def code_plan_from_dict(d: Dict[str, Any]) -> CodePlan:
    """Rebuild a ``CodePlan`` from its ``asdict`` JSON form —
    the shape persisted on a ``promo:Instantiation`` artefact."""
    cp = CodePlan()
    cp.states = [_mk(StateSlot, s) for s in d.get("states", [])]
    cp.gathers = [_mk(Gather, g) for g in d.get("gathers", [])]
    cp.matrices = [_mk(MatrixLit, m) for m in d.get("matrices", [])]
    for m in cp.matrices:
        m.entries = [tuple(e) for e in m.entries]
    cp.params = [_mk(ParamSlot, p) for p in d.get("params", [])]
    cp.inputs = [_mk(ParamSlot, p) for p in d.get("inputs", [])]
    cp.outputs = [_mk(OutputSlot, o) for o in d.get("outputs", [])]
    cp.levels = [[_mk(PlanBlock, b) for b in lvl]
                 for lvl in d.get("levels", [])]
    cp.loops = [[tuple(pair) for pair in scc]
                for scc in d.get("loops", [])]
    cp.initials = [_mk(PlanBlock, b) for b in d.get("initials", [])]
    cp.constraints = [_mk(PlanBlock, b) for b in d.get("constraints", [])]
    raw_names = d.get("names", {})
    if raw_names and all(
            isinstance(m, dict)
            and all(isinstance(n, str) for n in m.values())
            for m in raw_names.values()):
        # legacy 2-level {et: {var: name}} — pre-Option-A persisted
        # plans; host occurrence only.
        cp.names = {"": {et: dict(m) for et, m in raw_names.items()}}
    else:
        cp.names = {o: {et: dict(m) for et, m in mm.items()}
                    for o, mm in raw_names.items()}
    cp.occurrences = list(d.get("occurrences", []))
    return cp
