"""Endpoint regression tests for ``/api/equation/check``.

5396acd added ``*_domain_iri`` fields to ``CheckRequest`` and
``_build_space`` forwarded them to ``CompileSpace.__init__``, which never
accepted the kwargs — every call returned 500.  Unit tests of
``check()`` itself could not catch that drift; these go through HTTP.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, RDFS

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


def test_context_refreshes_rhs_latex_on_alias_edit(client):
    """Stored rhs_latex is a save-time cache — an alias edit on a
    *referenced* variable must re-render the referencing equation in
    /context, not serve the stale symbol."""
    v_a = {"iri": f"{BASE}#V_a", "label": "a", "internal_id": "V_a",
           "aliases": {"global_ID": "V_a"}, "network": "root",
           "units": [0] * 8, "index_structures": [], "equations": {}}
    eq = {"iri": f"{BASE}#E_b", "lhs": f"{BASE}#V_b", "rhs": "sqrt(a)",
          "network": "root"}
    v_b = {"iri": f"{BASE}#V_b", "label": "b", "internal_id": "V_b",
           "aliases": {"global_ID": "V_b"}, "network": "root",
           "units": [0] * 8, "index_structures": [],
           "equations": {"root": eq}}
    for v in (v_a, v_b):
        r = client.post("/api/equation/variables", json=v)
        assert r.status_code == 200, r.text

    # Edit a's latex alias — b's equation references it.
    r = client.post("/api/equation/variables", json={
        **v_a, "aliases": {"global_ID": "V_a", "latex": "\\alpha"}})
    assert r.status_code == 200, r.text

    ctx = client.get("/api/equation/context").json()
    stored_b = next(v for v in ctx["variables"] if v["label"] == "b")
    latex = next(iter(stored_b["equations"].values()))["rhs_latex"]
    assert "\\alpha" in latex


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


@pytest.mark.parametrize("text", ["setPoint - u", "setPoint * u"])
def test_signal_membership_does_not_create_algebra(client, text):
    r = client.post("/api/equation/check", json={
        "text": text,
        "variables": [
            _var("V_s", label="setPoint", tokens=[f"{BASE}#token_signal"],
                 token_vector={"signal": 1}),
            _var("V_u", label="u", tokens=[f"{BASE}#token_signal"],
                 token_vector={}),
        ],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["units"] == [0] * 8
    assert "tokens" not in body
    assert "advisories" not in body


def test_units_still_reject_incompatible_signal_sum(client):
    r = client.post("/api/equation/check", json={
        "text": "a + b",
        "variables": [_var("V_a", label="a"),
                      _var("V_b", label="b", units=[1, 0, 0, 0, 0, 0, 0, 0])],
    })
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["error_kind"] == "UnitError"


def _make_artefact(store, iri="https://w3id.org/promo/library"):
    store.create_artefact_graph(iri, "library", uses=[BASE])
    return iri


def test_save_scoped_to_other_artefact_writes_home(client):
    """A POST scoped to artefact B for a subject homed in A updates
    A's record — it must not shadow-copy into B (the V_10/V_23
    duplicate incident)."""
    LIB = _make_artefact(graph_store.get_store())
    v = {"iri": f"{BASE}#V_home", "label": "h", "internal_id": "V_home",
         "network": "root", "units": [0] * 8, "index_structures": [],
         "equations": {}}
    r = client.post("/api/equation/variables", json=v)
    assert r.status_code == 200, r.text

    r = client.post("/api/equation/variables", json=v,
                    params={"graph": LIB})
    assert r.status_code == 200, r.text

    store = graph_store.get_store()
    s = URIRef(v["iri"])
    assert (s, None, None) in store.graph(BASE)
    assert (s, None, None) not in store.graph(LIB)


def test_delete_targets_named_graph_copy(client):
    """``?graph=`` on DELETE removes only that graph's copy of a
    duplicated subject; deleting the last surviving copy is still
    reference-guarded."""
    LIB = _make_artefact(graph_store.get_store())
    v_dup = {"iri": f"{BASE}#V_dup", "label": "d",
             "internal_id": "V_dup", "network": "root",
             "units": [0] * 8, "index_structures": [], "equations": {}}
    eq = {"iri": f"{BASE}#E_user", "lhs": f"{BASE}#V_user", "rhs": "d",
          "network": "root"}
    v_user = {"iri": f"{BASE}#V_user", "label": "u",
              "internal_id": "V_user", "network": "root",
              "units": [0] * 8, "index_structures": [],
              "equations": {"root": eq}}
    for v in (v_dup, v_user):
        r = client.post("/api/equation/variables", json=v)
        assert r.status_code == 200, r.text
    store = graph_store.get_store()
    s = URIRef(v_dup["iri"])
    store.graph(LIB).add((s, RDF.type, graph_store.PROMO["Variable"]))
    store.graph(LIB).add((s, RDFS.label, Literal("d")))

    # The stray copy goes; the referenced original survives — another
    # editable owner keeps every reference satisfied.
    r = client.delete(
        "/api/equation/variables/" + quote(v_dup["iri"], safe=""),
        params={"graph": LIB})
    assert r.status_code == 200, r.text
    assert (s, None, None) not in store.graph(LIB)
    assert (s, None, None) in store.graph(BASE)

    # Now the ontology copy is the only owner — the guard returns.
    r = client.delete(
        "/api/equation/variables/" + quote(v_dup["iri"], safe=""),
        params={"graph": BASE})
    assert r.status_code == 409
