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
    evaluate,
)
from backend.core import graph_store
from backend.main import app


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
    """E2 feeds back on the state variable — the one allowed cycle."""
    report = evaluate(CHAIN, Selection(
        sequence=["E1", "E2"], base_equation="E1",
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
        sequence=["E1", "E2", "E3"], base_equation="E1"))
    assert report.cycles, "expected an unwanted cycle"
    assert not report.closed


def test_stateless_selection_has_no_state_variable():
    """Transport-style entity: acyclic subgraph, no base equation.
    With no integrator exemption the sequence is pure dependency
    order — the defining equation precedes its consumer."""
    graph = _graph(_eq("E1", "f", ["a"]), _eq("E2", "a", []))
    report = evaluate(graph, Selection(sequence=["E2", "E1"]))
    assert report.state_variable is None
    assert report.closed


# ---------------------------------------------------------------------------
# Engine: conflicts & ordering
# ---------------------------------------------------------------------------

def test_duplicate_definition_conflict():
    graph = _graph(_eq("E1", "s"), _eq("E2", "s"), _eq("E3", "s"))
    report = evaluate(graph, Selection(
        sequence=["E1", "E2"], base_equation="E1"))
    kinds = [c.kind for c in report.conflicts]
    assert "duplicate_definition" in kinds
    assert not report.closed


def test_role_conflicts():
    graph = _graph(_eq("E1", "s", ["x"]), _eq("E2", "x"))
    report = evaluate(graph, Selection(
        sequence=["E1", "E2"], base_equation="E1",
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
        sequence=["E1", "E2", "E3"], base_equation="E1"))
    assert report.order_violations
    assert report.order_violations[0].equation == "E2"
    assert report.order_violations[0].defined_by == "E3"
    assert not report.closed


def test_base_equation_must_head_sequence():
    report = evaluate(CHAIN, Selection(
        sequence=["E2", "E1"], base_equation="E1",
        instantiated={"p"}, ports={"q"}))
    assert any(v.equation == "E1" for v in report.order_violations)


def test_unknown_equation_conflict():
    report = evaluate(CHAIN, Selection(sequence=["E1", "ZZZ"],
                                       base_equation="E1"))
    assert any(c.kind == "unknown_equation" for c in report.conflicts)


def test_unused_marking_warns():
    report = evaluate(CHAIN, Selection(
        sequence=["E1", "E2"], base_equation="E1",
        instantiated={"p", "unused"}, ports={"q"}))
    assert any("unused" in w for w in report.warnings)
    assert report.closed          # warnings do not block closure


def test_unreachable_equation_warns():
    graph = _graph(
        _eq("E1", "s", ["p"]),
        _eq("E9", "other"),        # disconnected from the base cone
    )
    report = evaluate(graph, Selection(
        sequence=["E1", "E9"], base_equation="E1", instantiated={"p"}))
    assert any("E9" in w for w in report.warnings)
    assert report.closed


# ---------------------------------------------------------------------------
# Endpoint tests (real store in a throwaway data dir)
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROMO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(graph_store, "_STORE", None)
    with TestClient(app) as c:
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
        "sequence": ["https://w3id.org/promo/ontology#eq_E1",
                     "https://w3id.org/promo/ontology#eq_E2"],
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
        "sequence": ["https://w3id.org/promo/ontology#eq_E1",
                     "https://w3id.org/promo/ontology#eq_E2"],
        "base_equation": "https://w3id.org/promo/ontology#eq_E1",
        "instantiated": [],
        "ports": [],
    }
    r = client.put("/api/behaviour/assignment", json=payload)
    assert r.status_code == 200
    assert r.json()["closed"]

    r = client.get("/api/behaviour/assignment",
                   params={"entity_type": et})
    assert r.status_code == 200
    body = r.json()
    assert body["sequence"] == payload["sequence"]
    assert body["base_equation"] == payload["base_equation"]
    assert body["state_variable"].endswith("#var_s")
    assert body["closed"]

    r = client.delete("/api/behaviour/assignment",
                      params={"entity_type": et})
    assert r.status_code == 204
    r = client.get("/api/behaviour/assignment",
                   params={"entity_type": et})
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
        "sequence": [base, "https://w3id.org/promo/ontology#eq_E2"],
        "base_equation": base})
    assert r.json()["closed"]
    r = client.get("/api/behaviour/assignment",
                   params={"entity_type": et})
    assert len(r.json()["sequence"]) == 2
