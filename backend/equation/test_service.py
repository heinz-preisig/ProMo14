"""Endpoint regression tests for ``/api/equation/check``.

5396acd added ``*_domain_iri`` fields to ``CheckRequest`` and
``_build_space`` forwarded them to ``CompileSpace.__init__``, which never
accepted the kwargs — every call returned 500.  Unit tests of
``check()`` itself could not catch that drift; these go through HTTP.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core import graph_store
from backend.main import app
from backend.testing import GraphClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROMO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(graph_store, "_STORE", None)
    with GraphClient(
            app, graph_iri="https://w3id.org/promo/ontology") as c:
        yield c
    monkeypatch.setattr(graph_store, "_STORE", None)


BASE = "https://w3id.org/promo/ontology"


def _var(tag: str, **over):
    v = {"iri": f"{BASE}#{tag}", "label": tag, "network": "root",
         "type": "state"}
    v.update(over)
    return v


def test_check_plain_expression(client):
    r = client.post("/api/equation/check", json={
        "text": "a + b",
        "lhs": "a",
        "variables": [_var("V_a", label="a"), _var("V_b", label="b")],
    })
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_check_instantiate_constant(client):
    """``Instantiate(c)`` with a constant-class LHS declares the value
    slot — incidence stays empty (type-level reference, ADR-008)."""
    r = client.post("/api/equation/check", json={
        "text": "Instantiate(c)",
        "lhs": "c",
        "variables": [_var("V_c", label="c", type="constant")],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["incidence"] == []


def test_check_instantiate_state_var_rejected(client):
    """A state variable may not sit on an Instantiate LHS — the error is
    a proper ``ok: false`` response, not a 500."""
    r = client.post("/api/equation/check", json={
        "text": "Instantiate(c)",
        "lhs": "c",
        "variables": [_var("V_c", label="c", type="state")],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert "constant" in body["error"] or "parameter" in body["error"]


def test_check_token_empty_signature_warns_basis_change(client):
    """§24: an expression collapsing to {} is a basis change, not a
    relation — warn, never block.  `c` (component_mass/mass) times `Mm`
    (mass/component_mass) is token-neutral."""
    r = client.post("/api/equation/check", json={
        "text": "( c . Mm )",
        "lhs": "rho",
        "variables": [
            _var("V_c", label="c",
                 token_vector={"token_component_mass": 1, "token_mass": -1}),
            _var("V_Mm", label="Mm",
                 token_vector={"token_mass": 1, "token_component_mass": -1}),
            _var("V_rho", label="rho"),
        ],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["tokens"] == {}
    assert any("basis change" in w for w in body["warnings"])


def test_check_token_mismatch_warns_vs_declared(client):
    """§24: computed signature differing from the LHS variable's declared
    tokenVector is an advisory."""
    r = client.post("/api/equation/check", json={
        "text": "( m . h )",
        "lhs": "e_dot",
        "variables": [
            _var("V_m", label="m",
                 token_vector={"token_mass": 1, "token_time": -1}),
            _var("V_h", label="h",
                 token_vector={"token_energy": 1, "token_mass": -1}),
            _var("V_e_dot", label="e_dot",
                 token_vector={"token_energy": 1, "token_entropy": -1}),
        ],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["tokens"] == {"token_energy": 1, "token_time": -1}
    assert body["tokens_pretty"] == "energy time^-1"
    assert any("does not match the declared" in w for w in body["warnings"])


def test_check_token_matching_declared_no_warning(client):
    """No advisory when the computed signature equals the declaration."""
    r = client.post("/api/equation/check", json={
        "text": "( m . h )",
        "lhs": "e_dot",
        "variables": [
            _var("V_m", label="m",
                 token_vector={"token_mass": 1, "token_time": -1}),
            _var("V_h", label="h",
                 token_vector={"token_energy": 1, "token_mass": -1}),
            _var("V_e_dot", label="e_dot",
                 token_vector={"token_energy": 1, "token_time": -1}),
        ],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["warnings"] == []
