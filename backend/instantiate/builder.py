"""Model instantiation (design doc §19).

Pure-Python mechanics, no rdflib/FastAPI deps — the service layer
adapts store graphs into the plain structures this module consumes.

Instantiation binds a model artefact (topology) to behaviour
assignments (per entity type) and produces the assembled equation-set
report:

- **Index element sets** — ``N`` = model nodes, ``A`` = token-flow
  arcs, each arc sub-index = its member arcs, and per entity type the
  node subset ``N_T``.
- **Variable bindings** — every variable referenced by an entity
  type's assignment gets a binding kind:

  - ``incidence`` — a ``[node, arc]``-indexed variable binds to the
    numeric ``F`` matrix for its arc index (base ``A`` or sub-index);
  - ``constant``  — pre-bound ``promo:value`` (universal constants),
    one global instance;
  - ``parameter`` — marked to-be-instantiated or a bound-value class;
  - ``port``      — external input, resolved per contact across an
    arc to a peer variable;
  - ``local``     — state/defined vars, index structures mapped to
    element sets (node index → the type's nodes, arc index → member
    arcs incident on the type's nodes; non-topological indices such
    as species stay symbolic).

- **Port resolution** — a port variable carrying token τ binds
  through an incident arc to the peer node's *defined* variable
  (sequence lhs ∪ state) with a comparable token (shared
  ``promo:parent`` ancestry).  ``tokenKind`` pre-filters carriers
  (conserved → token-flow arcs, reference → reference arcs).
  Arc-indexed peer vars bind at the arc element; node-indexed at the
  peer node.  One candidate → ``bound``; zero → ``unbound``; several
  → ``ambiguous``.

Unresolved indices and unbound/ambiguous ports are reported as
problems, never silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from backend.equation.checker import INSTANTIATE_CLASSES

from .resolver import (
    ArcInfo,
    ArcMembership,
    NodeInfo,
    SubIndexInfo,
    ancestors,
)

#: Carriers that participate in conservation (mirrors resolver/fbuilder).
_TOKEN_FLOW = (None, "token-flow")

#: tokenKind → arc carrier it may ride on.
_TOKEN_KIND_CARRIER = {"conserved": "token-flow", "reference": "reference"}


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass
class VarInfo:
    """The slice of a variable the builder needs."""

    iri: str
    label: str = ""
    internal_id: Optional[str] = None
    index_structures: List[str] = field(default_factory=list)
    tokens: List[str] = field(default_factory=list)
    value: Optional[str] = None
    var_class: str = "state"
    port_variable: bool = False


@dataclass
class EqInfo:
    """The slice of an equation the builder needs."""

    iri: str
    lhs: str
    inputs: List[str] = field(default_factory=list)  # incidence_list
    internal_id: Optional[str] = None


@dataclass
class AssignmentInfo:
    """A behaviour assignment for one entity type (§13 artefact)."""

    entity_type: str
    sequence: List[str] = field(default_factory=list)   # equation IRIs
    base_equation: Optional[str] = None
    state_variable: Optional[str] = None
    instantiated: List[str] = field(default_factory=list)
    ports: List[str] = field(default_factory=list)
    closed: bool = False


@dataclass
class IndexInfo:
    """An index with its source kind (raw ``promo:indexClass``)."""

    iri: str
    source: str = ""                    # "node" | "arc" | "token" | …
    sub_index_of: Optional[str] = None
    short_name: str = ""


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@dataclass
class VarBinding:
    """One variable's binding within an entity-type instantiation."""

    var: str
    role: str                           # state|defined|port|parameter|input
    binding: str                        # local|port|parameter|constant|incidence
    instance: str
    indices: Dict[str, Optional[List[str]]] = field(default_factory=dict)
    matrix: Optional[str] = None        # incidence: arc index IRI
    value: Optional[str] = None         # constant: pre-bound value


@dataclass
class EqBinding:
    """One equation in the instantiated computation sequence."""

    equation: str
    lhs: str                            # variable IRI
    inputs: List[str] = field(default_factory=list)


@dataclass
class EntityInstantiation:
    """The instantiated equation set for one entity type."""

    entity_type: str
    nodes: List[str] = field(default_factory=list)
    has_assignment: bool = False
    closed: bool = False
    state_variable: Optional[str] = None
    variables: List[VarBinding] = field(default_factory=list)
    equations: List[EqBinding] = field(default_factory=list)


