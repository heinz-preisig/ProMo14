"""Tests for the §19 instantiation builder.

Engine tests run on plain dicts; the endpoint test seeds a small model
(capacity —arc— diffusion transport —arc— capacity), variables,
equations and behaviour assignments into a throwaway store and checks
the assembled report.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rdflib import RDF, RDFS, Literal, URIRef

from backend.core import graph_store
from backend.core.graph_store import PROMO
from backend.instantiate.builder import (
    AssignmentInfo,
    EqInfo,
    IndexInfo,
    VarInfo,
    build,
)
from backend.instantiate.resolver import (
    ArcInfo,
    NodeInfo,
    SubIndexInfo,
    resolve,
)
from backend.equation.compile_space import CompileSpace, Index, Variable
from backend.equation.units import Units
from backend.instantiate.emit_python import emit_python
from backend.instantiate.fbuilder import build as fbuild
from backend.instantiate.plan import plan
from backend.instantiate.scheduler import schedule
from backend.main import app

BASE = "https://w3id.org/promo/ontology"


def _et(frag: str) -> str:
    return f"{BASE}#etype_{frag}"


def _idx(frag: str) -> str:
    return f"{BASE}#{frag}"


def _var(frag: str) -> str:
    return f"{BASE}#var_{frag}"


def _eq(frag: str) -> str:
    return f"{BASE}#eq_{frag}"


def _tok(frag: str) -> str:
    return f"{BASE}#tok_{frag}"


# ---------------------------------------------------------------------------
# Shared fixture: c1 —a1— t1 —a2— c2  (diffusion transport between capacities)
# ---------------------------------------------------------------------------

NODES = {
    "c1": NodeInfo("c1", _et("lumped_capacity")),
    "t1": NodeInfo("t1", _et("diffusion_transport")),
    "c2": NodeInfo("c2", _et("lumped_capacity")),
}

ARCS = {
    "a1": ArcInfo("a1", "c1", "t1", "token-flow"),
    "a2": ArcInfo("a2", "t1", "c2", "token-flow"),
}

PARENTS = {
    _et("diffusion_transport"): _et("mass_transport"),
    _et("mass_transport"): _et("transport_system"),
}

SUB_INDICES = {
    _idx("idx_arc_diffusion"): SubIndexInfo(
        _idx("idx_arc_diffusion"), _idx("idx_arc"),
        _et("diffusion_transport"), "A_diff"),
}

INDICES = {
    _idx("idx_node"): IndexInfo(_idx("idx_node"), source="node",
                                short_name="N"),
    _idx("idx_arc"): IndexInfo(_idx("idx_arc"), source="arc",
                               short_name="A"),
    _idx("idx_arc_diffusion"): IndexInfo(
        _idx("idx_arc_diffusion"), sub_index_of=_idx("idx_arc"),
        short_name="A_diff"),
    _idx("idx_species"): IndexInfo(_idx("idx_species"), source="token",
                                   short_name="S"),
}

TOKEN_PARENTS = {_tok("observation"): _tok("signal")}
TOKEN_KINDS = {
    _tok("mass"): "conserved",
    _tok("signal"): "reference",
    _tok("observation"): "reference",
}

VARIABLES = {
    _var("m"): VarInfo(_var("m"), "mass", "V_1",
                       index_structures=[_idx("idx_node")],
                       tokens=[_tok("mass")]),
    _var("p"): VarInfo(_var("p"), "pressure", "V_2",
                       index_structures=[_idx("idx_node")],
                       tokens=[_tok("mass")], port_variable=True),
    _var("J"): VarInfo(_var("J"), "diffusive flow", "V_3",
                       index_structures=[_idx("idx_arc_diffusion")],
                       tokens=[_tok("mass")], port_variable=True),
    _var("F"): VarInfo(_var("F"), "F_diff", "V_4",
                       index_structures=[_idx("idx_node"),
                                         _idx("idx_arc_diffusion")],
                       var_class="constant"),
    _var("k"): VarInfo(_var("k"), "conductivity", "V_5",
                       var_class="parameter"),
    _var("p_in"): VarInfo(_var("p_in"), "effort in", "V_6",
                          index_structures=[_idx("idx_arc_diffusion")],
                          tokens=[_tok("mass")]),
}

EQUATIONS = {
    _eq("bal"): EqInfo(_eq("bal"), _var("m"), [_var("F"), _var("J")],
                       "E_1", rhs="V_4 * V_3"),
    _eq("prop"): EqInfo(_eq("prop"), _var("p"), [_var("m")], "E_2",
                        rhs="V_1"),
    _eq("flow"): EqInfo(_eq("flow"), _var("J"),
                        [_var("k"), _var("p_in")], "E_3",
                        rhs="V_5 . V_6"),
}

ASSIGNMENTS = {
    _et("lumped_capacity"): AssignmentInfo(
        entity_type=_et("lumped_capacity"),
        sequence=[_eq("bal"), _eq("prop")],
        base_equation=_eq("bal"),
        state_variable=_var("m"),
        ports=[_var("J")],
        closed=True),
    _et("diffusion_transport"): AssignmentInfo(
        entity_type=_et("diffusion_transport"),
        sequence=[_eq("flow")],
        # no base_equation: a stateless transport has no balance, so
        # no state variable — J stays a defined var.
        ports=[_var("p_in")],
        instantiated=[_var("k")],
        closed=True),
}


def _build(nodes=NODES, arcs=ARCS, assignments=ASSIGNMENTS,
           variables=VARIABLES, equations=EQUATIONS):
    memberships = resolve(nodes, arcs, SUB_INDICES, PARENTS)
    return build(nodes, arcs, memberships, SUB_INDICES, INDICES,
                 assignments, variables, equations,
                 TOKEN_PARENTS, TOKEN_KINDS)


def _entity(rep, et):
    return next(e for e in rep.entity_types if e.entity_type == et)


def _binding(entity, var):
    return next(v for v in entity.variables if v.var == var)


# ---------------------------------------------------------------------------
# Index element sets
# ---------------------------------------------------------------------------

def test_index_element_sets():
    rep = _build()
    assert rep.indices[_idx("idx_node")] == ["c1", "c2", "t1"]
    assert rep.indices[_idx("idx_arc")] == ["a1", "a2"]
    assert rep.indices[_idx("idx_arc_diffusion")] == ["a1", "a2"]


def test_empty_sub_index_yields_empty_set():
    sub = dict(SUB_INDICES)
    sub[_idx("idx_arc_heat")] = SubIndexInfo(
        _idx("idx_arc_heat"), _idx("idx_arc"), _et("heat_transport"),
        "A_heat")
    memberships = resolve(NODES, ARCS, sub, PARENTS)
    rep = build(NODES, ARCS, memberships, sub, INDICES,
                ASSIGNMENTS, VARIABLES, EQUATIONS,
                TOKEN_PARENTS, TOKEN_KINDS)
    assert rep.indices[_idx("idx_arc_heat")] == []


# ---------------------------------------------------------------------------
# Variable bindings
# ---------------------------------------------------------------------------

def test_local_var_binds_node_elements():
    rep = _build()
    cap = _entity(rep, _et("lumped_capacity"))
    m = _binding(cap, _var("m"))
    assert m.role == "state"
    assert m.binding == "local"
    assert m.indices[_idx("idx_node")] == ["c1", "c2"]   # N_T, not all N
    assert m.instance == "V_1@etype_lumped_capacity"


def test_arc_indexed_var_binds_incident_members():
    rep = _build()
    tr = _entity(rep, _et("diffusion_transport"))
    j = _binding(tr, _var("J"))
    assert j.role == "defined"
    assert j.binding == "local"
    assert j.indices[_idx("idx_arc_diffusion")] == ["a1", "a2"]


def test_incidence_var_binds_matrix():
    rep = _build()
    cap = _entity(rep, _et("lumped_capacity"))
    f = _binding(cap, _var("F"))
    assert f.binding == "incidence"
    assert f.matrix == _idx("idx_arc_diffusion")
    # The bound element sets define the restricted matrix's
    # rows/cols for codegen (the matrix IS the binding, but its
    # extent comes from these).
    assert f.indices[_idx("idx_node")] == ["c1", "c2"]
    assert f.indices[_idx("idx_arc_diffusion")] == ["a1", "a2"]


def test_incidence_requires_constant_class():
    """A non-constant [N,A]-indexed variable is data, not F — it never
    takes the incidence matrix (here: an unmarked external input)."""
    variables = dict(VARIABLES)
    variables[_var("F")] = VarInfo(
        _var("F"), "F_diff", "V_4",
        index_structures=[_idx("idx_node"), _idx("idx_arc_diffusion")],
        var_class="state")
    rep = _build(variables=variables)
    cap = _entity(rep, _et("lumped_capacity"))
    f = _binding(cap, _var("F"))
    assert f.binding == "input"      # data, not incidence
    assert f.matrix is None
    assert f.indices[_idx("idx_node")] == ["c1", "c2"]
    assert f.indices[_idx("idx_arc_diffusion")] == ["a1", "a2"]
    assert any(p.kind == "unmarked-input" for p in rep.problems)


def test_parameter_and_constant_bindings():
    rep = _build()
    tr = _entity(rep, _et("diffusion_transport"))
    k = _binding(tr, _var("k"))
    assert k.role == "parameter" and k.binding == "parameter"

    const = VarInfo(_var("half"), "half", "V_9", value="0.5",
                    var_class="constant")
    variables = dict(VARIABLES)
    variables[_var("half")] = const
    equations = dict(EQUATIONS)
    equations[_eq("prop")] = EqInfo(_eq("prop"), _var("p"),
                                    [_var("m"), _var("half")], "E_2")
    rep = _build(variables=variables, equations=equations)
    cap = _entity(rep, _et("lumped_capacity"))
    h = _binding(cap, _var("half"))
    assert h.binding == "constant" and h.value == "0.5"


def test_unresolved_index_stays_symbolic():
    variables = dict(VARIABLES)
    variables[_var("c")] = VarInfo(
        _var("c"), "concentration", "V_7",
        index_structures=[_idx("idx_node"), _idx("idx_species")],
        tokens=[_tok("mass")])
    equations = dict(EQUATIONS)
    equations[_eq("prop")] = EqInfo(_eq("prop"), _var("p"),
                                    [_var("m"), _var("c")], "E_2")
    rep = _build(variables=variables, equations=equations)
    cap = _entity(rep, _et("lumped_capacity"))
    c = _binding(cap, _var("c"))
    assert c.indices[_idx("idx_node")] == ["c1", "c2"]
    assert c.indices[_idx("idx_species")] is None   # not topology


# ---------------------------------------------------------------------------
# Port resolution
# ---------------------------------------------------------------------------

def test_arc_indexed_port_binds_per_contact():
    """Transport's effort port binds to the peer capacity's exported
    effort at each incident arc — one binding per contact."""
    rep = _build()
    ports = [p for p in rep.ports if p.var == _var("p_in")]
    assert len(ports) == 2                       # two contacts
    by_arc = {p.arc: p for p in ports}
    assert by_arc["a1"].status == "bound"
    assert by_arc["a1"].peer_var == _var("p")
    assert by_arc["a1"].element == "c1"          # p is node-indexed
    assert by_arc["a2"].element == "c2"


def test_flow_port_binds_at_arc_element():
    """Capacity's flow port binds to the transport's arc-indexed J —
    the element is the arc itself."""
    rep = _build()
    ports = [p for p in rep.ports if p.var == _var("J")]
    assert len(ports) == 2                       # c1 via a1, c2 via a2
    by_node = {p.node: p for p in ports}
    assert by_node["c1"].status == "bound"
    assert by_node["c1"].peer_var == _var("J")
    assert by_node["c1"].element == "a1"         # J is arc-indexed
    assert by_node["c2"].element == "a2"


def test_unbound_and_ambiguous_ports():
    variables = dict(VARIABLES)
    # Peer defines nothing comparable: p carries an incomparable token
    # and the state m — though comparable — is unflagged → internal.
    variables[_var("p")] = VarInfo(_var("p"), "pressure", "V_2",
                                  index_structures=[_idx("idx_node")],
                                  tokens=[_tok("energy")])
    rep = _build(variables=variables)
    ports = [p for p in rep.ports if p.var == _var("p_in")]
    assert all(p.status == "unbound" for p in ports)
    assert any(pr.kind == "unbound-port" for pr in rep.problems)
    # …with the state-hidden hint.
    assert any("not exported" in pr.message for pr in rep.problems)

    # Two flagged comparable vars on the peer → ambiguous.
    variables = dict(VARIABLES)
    variables[_var("m")] = VarInfo(_var("m"), "mass", "V_1",
                                  index_structures=[_idx("idx_node")],
                                  tokens=[_tok("mass")],
                                  port_variable=True)
    rep = _build(variables=variables)
    ports = [p for p in rep.ports if p.var == _var("p_in")]
    assert all(p.status == "ambiguous" for p in ports)
    assert any(pr.kind == "ambiguous-port" for pr in rep.problems)


def test_unflagged_secondary_state_binds():
    """R3: port_variable is an override, not a gate — an unflagged
    defined var carrying a comparable token is still a candidate."""
    variables = dict(VARIABLES)
    variables[_var("p")] = VarInfo(_var("p"), "pressure", "V_2",
                                  index_structures=[_idx("idx_node")],
                                  tokens=[_tok("mass")],
                                  port_variable=False)
    rep = _build(variables=variables)
    ports = [p for p in rep.ports if p.var == _var("p_in")]
    assert all(p.status == "bound" for p in ports)
    assert all(p.peer_var == _var("p") for p in ports)


def test_flagged_state_exports():
    """Flagging the state marks it exportable — and preferred over
    unflagged same-token candidates."""
    variables = dict(VARIABLES)
    variables[_var("m")] = VarInfo(_var("m"), "mass", "V_1",
                                  index_structures=[_idx("idx_node")],
                                  tokens=[_tok("mass")],
                                  port_variable=True)
    variables[_var("p")] = VarInfo(_var("p"), "pressure", "V_2",
                                  index_structures=[_idx("idx_node")],
                                  tokens=[_tok("mass")],
                                  port_variable=False)
    rep = _build(variables=variables)
    ports = [p for p in rep.ports if p.var == _var("p_in")]
    assert all(p.status == "bound" and p.peer_var == _var("m")
               for p in ports)


def test_flag_disambiguates_same_token_vars():
    """Two comparable defined vars: ambiguous unflagged, the flag
    selects the export."""
    variables = dict(VARIABLES)
    variables[_var("h")] = VarInfo(_var("h"), "enthalpy", "V_8",
                                  index_structures=[_idx("idx_node")],
                                  tokens=[_tok("mass")])
    variables[_var("p")] = VarInfo(_var("p"), "pressure", "V_2",
                                  index_structures=[_idx("idx_node")],
                                  tokens=[_tok("mass")],
                                  port_variable=False)
    equations = dict(EQUATIONS)
    equations[_eq("prop2")] = EqInfo(_eq("prop2"), _var("h"),
                                     [_var("m")], "E_5")
    assignments = dict(ASSIGNMENTS)
    assignments[_et("lumped_capacity")] = AssignmentInfo(
        entity_type=_et("lumped_capacity"),
        sequence=[_eq("bal"), _eq("prop"), _eq("prop2")],
        base_equation=_eq("bal"),
        state_variable=_var("m"),
        ports=[_var("J")],
        closed=True)

    rep = _build(variables=variables, equations=equations,
                 assignments=assignments)
    ports = [p for p in rep.ports if p.var == _var("p_in")]
    assert all(p.status == "ambiguous" for p in ports)

    variables[_var("h")] = VarInfo(_var("h"), "enthalpy", "V_8",
                                  index_structures=[_idx("idx_node")],
                                  tokens=[_tok("mass")],
                                  port_variable=True)
    rep = _build(variables=variables, equations=equations,
                 assignments=assignments)
    ports = [p for p in rep.ports if p.var == _var("p_in")]
    assert all(p.status == "bound" and p.peer_var == _var("h")
               for p in ports)


def test_signal_token_comparability():
    """A port carrying plain `signal` matches an `observation` export
    (ancestor comparability, §14) — through a reference arc."""
    arcs = dict(ARCS)
    arcs["a3"] = ArcInfo("a3", "t1", "c1", "reference")
    variables = dict(VARIABLES)
    variables[_var("sensor")] = VarInfo(
        _var("sensor"), "sensor out", "V_8",
        tokens=[_tok("observation")], port_variable=True)
    variables[_var("sig_in")] = VarInfo(
        _var("sig_in"), "signal in", "V_9",
        tokens=[_tok("signal")])
    equations = dict(EQUATIONS)
    equations[_eq("sense")] = EqInfo(_eq("sense"), _var("sensor"),
                                     [_var("m")], "E_4")
    assignments = dict(ASSIGNMENTS)
    assignments[_et("lumped_capacity")] = AssignmentInfo(
        entity_type=_et("lumped_capacity"),
        sequence=[_eq("bal"), _eq("prop"), _eq("sense")],
        base_equation=_eq("bal"),
        state_variable=_var("m"),
        ports=[_var("J")],
        closed=True)
    assignments[_et("diffusion_transport")] = AssignmentInfo(
        entity_type=_et("diffusion_transport"),
        sequence=[_eq("flow")],
        base_equation=_eq("flow"),
        ports=[_var("p_in"), _var("sig_in")],
        instantiated=[_var("k")],
        closed=True)
    rep = _build(nodes=NODES, arcs=arcs, assignments=assignments,
                 variables=variables, equations=equations)
    ports = [p for p in rep.ports if p.var == _var("sig_in")]
    # scalar port over the reference arc: c1's exported `sensor`
    # (observation) is comparable to `signal` → bound at the peer node.
    assert len(ports) == 1
    assert ports[0].status == "bound"
    assert ports[0].arc == "a3"
    assert ports[0].peer_var == _var("sensor")
    assert ports[0].element == "c1"


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

def _levels(rep):
    """(type, eq) -> level map from a schedule."""
    sched = schedule(rep)
    return {b.equation: i
            for i, lvl in enumerate(sched.levels) for b in lvl}, sched


def test_schedule_linear_chain():
    """states → secondary states → flows → balances: prop (level 0)
    feeds the transport's flow (level 1) which feeds the balance
    (level 2).  The state var creates no edge — it is the
    integrator's output, not the balance equation's product."""
    rep = _build()
    lvl, sched = _levels(rep)
    assert lvl[_eq("prop")] == 0
    assert lvl[_eq("flow")] == 1
    assert lvl[_eq("bal")] == 2
    assert sched.loops == []


def test_schedule_algebraic_loop():
    """prop consuming the flow port closes an algebraic cycle
    {prop, flow} — reported as a loop; the balance stays outside."""
    equations = dict(EQUATIONS)
    equations[_eq("prop")] = EqInfo(_eq("prop"), _var("p"),
                                    [_var("m"), _var("J")], "E_2")
    rep = _build(equations=equations)
    lvl, sched = _levels(rep)
    assert len(sched.loops) == 1
    assert {q for _t, q in sched.loops[0]} == {
        _eq("prop"), _eq("flow")}
    block_loop = {b.equation: b.loop
                  for lvl_ in sched.levels for b in lvl_}
    assert block_loop[_eq("prop")] == 0
    assert block_loop[_eq("flow")] == 0
    assert block_loop[_eq("bal")] == -1
    assert lvl[_eq("bal")] > lvl[_eq("prop")]


def test_schedule_unbound_port_no_edge():
    """An unbound port contributes no dependency — flow drops to
    level 0 alongside prop."""
    variables = dict(VARIABLES)
    variables[_var("p")] = VarInfo(_var("p"), "pressure", "V_2",
                                  index_structures=[_idx("idx_node")],
                                  tokens=[_tok("energy")])
    rep = _build(variables=variables)
    lvl, sched = _levels(rep)
    assert lvl[_eq("prop")] == 0
    assert lvl[_eq("flow")] == 0
    assert lvl[_eq("bal")] == 1     # J port still bound → flow→bal
    assert sched.loops == []


# ---------------------------------------------------------------------------
# Codegen plan
# ---------------------------------------------------------------------------

def _plan(rep):
    memberships = resolve(NODES, ARCS, SUB_INDICES, PARENTS)
    inc = fbuild(NODES, ARCS, memberships, SUB_INDICES)
    return plan(rep, schedule(rep), inc, EQUATIONS, INDICES)


def test_plan_states_and_matrices():
    """The capacity's state m gets the [c1,c2] slot; F is restricted
    to the type's bound elements — the stateless transport row
    drops out of the global matrix."""
    cp = _plan(_build())
    assert len(cp.states) == 1
    st = cp.states[0]
    assert st.var == _var("m")
    assert st.instance == "V_1@etype_lumped_capacity"
    assert st.indices[_idx("idx_node")] == ["c1", "c2"]
    assert (st.offset, st.size) == (0, 2)

    assert len(cp.matrices) == 1
    mx = cp.matrices[0]
    assert mx.instance == "V_4@etype_lumped_capacity"
    assert mx.rows == ["c1", "c2"] and mx.cols == ["a1", "a2"]
    # a1: c1 -1 (t1's row dropped); a2: c2 +1.
    assert sorted(mx.entries) == [(0, 0, -1), (1, 1, 1)]

    assert [p.instance for p in cp.params] == [
        "V_5@etype_diffusion_transport"]
    assert cp.inputs == []


def test_plan_gathers():
    """Both ports become index maps over their bound arc elements:
    p_in gathers p at the arc's peer node; J is identity (the peer
    var is arc-indexed over the same set)."""
    cp = _plan(_build())
    by_var = {g.var: g for g in cp.gathers}
    pin = by_var[_var("p_in")]
    assert pin.elements == ["a1", "a2"]
    assert pin.map == [0, 1]          # a1→c1, a2→c2 in p's [c1,c2]
    assert pin.peer_instance == "V_2@etype_lumped_capacity"
    j = by_var[_var("J")]
    assert j.elements == ["a1", "a2"]
    assert j.map == [0, 1]            # identity over A_diff
    assert j.peer_instance == "V_3@etype_diffusion_transport"


def test_plan_blocks_carry_rhs_and_indices():
    """Blocks follow the schedule; each carries its lhs instance and
    bound element sets for the emitter."""
    cp = _plan(_build())
    seq = [b.equation for lvl in cp.levels for b in lvl]
    assert seq == [_eq("prop"), _eq("flow"), _eq("bal")]
    prop = cp.levels[0][0]
    assert prop.lhs_instance == "V_2@etype_lumped_capacity"
    assert prop.lhs_indices[_idx("idx_node")] == ["c1", "c2"]
    assert all(b.loop == -1 for lvl in cp.levels for b in lvl)


def _emit_space():
    """A CompileSpace over the fixture variables/indices — names are
    the internal_ids (V_N), which resolve via the space's
    internal-id map."""
    variables = {
        iri: Variable(
            iri=iri, internal_id=v.internal_id, label=v.label,
            network="", type=v.var_class, units=Units(),
            index_structures=v.index_structures, value=v.value)
        for iri, v in VARIABLES.items()
    }
    indices = {
        iri: Index(iri=iri, label=idx.short_name, network="",
                   index_class="index",
                   aliases={"internal_code": idx.short_name},
                   sub_index_of=idx.sub_index_of)
        for iri, idx in INDICES.items()
    }
    return CompileSpace(variables, indices,
                        variable_definition_network="",
                        expression_definition_network="")


def test_emit_python():
    """The NumPy emitter: state unpack, param lookup, gathers, the
    rendered blocks in schedule order, and the balance into dy.
    J is shared (capacity port + transport defined) → its instances
    get type-suffixed names."""
    src = emit_python(_plan(_build()), _emit_space())
    assert "V_4 = np.array([[-1, 0], [0, 1]])" in src
    assert "def derivative(t, y, par):" in src
    assert "V_1 = y[0:2]" in src
    assert 'V_5 = par["V_5"]' in src
    # level 0: p = m
    assert "V_2 = V_1" in src
    # level 1: p_in gathers p at peer nodes; J = k ⊙ p_in
    assert "V_6 = V_2[[0, 1]]" in src
    assert "V_3_diffusion_transport = V_5 * V_6" in src
    # level 2: J gather (identity over A_diff); dm = F·J
    assert ("V_3_lumped_capacity = V_3_diffusion_transport[[0, 1]]"
            in src)
    assert ("dy[0:2] = np.tensordot(V_4, V_3_lumped_capacity, "
            "axes=([1], [0]))" in src)
    assert "return dy" in src


# ---------------------------------------------------------------------------
# Problems
# ---------------------------------------------------------------------------

def test_missing_assignment_and_untyped_node():
    nodes = dict(NODES)
    nodes["x1"] = NodeInfo("x1", _et("reactor"))      # no assignment
    nodes["x2"] = NodeInfo("x2", None)                # untyped
    rep = _build(nodes=nodes)
    kinds = {p.kind for p in rep.problems}
    assert "no-assignment" in kinds
    assert "untyped-node" in kinds


def test_open_assignment_flagged():
    assignments = dict(ASSIGNMENTS)
    assignments[_et("lumped_capacity")] = AssignmentInfo(
        entity_type=_et("lumped_capacity"),
        sequence=[_eq("bal")], base_equation=_eq("bal"),
        state_variable=_var("m"), ports=[_var("J")], closed=False)
    rep = _build(assignments=assignments)
    cap = _entity(rep, _et("lumped_capacity"))
    assert cap.has_assignment and not cap.closed
    assert any(p.kind == "assignment-open" for p in rep.problems)


def test_unmarked_input_problem():
    equations = dict(EQUATIONS)
    equations[_eq("prop")] = EqInfo(_eq("prop"), _var("p"),
                                    [_var("m"), _var("k")], "E_2")
    rep = _build(equations=equations)
    cap = _entity(rep, _et("lumped_capacity"))
    k = _binding(cap, _var("k"))
    # k is parameter-class → parameter binding, not an unmarked input.
    assert k.binding == "parameter"
    variables = dict(VARIABLES)
    variables[_var("ext")] = VarInfo(_var("ext"), "external", "V_9")
    equations[_eq("prop")] = EqInfo(_eq("prop"), _var("p"),
                                    [_var("m"), _var("ext")], "E_2")
    rep = _build(variables=variables, equations=equations)
    assert any(p.kind == "unmarked-input" for p in rep.problems)


# ---------------------------------------------------------------------------
# Endpoint test (throwaway store)
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROMO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(graph_store, "_STORE", None)
    with TestClient(app) as c:
        yield c
    monkeypatch.setattr(graph_store, "_STORE", None)


def _seed_endpoint_model(store):
    """Seed nodes/arcs, variables, equations into the ontology graph."""
    g = store.ontology_graph
    base = str(store.ONTOLOGY_GRAPH_IRI)

    def node(frag, et_frag, label):
        iri = URIRef(f"{base}/ModelNode_{frag}")
        g.add((iri, RDF.type, PROMO["ModelNode"]))
        g.add((iri, PROMO["entityType"], URIRef(_et(et_frag))))
        g.add((iri, RDFS.label, Literal(label)))
        return str(iri)

    def arc(frag, src, tgt):
        iri = URIRef(f"{base}/ModelArc_{frag}")
        g.add((iri, RDF.type, PROMO["ModelArc"]))
        g.add((iri, PROMO["source"], URIRef(src)))
        g.add((iri, PROMO["target"], URIRef(tgt)))
        g.add((iri, PROMO["arcType"], Literal("promo:ArcType/token-flow")))
        return str(iri)

    def var(frag, label, indices=(), tokens=(), cls="state",
            port=False, internal_id=None):
        iri = URIRef(_var(frag))
        g.add((iri, RDF.type, PROMO["Variable"]))
        g.add((iri, RDFS.label, Literal(label)))
        g.add((iri, PROMO["variableClass"], Literal(cls)))
        if internal_id:
            g.add((iri, PROMO["internalID"], Literal(internal_id)))
        for i in indices:
            g.add((iri, PROMO["indexStructure"], URIRef(i)))
        for t in tokens:
            g.add((iri, PROMO["carriesToken"], URIRef(t)))
        if port:
            g.add((iri, PROMO["portVariable"], Literal(True)))
        return str(iri)

    def eq(frag, lhs_iri, inputs, internal_id):
        iri = URIRef(_eq(frag))
        g.add((iri, RDF.type, PROMO["Equation"]))
        g.add((iri, PROMO["internalID"], Literal(internal_id)))
        g.add((iri, PROMO["incidenceList"],
               Literal(json.dumps(inputs))))
        g.add((URIRef(lhs_iri), PROMO["hasEquation"], iri))
        return str(iri)

    n1 = node("c1", "lumped_capacity", "C1")
    n2 = node("t1", "diffusion_transport", "T")
    n3 = node("c2", "lumped_capacity", "C2")
    arc("a1", n1, n2)
    arc("a2", n2, n3)

    m = var("m", "mass", [_idx("idx_node")], [_tok("mass")],
            internal_id="V_1")
    p = var("p", "pressure", [_idx("idx_node")], [_tok("mass")],
            port=True, internal_id="V_2")
    j = var("J", "diffusive flow", [_idx("idx_arc_diffusion")],
            [_tok("mass")], port=True, internal_id="V_3")
    f = var("F", "F_diff",
            [_idx("idx_node"), _idx("idx_arc_diffusion")],
            cls="constant", internal_id="V_4")
    k = var("k", "conductivity", cls="parameter", internal_id="V_5")
    pin = var("p_in", "effort in", [_idx("idx_arc_diffusion")],
              [_tok("mass")], internal_id="V_6")

    e_bal = eq("bal", m, [f, j], "E_1")
    e_prop = eq("prop", p, [m], "E_2")
    e_flow = eq("flow", j, [k, pin], "E_3")
    return {
        "nodes": (n1, n2, n3), "m": m, "p": p, "j": j, "f": f,
        "k": k, "pin": pin,
        "e_bal": e_bal, "e_prop": e_prop, "e_flow": e_flow,
    }


def test_model_endpoint(client):
    store = graph_store.get_store()
    ids = _seed_endpoint_model(store)
    graph = str(store.ONTOLOGY_GRAPH_IRI)

    # Behaviour assignments via the BL endpoint (evaluates + stamps
    # closed).
    r = client.put("/api/behaviour/assignment", json={
        "entity_type": _et("lumped_capacity"),
        "sequence": [ids["e_bal"], ids["e_prop"]],
        "base_equation": ids["e_bal"],
        "ports": [ids["j"]],
    })
    assert r.status_code == 200, r.text
    r = client.put("/api/behaviour/assignment", json={
        "entity_type": _et("diffusion_transport"),
        "sequence": [ids["e_flow"]],
        # no base_equation: stateless transport — otherwise the closure
        # would stamp J as state variable and the scheduler would treat
        # it as integrator output.
        "instantiated": [ids["k"]],
        "ports": [ids["pin"]],
    })
    assert r.status_code == 200, r.text

    r = client.get("/api/instantiate/model", params={"graph": graph})
    assert r.status_code == 200, r.text
    body = r.json()

    # Index element sets.
    assert body["indices"][_idx("idx_node")] == list(body["indices"][_idx("idx_node")])
    assert set(body["indices"][_idx("idx_arc")]) == {
        f"{graph}/ModelArc_a1", f"{graph}/ModelArc_a2"}

    ets = {e["entity_type"]: e for e in body["entity_types"]}
    cap = ets[_et("lumped_capacity")]
    tr = ets[_et("diffusion_transport")]
    assert cap["has_assignment"] and tr["has_assignment"]
    assert len(cap["nodes"]) == 2 and len(tr["nodes"]) == 1
    assert cap["state_variable"] == ids["m"]

    cap_vars = {v["var"]: v for v in cap["variables"]}
    assert cap_vars[ids["f"]]["binding"] == "incidence"
    assert cap_vars[ids["f"]]["matrix"] == _idx("idx_arc_diffusion")
    assert cap_vars[ids["m"]]["indices"][_idx("idx_node")] == cap["nodes"]
    tr_vars = {v["var"]: v for v in tr["variables"]}
    assert tr_vars[ids["k"]]["binding"] == "parameter"
    assert tr_vars[ids["pin"]]["binding"] == "port"

    # Equation sequence preserved.
    assert [e["equation"] for e in cap["equations"]] == [
        ids["e_bal"], ids["e_prop"]]

    # Ports: transport's effort port bound per contact; capacity's
    # flow port bound at the arc element.
    pin_ports = [p for p in body["ports"] if p["var"] == ids["pin"]]
    assert len(pin_ports) == 2
    assert all(p["status"] == "bound" for p in pin_ports)
    assert {p["peer_var"] for p in pin_ports} == {ids["p"]}
    j_ports = [p for p in body["ports"] if p["var"] == ids["j"]]
    assert all(p["status"] == "bound" for p in j_ports)
    assert {p["element"] for p in j_ports} == {
        f"{graph}/ModelArc_a1", f"{graph}/ModelArc_a2"}

    # Incidence matrices ride along.
    assert body["incidence"]["base"]["arcs"] == [
        f"{graph}/ModelArc_a1", f"{graph}/ModelArc_a2"]

    # A closed two-assignment model: no unbound/ambiguous port problems.
    assert not [p for p in body["problems"]
                if p["kind"].endswith("-port")]

    # Schedule: prop → flow → bal, no algebraic loops.
    lvl = {b["equation"]: i
           for i, level in enumerate(body["schedule"]["levels"])
           for b in level}
    assert lvl[ids["e_prop"]] == 0
    assert lvl[ids["e_flow"]] == 1
    assert lvl[ids["e_bal"]] == 2
    assert body["schedule"]["loops"] == []


def test_model_endpoint_requires_graph(client):
    r = client.get("/api/instantiate/model")
    assert r.status_code == 400
