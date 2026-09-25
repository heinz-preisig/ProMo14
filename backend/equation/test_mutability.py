"""Tests for the variable mutability policy (design doc §18).

A variable referenced by an equation keeps units, index structures, tokens,
port status and reference-key names locked.  Role/classifications remain
editable; network remains editable only while references are its own defining
LHS equations.  Surface names and the value slot stay free.  Enforcement lives
in ``backend/equation/service.py`` — POST and PUT both guard, DELETE is blocked
by foreign references.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from backend.core import graph_store
from backend.main import app
from backend.testing import GraphClient


def _iri_path(iri: str) -> str:
    return quote(iri, safe="/:@!$&'()*+,;=-._~")


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
    """Minimal VariableRecord payload; ``tag`` doubles as fragment/id."""
    v = {
        "iri": f"{BASE}#{tag}",
        "label": tag,
        "internal_id": tag,
        "aliases": {"global_ID": tag},
        "network": "root",
        "variable_class": "state",
        "units": [0] * 8,
        "tokens": [],
        "index_structures": [],
        "classifications": {},
        "equations": {},
    }
    v.update(over)
    return v


def _eq(tag: str, lhs_iri: str, rhs: str):
    return {
        "iri": f"{BASE}#{tag}",
        "lhs": lhs_iri,
        "rhs": rhs,
        "network": "root",
    }


def _post(client, var):
    r = client.post("/api/equation/variables", json=var)
    assert r.status_code == 200, r.text
    return r


def _put(client, var):
    return client.put(f"/api/equation/variables/{_iri_path(var['iri'])}",
                      json=var)


# ---------------------------------------------------------------------------
# Structural lock
# ---------------------------------------------------------------------------

def test_structural_edit_blocked_when_referenced(client):
    """Units of a variable used in another equation's rhs → 409."""
    _post(client, _var("V_1", units=[0, 0, 0, 1, 0, 0, 0, 0]))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    r = _put(client, _var("V_1", units=[1, 0, 0, 0, 0, 0, 0, 0]))
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert "units" in detail["locked_fields"]
    assert detail["references"][0]["via"] == "rhs"


def test_surface_edit_free_when_referenced(client):
    """label/doc/latex stay editable on a referenced variable."""
    _post(client, _var("V_1"))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    v = _var("V_1", label="density",
             aliases={"global_ID": "V_1", "latex": "\\rho"},
             doc="mass per volume")
    r = _put(client, v)
    assert r.status_code == 200, r.text


def test_role_edit_allowed_when_referenced(client):
    """Role/classification edits do not change reference resolution."""
    _post(client, _var("V_1"))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    r = _put(client, _var(
        "V_1",
        variable_class="parameter",
        classifications={"axis:function": "term:parameter"},
    ))
    assert r.status_code == 200, r.text


def test_own_equation_allows_role_change(client):
    """A variable's own defining equation does not lock its role."""
    _post(client, _var("V_1", equations={
        "root": _eq("E_1", f"{BASE}#V_1", "2"),
    }))

    r = _put(client, _var("V_1", variable_class="parameter"))
    assert r.status_code == 200, r.text


def test_network_edit_allowed_with_own_equation_only(client):
    """Moving a variable and its own definition together is safe."""
    _post(client, _var("V_1", equations={
        "root": _eq("E_1", f"{BASE}#V_1", "2"),
    }))

    moved = _var("V_1", network="physical", equations={
        "root": {
            **_eq("E_1", f"{BASE}#V_1", "2"),
            "network": "physical",
        },
    })
    r = _put(client, moved)
    assert r.status_code == 200, r.text


def test_network_edit_blocked_with_foreign_reference(client):
    """A domain move could invalidate qualified references elsewhere."""
    _post(client, _var("V_1"))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    r = _put(client, _var("V_1", network="physical"))
    assert r.status_code == 409
    assert "network" in r.json()["detail"]["locked_fields"]


def test_structural_edit_free_when_unused(client):
    """No references → structural fields editable."""
    _post(client, _var("V_1", units=[0, 0, 0, 1, 0, 0, 0, 0]))
    r = _put(client, _var("V_1", units=[1, 0, 0, 0, 0, 0, 0, 0]))
    assert r.status_code == 200, r.text


def test_post_update_path_is_guarded(client):
    """The frontend updates via POST — the guard must hold there too."""
    _post(client, _var("V_1"))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    r = client.post("/api/equation/variables",
                    json=_var("V_1", units=[1, 0, 0, 0, 0, 0, 0, 0]))
    assert r.status_code == 409


def test_token_boundary_no_false_positive(client):
    """``V_1`` in an rhs must not lock ``V_12`` (whole-token match)."""
    _post(client, _var("V_12"))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    r = _put(client, _var("V_12", units=[1, 0, 0, 0, 0, 0, 0, 0]))
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_blocked_by_foreign_reference(client):
    _post(client, _var("V_1"))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    r = client.delete(f"/api/equation/variables/{_iri_path(f'{BASE}#V_1')}")
    assert r.status_code == 409
    assert r.json()["detail"]["references"]


def test_delete_removes_own_equations(client):
    """Own equations go with the variable — and stop referencing others."""
    _post(client, _var("V_1"))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    r = client.delete(f"/api/equation/variables/{_iri_path(f'{BASE}#V_2')}")
    assert r.status_code == 200
    # V_1 is no longer referenced — the orphaned equation must be gone.
    r = client.delete(f"/api/equation/variables/{_iri_path(f'{BASE}#V_1')}")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# References endpoint
# ---------------------------------------------------------------------------

def test_references_endpoint(client):
    _post(client, _var("V_1"))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    r = client.get(
        f"/api/equation/variables/{_iri_path(f'{BASE}#V_1')}/references")
    assert r.status_code == 200
    body = r.json()
    assert body["used"] is True
    assert any(ref["via"] == "rhs" for ref in body["references"])

    r = client.get(
        f"/api/equation/variables/{_iri_path(f'{BASE}#V_2')}/references")
    assert r.json()["used"] is True  # own defining equation