@dataclass
class PortBinding:
    """Resolution of one port variable on one model node."""

    node: str
    var: str
    status: str                         # bound|unbound|ambiguous
    arc: Optional[str] = None
    peer_node: Optional[str] = None
    peer_var: Optional[str] = None
    element: Optional[str] = None       # arc or node IRI the peer var binds at
    candidates: List[Tuple[str, str, str]] = field(default_factory=list)


@dataclass
class Problem:
    kind: str
    message: str
    node: Optional[str] = None
    entity_type: Optional[str] = None


@dataclass
class Instantiation:
    """The assembled model equation-set report."""

    indices: Dict[str, List[str]] = field(default_factory=dict)
    entity_types: List[EntityInstantiation] = field(default_factory=list)
    ports: List[PortBinding] = field(default_factory=list)
    problems: List[Problem] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _frag(iri: str) -> str:
    return iri.split("#")[-1].split("/")[-1]


def _arc_like(idx: Optional[IndexInfo],
              indices: Dict[str, IndexInfo],
              seen: Optional[Set[str]] = None) -> bool:
    """True iff the index enumerates arcs (source ``arc`` or a
    sub-index chain that bottoms out at an arc index)."""
    seen = seen or set()
    while idx is not None and idx.iri not in seen:
        if idx.source == "arc":
            return True
        seen.add(idx.iri)
        idx = indices.get(idx.sub_index_of or "")
    return False


def _node_like(idx: Optional[IndexInfo],
               indices: Dict[str, IndexInfo],
               seen: Optional[Set[str]] = None) -> bool:
    seen = seen or set()
    while idx is not None and idx.iri not in seen:
        if idx.source == "node":
            return True
        seen.add(idx.iri)
        idx = indices.get(idx.sub_index_of or "")
    return False


