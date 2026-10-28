"""Tests for the behaviour-linker closure engine and endpoints.

The engine tests exercise the §8/§12/§13 mechanics directly on plain
dicts; the endpoint tests run the FastAPI app against a throwaway
``PROMO_DATA_DIR`` store.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.behaviour.closure import (
    EquationInfo,
    Selection,
    apply_move,
    evaluate,
)
from backend.core import graph_store
from backend.main import app
from backend.testing import GraphClient


# ---------------------------------------------------------------------------
# Engine fixtures
# ---------------------------------------------------------------------------

def _eq(iri: str, lhs: str, incidence=()) -> EquationInfo:
    return EquationInfo(iri=iri, lhs=lhs, incidence=list(incidence))


def _graph(*eqs: EquationInfo) -> dict:
    return {e.iri: e for e in eqs}


# A small capacity-like behaviour:
#   E1: s  := f(x, p)      base/state equation
#   E2: x  := g(s, q)      property law feeding back on state (allowed)
#   p, q are endpoints (instantiated / port)
CHAIN = _graph(
    _eq("E1", "s", ["x", "p"]),
    _eq("E2", "x", ["s", "q"]),
)


# ---------------------------------------------------------------------------
# Engine: resolution & closure
# ---------------------------------------------------------------------------

def test_empty_selection_is_not_closed():
    report = evaluate(CHAIN, Selection())
    assert not report.closed
    assert report.state_variable is None
    assert report.unresolved == []


def test_base_equation_exposes_its_inputs():
    report = evaluate(CHAIN, Selection(sequence=["E1"], base_equation="E1"))
    assert report.state_variable == "s"
    assert {u.variable for u in report.unresolved} == {"x", "p"}
    # x has a candidate equation; p has none (endpoint-only variable)
    assert report.unresolved[0].candidates == ["E2"]
    assert report.unresolved[1].candidates == []
    assert not report.closed


def test_closed_chain_with_state_feedback():
    """E2 feeds back on the state variable — the one allowed cycle.
    The base equation is now the last step in the sequence."""
    report = evaluate(CHAIN, Selection(
        sequence=["E2", "E1"], base_equation="E1",
        instantiated={"p"}, ports={"q"}))
    assert report.unresolved == []
    assert report.cycles == []
    assert report.conflicts == []
    assert report.order_violations == []
    assert report.closed


def test_unwanted_cycle_is_reported():
    graph = _graph(
        _eq("E1", "s", ["x"]),
        _eq("E2", "x", ["y"]),
        _eq("E3", "y", ["x"]),      # x <-> y cycle not through state
    )
    report = evaluate(graph, Selection(
        sequence=["E2", "E3", "E1"], base_equation="E1"))
    assert report.cycles, "expected an unwanted cycle"
    assert not report.closed


def test_stateless_selection_has_no_state_variable():
    """Transport-style entity: acyclic subgraph, no base equation.
    With no integrator exemption the sequence is pure dependency
    order — the defining equation precedes its consumer.  §21: the
    tip variable must be declared an output for the assignment to
    close (a stateless entity's outputs are its interface)."""
    graph = _graph(_eq("E1", "f", ["a"]), _eq("E2", "a", []))
    report = evaluate(graph, Selection(sequence=["E2", "E1"]))
    assert report.state_variable is None
    assert report.unconsumed == ["f"]
    assert not report.closed
    report = evaluate(graph, Selection(
        sequence=["E2", "E1"], outputs={"f"}))
    assert report.closed


# ---------------------------------------------------------------------------
# Engine: frontier suggestions
# ---------------------------------------------------------------------------

def test_frontier_suggests_reachable_resolver():
    """The frontier lists equations that resolve an open variable and are
    reachable from the selected base cone."""
    report = evaluate(CHAIN, Selection(sequence=["E1"], base_equation="E1"))
    assert report.frontier == ["E2"]


def test_frontier_empty_when_closed():
    report = evaluate(CHAIN, Selection(
        sequence=["E2", "E1"], base_equation="E1",
        instantiated={"p"}, ports={"q"}))
    assert report.frontier == []
    assert report.closed


def test_frontier_reachable_from_stateless_sequence():
    graph = _graph(_eq("E1", "f", ["a"]), _eq("E2", "a", []))
    report = evaluate(graph, Selection(sequence=["E1"]))
    assert report.frontier == ["E2"]


# ---------------------------------------------------------------------------
# Engine: conflicts & ordering
# ---------------------------------------------------------------------------

def test_duplicate_definition_conflict():
    graph = _graph(_eq("E1", "s"), _eq("E2", "s"), _eq("E3", "s"))
    report = evaluate(graph, Selection(
        sequence=["E2", "E1"], base_equation="E1"))
    kinds = [c.kind for c in report.conflicts]
    assert "duplicate_definition" in kinds
    assert not report.closed


def test_role_conflicts():
    graph = _graph(_eq("E1", "s", ["x"]), _eq("E2", "x"))
    report = evaluate(graph, Selection(
        sequence=["E2", "E1"], base_equation="E1",
        instantiated={"x"}, ports={"x", "z"}))
    kinds = {c.kind for c in report.conflicts}
    assert "defined_and_instantiated" in kinds
    assert "defined_and_port" in kinds
    assert "instantiated_and_port" in kinds   # x is in both sets


def test_order_violation_late_dependency():
    """E2 consumes x before the equation defining it — not lower-
    triangular."""
    graph = _graph(
        _eq("E1", "s", ["y"]),
        _eq("E2", "y", ["x"]),
        _eq("E3", "x"),
    )
    report = evaluate(graph, Selection(
        sequence=["E2", "E3", "E1"], base_equation="E1"))
    assert report.order_violations
    assert report.order_violations[0].equation == "E2"
    assert report.order_violations[0].defined_by == "E3"
    assert not report.closed


def test_any_base_equation_yields_state_variable():
    """A base equation's LHS is always the privileged cycle variable,
    independent of ontology class."""
    graph = _graph(
        EquationInfo(iri="E1", lhs="a", lhs_class="generic",
                     incidence=["b"]),
        EquationInfo(iri="E2", lhs="b", lhs_class="generic",
                     incidence=[]),
    )
    report = evaluate(graph, Selection(
        sequence=["E2", "E1"], base_equation="E1"))
    assert report.state_variable == "a"
    assert report.cycles == []
    assert report.closed


def test_base_equation_must_close_sequence():
    report = evaluate(CHAIN, Selection(
        sequence=["E1", "E2"], base_equation="E1",
        instantiated={"p"}, ports={"q"}))
    assert any(v.equation == "E1" for v in report.order_violations)


def test_unknown_equation_conflict():
    report = evaluate(CHAIN, Selection(sequence=["E1", "ZZZ"],
                                       base_equation="E1"))
    assert any(c.kind == "unknown_equation" for c in report.conflicts)


def test_unused_port_warns():
    report = evaluate(CHAIN, Selection(
        sequence=["E2", "E1"], base_equation="E1",
        instantiated={"p"}, ports={"q", "unused"}))
    assert any("unused" in w for w in report.warnings)
    assert report.closed          # warnings do not block closure


def test_unreferenced_instantiated_no_warning():
    """An instantiated mark with no internal reference is a legitimate
    interface declaration (bound value provided outward), not a hint."""
    report = evaluate(CHAIN, Selection(
        sequence=["E2", "E1"], base_equation="E1",
        instantiated={"p", "provided"}, ports={"q"}))
    assert not any("provided" in w for w in report.warnings)
    assert report.closed


def test_unreachable_equation_warns():
    """Evaluate-only view of an unmoved selection: an equation outside
    every root cone warns and blocks closure (§21 dead code)."""
    graph = _graph(
        _eq("E1", "s", ["p"]),
        _eq("E9", "other"),        # disconnected from the base cone
    )
    report = evaluate(graph, Selection(
        sequence=["E9", "E1"], base_equation="E1", instantiated={"p"}))
    assert any("E9" in w for w in report.warnings)
    assert report.unconsumed == ["other"]
    assert not report.closed


# ---------------------------------------------------------------------------
# Engine: auto-instantiated endpoints (constant/parameter class, bound value)
# ---------------------------------------------------------------------------

def test_auto_instantiated_resolves_without_marking():
    """A bound-value variable terminates the search on its own."""
    report = evaluate(CHAIN, Selection(
        sequence=["E2", "E1"], base_equation="E1",
        ports={"q"}),
        auto_instantiated={"p"})
    assert report.unresolved == []
    assert [u.variable for u in report.auto_instantiated] == ["p"]
    assert report.closed


def test_auto_instantiated_offers_override_candidates():
    """The hint is overridable — candidate equations are still listed."""
    graph = _graph(
        _eq("E1", "s", ["p"]),
        _eq("E2", "p"),            # could define the constant anyway
    )
    report = evaluate(graph, Selection(
        sequence=["E1"], base_equation="E1"),
        auto_instantiated={"p"})
    assert report.unresolved == []
    assert report.auto_instantiated[0].candidates == ["E2"]
    assert report.closed


def test_auto_instantiated_overridden_by_equation():
    """Selecting a defining equation wins over the class hint."""
    graph = _graph(
        _eq("E1", "s", ["p"]),
        _eq("E2", "p"),
    )
    report = evaluate(graph, Selection(
        sequence=["E2", "E1"], base_equation="E1"),
        auto_instantiated={"p"})
    assert report.auto_instantiated == []
    assert report.defined["p"] == "E2"
    assert report.closed


def test_auto_instantiated_overridden_by_port():
    """An explicit port declaration wins over the class hint."""
    report = evaluate(CHAIN, Selection(
        sequence=["E2", "E1"], base_equation="E1",
        ports={"p", "q"}),
        auto_instantiated={"p"})
    assert report.auto_instantiated == []
    assert report.unresolved == []
    assert report.closed


def test_auto_instantiated_unreferenced_not_listed():
    """Auto vars the selection never touches stay out of the report."""
    report = evaluate(CHAIN, Selection(
        sequence=["E2", "E1"], base_equation="E1",
        instantiated={"p"}, ports={"q"}),
        auto_instantiated={"p", "other_const"})
    assert [u.variable for u in report.auto_instantiated] == []
    assert report.closed


# ---------------------------------------------------------------------------
# Engine: §21 moves — every gesture is a re-closure
# ---------------------------------------------------------------------------

def _moved(graph, sel, **kw):
    return apply_move(graph, sel, **kw)["selection"]


def test_move_pick_base_then_pick_closes_chain():
    sel = _moved(CHAIN, Selection(), kind="pick_base", equation="E1")
    assert sel.base_equation == "E1"
    sel = _moved(CHAIN, sel, kind="pick", variable="x", equation="E2")
    sel = _moved(CHAIN, sel, kind="mark", variable="p",
                 role="instantiated")
    sel = _moved(CHAIN, sel, kind="mark", variable="q", role="ports")
    report = evaluate(CHAIN, sel)
    assert sel.sequence == ["E2", "E1"]       # ordered, base last
    assert report.closed


def test_move_pick_pulls_unique_definers():
    """p's only definer is pulled in automatically; x (two candidates)
    and q (none) stay open."""
    graph = _graph(
        _eq("E1", "s", ["x", "p", "q"]),
        _eq("E2", "x", ["s"]),
        _eq("E2b", "x"),
        _eq("E3", "p"),                        # unique definer of p
    )
    sel = _moved(graph, Selection(), kind="pick_base", equation="E1")
    sel = _moved(graph, sel, kind="pick", variable="x", equation="E2")
    assert "E3" in sel.sequence               # auto-pulled
    report = evaluate(graph, sel)
    assert {u.variable for u in report.unresolved} == {"q"}


def test_move_delete_cascades_exclusive_cone():
    """Deleting E2 drops its exclusive provider E3; x reopens."""
    graph = _graph(
        _eq("E1", "s", ["x", "p"]),
        _eq("E2", "x", ["s", "q"]),
        _eq("E3", "q"),                        # only feeds E2
    )
    sel = _moved(graph, Selection(), kind="pick_base", equation="E1")
    sel = _moved(graph, sel, kind="pick", variable="x", equation="E2")
    sel = _moved(graph, sel, kind="mark", variable="p",
                 role="instantiated")
    assert set(sel.sequence) == {"E1", "E2", "E3"}
    sel = _moved(graph, sel, kind="delete", equation="E2")
    assert sel.sequence == ["E1"]             # E3 pruned with E2's cone
    report = evaluate(graph, sel)
    assert {u.variable for u in report.unresolved} == {"x"}


def test_move_pick_exchanges_definer():
    """Picking a different equation for an already-defined variable
    swaps it and prunes the displaced cone."""
    graph = _graph(
        _eq("E1", "s", ["x", "p"]),
        _eq("E2", "x", ["s", "q"]),
        _eq("E2b", "x", ["p"]),                # alternative definer
        _eq("E3", "q"),
    )
    sel = _moved(graph, Selection(), kind="pick_base", equation="E1")
    sel = _moved(graph, sel, kind="pick", variable="x", equation="E2")
    sel = _moved(graph, sel, kind="pick", variable="x", equation="E2b")
    assert "E2" not in sel.sequence and "E2b" in sel.sequence
    assert "E3" not in sel.sequence           # exclusive cone pruned


def test_move_mark_endpoint_drops_definer():
    """Marking a defined variable instantiated/port ends its
    computation — the definer and its exclusive cone prune."""
    graph = _graph(
        _eq("E1", "s", ["x", "p"]),
        _eq("E2", "x", ["s", "q"]),
        _eq("E3", "q"),
    )
    sel = _moved(graph, Selection(), kind="pick_base", equation="E1")
    sel = _moved(graph, sel, kind="pick", variable="x", equation="E2")
    sel = _moved(graph, sel, kind="mark", variable="x",
                 role="instantiated")
    assert "E2" not in sel.sequence and "E3" not in sel.sequence
    assert "x" in sel.instantiated


def test_move_unpick_base_surfaces_cycle():
    """Removing the state endpoint leaves the integrator loop as an
    ordinary cycle — kept, reported, not silently wiped."""
    sel = _moved(CHAIN, Selection(
        sequence=["E2", "E1"], base_equation="E1"),
        kind="pick_base", equation=None)
    assert sel.base_equation is None
    assert set(sel.sequence) == {"E1", "E2"}
    report = evaluate(CHAIN, sel)
    assert report.cycles
    assert not report.closed


def test_move_reorder_yields_legal_order():
    """A desired permutation is a position hint; the engine emits the
    closest lower-triangular order."""
    graph = _graph(
        _eq("E1", "s", ["y"]),
        _eq("E2", "y", ["x"]),
        _eq("E3", "x"),
    )
    sel = _moved(graph, Selection(
        sequence=["E2", "E3", "E1"], base_equation="E1"),
        kind="reorder", sequence=["E2", "E3", "E1"])
    assert sel.sequence == ["E3", "E2", "E1"]


def test_move_output_demands_definer():
    """An output mark on an undefined variable opens a demand; the
    picker offers its definers and picking one closes it."""
    graph = _graph(
        _eq("E1", "f", ["a"]),
        _eq("E1b", "f", ["b"]),               # second definer — no pull
        _eq("E2", "a", []),
        _eq("E3", "b", []),
    )
    sel = _moved(graph, Selection(), kind="mark", variable="f",
                 role="outputs")
    report = evaluate(graph, sel)
    assert [u.variable for u in report.unresolved] == ["f"]
    assert report.unresolved[0].as_output
    assert sorted(report.frontier) == ["E1", "E1b"]
    sel = _moved(graph, sel, kind="pick", variable="f", equation="E1")
    report = evaluate(graph, sel)
    assert report.closed                      # E2 auto-pulled
    assert sel.sequence == ["E2", "E1"]


def test_move_output_mark_auto_pulls_unique_cone():
    """With a unique definer chain the mark alone closes the entity —
    there is no choice to offer."""
    graph = _graph(_eq("E1", "f", ["a"]), _eq("E2", "a", []))
    sel = _moved(graph, Selection(), kind="mark", variable="f",
                 role="outputs")
    assert sel.sequence == ["E2", "E1"]
    assert evaluate(graph, sel).closed


def test_move_output_roots_cone():
    """An equation needed only by an output survives — outputs are
    reachability roots alongside the base cone."""
    graph = _graph(
        _eq("E1", "s", ["x", "p"]),
        _eq("E2", "x", ["s", "q"]),
        _eq("E4", "m", ["s"]),                  # measurement off state
    )
    sel = _moved(graph, Selection(), kind="pick_base", equation="E1")
    sel = _moved(graph, sel, kind="pick", variable="x", equation="E2")
    sel = _moved(graph, sel, kind="mark", variable="p",
                 role="instantiated")
    sel = _moved(graph, sel, kind="mark", variable="q", role="ports")
    sel = _moved(graph, sel, kind="mark", variable="m",
                 role="outputs")
    sel = _moved(graph, sel, kind="pick", variable="m", equation="E4")
    report = evaluate(graph, sel)
    assert "E4" in sel.sequence
    assert report.closed


def test_move_unmark_output_prunes_cone():
    """Unmarking the only root of a based side-cone prunes it (§21:
    unreachable is a transient)."""
    graph = _graph(
        _eq("E1", "s", ["x", "p"]),
        _eq("E2", "x", ["s", "q"]),
        _eq("E4", "m", ["s"]),
    )
    sel = _moved(graph, Selection(
        sequence=["E4", "E2", "E1"], base_equation="E1",
        instantiated={"p"}, ports={"q"}, outputs={"m"}),
        kind="unmark", variable="m")
    assert "E4" not in sel.sequence


def test_move_mark_output_exclusive():
    """Output marking clears instantiated/port marks on the variable."""
    sel = _moved(CHAIN, Selection(
        sequence=["E2", "E1"], base_equation="E1",
        instantiated={"p", "x"}, ports={"q"}),
        kind="mark", variable="x", role="outputs")
    assert "x" in sel.outputs and "x" not in sel.instantiated


# ---------------------------------------------------------------------------
# Endpoint tests (real store in a throwaway data dir)
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROMO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(graph_store, "_STORE", None)
    with GraphClient(
            app, graph_iri="https://w3id.org/promo/ontology") as c:
        yield c
    monkeypatch.setattr(graph_store, "_STORE", None)


def _seed_vars():
    """Two variables + equations in the working ontology graph."""
    store = graph_store.get_store()
    g = store.ontology_graph
    store.add_variable_dict(g, {
        "iri": "https://w3id.org/promo/ontology#var_s",
        "label": "s", "network": "physical", "variable_class": "state",
        "equations": {"E_1": {
            "iri": "https://w3id.org/promo/ontology#eq_E1",
            "internal_id": "E_1", "rhs": "x",
            "incidence_list": ["https://w3id.org/promo/ontology#var_x"],
        }},
    })
    store.add_variable_dict(g, {
        "iri": "https://w3id.org/promo/ontology#var_x",
        "label": "x", "network": "physical", "variable_class": "state",
        "equations": {"E_2": {
            "iri": "https://w3id.org/promo/ontology#eq_E2",
            "internal_id": "E_2", "rhs": "s",
            "incidence_list": ["https://w3id.org/promo/ontology#var_s"],
        }},
    })
    return store


def test_context_endpoint_lists_entity_types_and_equations(client):
    _seed_vars()
    r = client.get("/api/behaviour/context")
    assert r.status_code == 200
    body = r.json()
    assert any(et["label"] == "Lumped" for et in body["entity_types"])
    eq_iris = {e["iri"] for e in body["equations"]}
    assert "https://w3id.org/promo/ontology#eq_E1" in eq_iris
    var_iris = {v["iri"] for v in body["variables"]}
    assert "https://w3id.org/promo/ontology#var_s" in var_iris


def test_evaluate_endpoint(client):
    _seed_vars()
    r = client.post("/api/behaviour/evaluate", json={
        "entity_type": "https://w3id.org/promo/ontology#Lumped",
        "sequence": ["https://w3id.org/promo/ontology#eq_E2",
                     "https://w3id.org/promo/ontology#eq_E1"],
        "base_equation": "https://w3id.org/promo/ontology#eq_E1",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["closed"]
    assert body["state_variable"].endswith("#var_s")
    assert body["labels"]["https://w3id.org/promo/ontology#var_x"] == "x"


def test_assignment_roundtrip(client):
    _seed_vars()
    et = "https://w3id.org/promo/ontology#Lumped"
    payload = {
        "entity_type": et,
        "sequence": ["https://w3id.org/promo/ontology#eq_E2",
                     "https://w3id.org/promo/ontology#eq_E1"],
        "base_equation": "https://w3id.org/promo/ontology#eq_E1",
        "instantiated": [],
        "ports": [],
    }
    r = client.put("/api/behaviour/assignment", json=payload)
    assert r.status_code == 200
    assert r.json()["closed"]

    r = client.get("/api/behaviour/assignment",
                   params={"entity_type": et,
                           "graph": "https://w3id.org/promo/ontology"})
    assert r.status_code == 200
    body = r.json()
    assert body["sequence"] == payload["sequence"]
    assert body["base_equation"] == payload["base_equation"]
    assert body["state_variable"].endswith("#var_s")
    assert body["closed"]

    r = client.delete("/api/behaviour/assignment",
                      params={"entity_type": et,
                           "graph": "https://w3id.org/promo/ontology"})
    assert r.status_code == 204
    r = client.get("/api/behaviour/assignment",
                   params={"entity_type": et,
                           "graph": "https://w3id.org/promo/ontology"})
    assert r.status_code == 404


def test_assignment_update_replaces_sequence(client):
    """A second PUT must not leave orphaned rdf:List cells behind."""
    _seed_vars()
    et = "https://w3id.org/promo/ontology#Lumped"
    base = "https://w3id.org/promo/ontology#eq_E1"
    client.put("/api/behaviour/assignment", json={
        "entity_type": et, "sequence": [base], "base_equation": base})
    r = client.put("/api/behaviour/assignment", json={
        "entity_type": et,
        "sequence": ["https://w3id.org/promo/ontology#eq_E2", base],
        "base_equation": base})
    assert r.json()["closed"]
    r = client.get("/api/behaviour/assignment",
                   params={"entity_type": et,
                           "graph": "https://w3id.org/promo/ontology"})
    assert len(r.json()["sequence"]) == 2


def test_move_endpoint_recloses(client):
    """The /move channel returns the re-closed selection + report."""
    _seed_vars()
    et = "https://w3id.org/promo/ontology#Lumped"
    base = "https://w3id.org/promo/ontology#eq_E1"
    r = client.post("/api/behaviour/move", json={
        "entity_type": et, "kind": "pick_base", "equation": base})
    assert r.status_code == 200
    body = r.json()
    sel = body["selection"]
    assert sel["base_equation"] == base
    assert body["report"]["state_variable"].endswith("#var_s")
    # Pick the definer for x — auto order places it before the base.
    r = client.post("/api/behaviour/move", json={
        "entity_type": et, "kind": "pick",
        "variable": "https://w3id.org/promo/ontology#var_x",
        "equation": "https://w3id.org/promo/ontology#eq_E2",
        "sequence": sel["sequence"], "base_equation": base})
    assert r.status_code == 200
    body = r.json()
    assert body["selection"]["sequence"] == [
        "https://w3id.org/promo/ontology#eq_E2", base]
    assert body["report"]["closed"]


def test_assignment_outputs_roundtrip(client):
    """promo:hasOutputVariable persists on the artefact (§21)."""
    _seed_vars()
    et = "https://w3id.org/promo/ontology#Lumped"
    base = "https://w3id.org/promo/ontology#eq_E1"
    var_x = "https://w3id.org/promo/ontology#var_x"
    r = client.put("/api/behaviour/assignment", json={
        "entity_type": et,
        "sequence": ["https://w3id.org/promo/ontology#eq_E2", base],
        "base_equation": base,
        "outputs": [var_x]})
    assert r.status_code == 200
    assert r.json()["outputs"] == [var_x]
    r = client.get("/api/behaviour/assignment",
                   params={"entity_type": et,
                           "graph": "https://w3id.org/promo/ontology"})
    assert r.json()["outputs"] == [var_x]