def _comparable(t1: str, t2: str, token_parents: Dict[str, str]) -> bool:
    """Token comparability: shared ``promo:parent`` ancestry (either
    direction — a plain ``signal`` var matches ``observation`` and
    ``manipulation`` arcs, §14)."""
    return (t2 in ancestors(t1, token_parents)
            or t1 in ancestors(t2, token_parents))


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build(nodes: Dict[str, NodeInfo],
          arcs: Dict[str, ArcInfo],
          memberships: List[ArcMembership],
          sub_indices: Dict[str, SubIndexInfo],
          indices: Dict[str, IndexInfo],
          assignments: Dict[str, AssignmentInfo],
          variables: Dict[str, VarInfo],
          equations: Dict[str, EqInfo],
          token_parents: Dict[str, str],
          token_kinds: Dict[str, str],
          ) -> Instantiation:
    """Assemble the instantiated equation set for a model.

    ``memberships``/``sub_indices`` are the §16 resolver output;
    ``assignments`` maps entity-type IRI → §13 assignment artefact;
    ``variables``/``equations`` come from the var/expr scope;
    ``token_parents``/``token_kinds`` describe the token taxonomy.
    """
    report = Instantiation()
    problems = report.problems

    # -- topology -----------------------------------------------------------
    node_set = sorted(nodes)
    token_flow_arcs = sorted(
        m.arc for m in memberships if m.carrier in _TOKEN_FLOW)
    members: Dict[str, List[str]] = {}
    for m in memberships:
        for si in m.sub_indices:
            members.setdefault(si, []).append(m.arc)
    for v in members.values():
        v.sort()

    # Incident arcs per node (contact = either end, direction-free).
    incident: Dict[str, List[str]] = {n: [] for n in node_set}
    for a in arcs.values():
        for end in (a.source, a.target):
            if end in incident:
                incident[end].append(a.iri)
    for v in incident.values():
        v.sort()

    # Index element sets: node index, base arc index, sub-indices.
    node_index = next((i.iri for i in indices.values()
                       if i.source == "node" and not i.sub_index_of), None)
    base_arc_index = next((i.iri for i in indices.values()
                           if i.source == "arc" and not i.sub_index_of),
                          None)
    if node_index:
        report.indices[node_index] = node_set
    if base_arc_index:
        report.indices[base_arc_index] = token_flow_arcs
    for si in sorted(sub_indices.values(), key=lambda s: s.iri):
        report.indices[si.iri] = members.get(si.iri, [])

    # -- group nodes by entity type ------------------------------------------
    type_nodes: Dict[str, List[str]] = {}
    for n in node_set:
        et = nodes[n].entity_type
        if not et:
            problems.append(Problem(
                kind="untyped-node",
                message=f"model node {_frag(n)} has no entity type",
                node=n))
            continue
        type_nodes.setdefault(et, []).append(n)

    def arc_elements(idx_iri: str, type_node_set: Set[str],
                     ) -> Optional[List[str]]:
        """Element set for an arc-like symbolic index on entity type T:
        member arcs incident on T's nodes."""
        if idx_iri in sub_indices:
            pool = members.get(idx_iri, [])
        elif idx_iri == base_arc_index:
            pool = token_flow_arcs
        elif _arc_like(indices.get(idx_iri), indices):
            pool = token_flow_arcs
        else:
            return None
        return sorted(a for a in pool
                      if arcs[a].source in type_node_set
                      or arcs[a].target in type_node_set)

    def index_elements(idx_iri: str, type_node_set: Set[str],
                       t_nodes: List[str]) -> Optional[List[str]]:
        idx = indices.get(idx_iri)
        if _node_like(idx, indices):
            return list(t_nodes)
        return arc_elements(idx_iri, type_node_set)

    # -- per entity type ------------------------------------------------------
    for et in sorted(type_nodes):
        t_nodes = sorted(type_nodes[et])
        t_set = set(t_nodes)
        inst = EntityInstantiation(entity_type=et, nodes=t_nodes)
        report.entity_types.append(inst)

        asg = assignments.get(et)
        if asg is None:
            problems.append(Problem(
                kind="no-assignment",
                message=f"no behaviour assignment for {_frag(et)}",
                entity_type=et))
            continue
        inst.has_assignment = True
        inst.closed = asg.closed
        inst.state_variable = asg.state_variable
        if not asg.closed:
            problems.append(Problem(
                kind="assignment-open",
                message=f"assignment for {_frag(et)} is not closed",
                entity_type=et))

        defined: Set[str] = set()
        if asg.state_variable:
            defined.add(asg.state_variable)
        eq_seq: List[EqInfo] = []
        for eq_iri in asg.sequence:
            eq = equations.get(eq_iri)
            if eq is None:
                problems.append(Problem(
                    kind="missing-equation",
                    message=f"assignment references unknown equation "
                            f"{_frag(eq_iri)}",
                    entity_type=et))
                continue
            eq_seq.append(eq)
            defined.add(eq.lhs)
            inst.equations.append(EqBinding(
                equation=eq.iri, lhs=eq.lhs, inputs=list(eq.inputs)))

        # Variable discovery order: sequence lhs/inputs, then role lists.
        seen: Set[str] = set()
        ordered_vars: List[str] = []
        for eq in eq_seq:
            for v in [eq.lhs] + list(eq.inputs):
                if v not in seen:
                    seen.add(v)
                    ordered_vars.append(v)
        for v in ([asg.state_variable] if asg.state_variable else []
                  ) + list(asg.instantiated) + list(asg.ports):
            if v not in seen:
                seen.add(v)
                ordered_vars.append(v)

        for v_iri in ordered_vars:
            var = variables.get(v_iri)
            if var is None:
                problems.append(Problem(
                    kind="missing-variable",
                    message=f"assignment references unknown variable "
                            f"{_frag(v_iri)}",
                    entity_type=et))
                continue

            # Role within this entity type's assignment.
            if v_iri == asg.state_variable:
                role = "state"
            elif v_iri in asg.ports:
                role = "port"
            elif v_iri in asg.instantiated \
                    or var.var_class in INSTANTIATE_CLASSES:
                role = "parameter"
            elif v_iri in defined:
                role = "defined"
            else:
                role = "input"

            # Binding kind.
            idx_iris = list(var.index_structures)
            arc_idx = next((i for i in idx_iris
                            if _arc_like(indices.get(i), indices)), None)
            node_idx = next((i for i in idx_iris
                             if _node_like(indices.get(i), indices)), None)
            if arc_idx and node_idx:
                binding = "incidence"
            elif var.value is not None:
                binding = "constant"
            elif role == "parameter":
                binding = "parameter"
            elif role == "port":
                binding = "port"
            elif role == "input":
                binding = "input"
            else:
                binding = "local"

            if binding == "input":
                problems.append(Problem(
                    kind="unmarked-input",
                    message=f"{var.label or _frag(v_iri)} is an external "
                            f"input of {_frag(et)} but is neither marked "
                            f"port nor instantiated",
                    entity_type=et))

            bound_indices: Dict[str, Optional[List[str]]] = {}
            if binding != "incidence":
                for i in idx_iris:
                    bound_indices[i] = index_elements(i, t_set, t_nodes)

            inst.variables.append(VarBinding(
                var=v_iri,
                role=role,
                binding=binding,
                instance=(var.internal_id or _frag(v_iri))
                         + "@" + _frag(et),
                indices=bound_indices,
                matrix=arc_idx if binding == "incidence" else None,
                value=var.value if binding == "constant" else None,
            ))

        # -- port resolution --------------------------------------------------
        # Arc-indexed ports bind per contact (one PortBinding per
        # incident carrier-matching arc); scalar ports aggregate all
        # candidates into a single binding.
        def peer_of(a_iri: str, n: str) -> Optional[str]:
            arc = arcs[a_iri]
            for end in (arc.source, arc.target):
                if end is not None and end != n:
                    return end
            return None

        def peer_defined(peer: str) -> Set[str]:
            peer_asg = assignments.get(nodes[peer].entity_type or "")
            if peer_asg is None:
                return set()
            out: Set[str] = set()
            if peer_asg.state_variable:
                out.add(peer_asg.state_variable)
            for eq_iri in peer_asg.sequence:
                eq = equations.get(eq_iri)
                if eq is not None:
                    out.add(eq.lhs)
            return out

        def emit_port(pb: PortBinding, var: VarInfo) -> None:
            report.ports.append(pb)
            if pb.status != "bound":
                problems.append(Problem(
                    kind=f"{pb.status}-port",
                    message=(f"port {var.label or _frag(pb.var)} on "
                             f"{_frag(pb.node)} is {pb.status}"),
                    node=pb.node, entity_type=et))

        for n in t_nodes:
            for v_iri in asg.ports:
                var = variables.get(v_iri)
                if var is None:
                    continue
                kinds = {token_kinds.get(t) for t in var.tokens} - {None}
                want = {_TOKEN_KIND_CARRIER.get(k) for k in kinds}
                carrier_ok = [
                    a for a in incident.get(n, [])
                    if not kinds or arcs[a].carrier in want]
                arc_indexed = any(
                    _arc_like(indices.get(i), indices)
                    for i in var.index_structures)

                def candidates_at(a_iri: str) -> List[Tuple[str, str]]:
                    peer = peer_of(a_iri, n)
                    if peer is None or peer not in nodes:
                        return []
                    # Candidates are the peer's *exported* defined vars
                    # (§14: port_variable = "can be exchanged") with a
                    # comparable token.
                    return [
                        (peer, w_iri)
                        for w_iri in sorted(peer_defined(peer))
                        if (w := variables.get(w_iri)) is not None
                        and w.port_variable
                        and any(_comparable(t, wt, token_parents)
                                for t in var.tokens
                                for wt in w.tokens)]

                if arc_indexed:
                    if not carrier_ok:
                        emit_port(PortBinding(node=n, var=v_iri,
                                              status="unbound"), var)
                    for a_iri in carrier_ok:
                        cands = candidates_at(a_iri)
                        pb = PortBinding(
                            node=n, var=v_iri, arc=a_iri,
                            status="unbound",
                            candidates=[(a_iri, p, w) for p, w in cands])
                        if len(cands) == 1:
                            peer, w_iri = cands[0]
                            w = variables[w_iri]
                            pb.status = "bound"
                            pb.peer_node = peer
                            pb.peer_var = w_iri
                            pb.element = (
                                a_iri if any(
                                    _arc_like(indices.get(i), indices)
                                    for i in w.index_structures)
                                else peer)
                        elif len(cands) > 1:
                            pb.status = "ambiguous"
                        emit_port(pb, var)
                else:
                    cands = [
                        (a_iri, peer, w_iri)
                        for a_iri in carrier_ok
                        for peer, w_iri in candidates_at(a_iri)]
                    pb = PortBinding(node=n, var=v_iri,
                                     status="unbound", candidates=cands)
                    if len(cands) == 1:
                        a_iri, peer, w_iri = cands[0]
                        w = variables[w_iri]
                        pb.status = "bound"
                        pb.arc = a_iri
                        pb.peer_node = peer
                        pb.peer_var = w_iri
                        pb.element = (
                            a_iri if any(
                                _arc_like(indices.get(i), indices)
                                for i in w.index_structures)
                            else peer)
                    elif len(cands) > 1:
                        pb.status = "ambiguous"
                    emit_port(pb, var)

    return report
