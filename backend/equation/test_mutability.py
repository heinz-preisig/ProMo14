"""Tests for the variable mutability policy (design doc §18).

A variable referenced by an equation keeps units, index structures, token
*membership* (carriesToken — licensing is a real consumer), port status and
reference-key names locked.  The token *signature* (tokenVector) is exempt
(ruled 2026-11-11): it feeds only advisories, so signature-only edits are the
sanctioned fix path for token advisories.  Role/classifications remain
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

from rdflib import Literal, URIRef

from backend.core import graph_store
from backend.core.graph_store import PROMO
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
        classifications={"axis:function": "term:parameter"},
    ))
    assert r.status_code == 200, r.text


def test_own_equation_allows_role_change(client):
    """A variable's own defining equation does not lock its role."""
    _post(client, _var("V_1", equations={
        "root": _eq("E_1", f"{BASE}#V_1", "2"),
    }))

    r = _put(client, _var(
        "V_1", classifications={"axis:function": "term:parameter"}))
    assert r.status_code == 200, r.text


def test_network_edit_qualifies_foreign_reference(client):
    """A domain move preserves editable references with qualification."""
    _post(client, _var("V_1"))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 + V_1"),
    }))

    r = _put(client, _var("V_1", network="physical"))
    assert r.status_code == 200, r.text
    context = client.get("/api/equation/context").json()
    equations = [
        equation
        for owner in context["variables"]
        if owner["internal_id"] == "V_2"
        for equation in owner["equations"].values()
    ]
    assert equations
    assert equations[0]["rhs"] == "( physical!V_1 + physical!V_1 )"


def test_canonical_rhs_is_persisted_and_authoritative(client):
    """A checked RHS stores its semantic tree; stale literal text is ignored."""
    _post(client, _var("V_1"))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 + V_1"),
    }))

    graph = graph_store.get_store().ontology_graph
    equation = URIRef(f"{BASE}#E_1")
    canonical = graph.value(equation, PROMO["rhsExpression"])
    assert canonical is not None

    graph.set((equation, PROMO["rhs"], Literal("stale source")))
    context = client.get("/api/equation/context").json()
    equations = [
        item
        for owner in context["variables"]
        if owner["internal_id"] == "V_2"
        for item in owner["equations"].values()
    ]
    assert equations[0]["rhs"] == "( V_1 + V_1 )"


def test_network_edit_blocks_cross_graph_reference(client):
    """A domain move blocks references from other graphs."""
    _post(client, _var("V_1"))
    _post(client, _var("V_2", equations={
        "other": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    r = _put(client, _var("V_1", network="physical"))
    assert r.status_code == 409
    assert "network" in r.json()["detail"]["locked_fields"]


def test_structural_edit_free_when_unused(client):
    """No references → structural fields editable."""
    _post(client, _var("V_1", units=[0, 0, 0, 1, 0, 0, 0, 0]))
    r = _put(client, _var("V_1", units=[1, 0, 0, 0, 0, 0, 0, 0]))
    assert r.status_code == 200, r.text


def test_own_equation_does_not_lock_signature(client):
    """A variable used only by its own defining equation(s) is not
    *used* in the §18 sense — its signature may be redefined (ruled
    2026-11-11).  Rewriting the equation is precisely how a signature
    change is expressed."""
    _post(client, _var("V_1", units=[0, 0, 0, 1, 0, 0, 0, 0], equations={
        "root": _eq("E_1", f"{BASE}#V_1", "2"),
    }))
    r = _put(client, _var("V_1", units=[1, 0, 0, 0, 0, 0, 0, 0]))
    assert r.status_code == 200, r.text


def test_own_and_foreign_refs_still_lock(client):
    """Mixed case: own defining equation + a foreign rhs use → locked."""
    _post(client, _var("V_1", units=[0, 0, 0, 1, 0, 0, 0, 0], equations={
        "root": _eq("E_1", f"{BASE}#V_1", "2"),
    }))
    _post(client, _var("V_2", equations={
        "root": _eq("E_2", f"{BASE}#V_2", "V_1 * 2"),
    }))
    r = _put(client, _var("V_1", units=[1, 0, 0, 0, 0, 0, 0, 0]))
    assert r.status_code == 409
    assert "units" in r.json()["detail"]["locked_fields"]


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


def test_invalid_latex_alias_rejected_before_save(client):
    variable = _var("V_1", aliases={"latex": r"\hat{n}_{conv"})
    response = client.post("/api/equation/variables", json=variable)
    assert response.status_code == 422
    assert response.json()["detail"]["field"] == "aliases.latex"
    context = client.get("/api/equation/context").json()
    assert all(item["iri"] != variable["iri"] for item in context["variables"])


def test_supported_latex_alias_forms_accepted(client):
    response = client.post("/api/equation/variables", json=_var(
        "V_1",
        aliases={"latex": r"{{\tilde{n}_conv}}"},
        index_structures=[],
    ))
    assert response.status_code == 200, response.text


def test_duplicate_variable_indices_rejected(client):
    index = "https://w3id.org/promo#index_N"
    response = client.post(
        "/api/equation/variables",
        json=_var("V_dup", port_variable=True, index_structures=[index, index]),
    )
    assert response.status_code == 422
    assert "must not repeat" in response.text


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
# Cascade delete (brutal mode)
# ---------------------------------------------------------------------------

def _context_iris(client):
    context = client.get("/api/equation/context").json()
    return {v["iri"] for v in context["variables"]}


def test_cascade_delete_removes_dependents(client):
    """?cascade=true removes the variable, its equations, and every
    dependent variable+equation in the cone — the brutal delete."""
    _post(client, _var("V_1"))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))
    _post(client, _var("V_3", equations={
        "root": _eq("E_2", f"{BASE}#V_3", "V_2 + 1"),
    }))

    r = client.delete(
        f"/api/equation/variables/{_iri_path(f'{BASE}#V_1')}"
        "?cascade=true")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["deleted"] == f"{BASE}#V_1"
    assert f"{BASE}#V_2" in body["cascade"]
    assert f"{BASE}#V_3" in body["cascade"]

    remaining = _context_iris(client)
    assert not {f"{BASE}#V_1", f"{BASE}#V_2", f"{BASE}#V_3"} & remaining


def test_cascade_delete_unrelated_variables_survive(client):
    _post(client, _var("V_1"))
    _post(client, _var("V_9"))

    r = client.delete(
        f"/api/equation/variables/{_iri_path(f'{BASE}#V_1')}"
        "?cascade=true")
    assert r.status_code == 200, r.text
    assert f"{BASE}#V_9" in _context_iris(client)


# ---------------------------------------------------------------------------
# Freeze (proven variables)
# ---------------------------------------------------------------------------

def test_frozen_blocks_edit_and_delete(client):
    """promo:frozen 409s structural edits and deletes until unfrozen."""
    _post(client, _var("V_1", frozen=True))

    r = _put(client, _var("V_1", doc="new doc", frozen=True))
    assert r.status_code == 409
    assert r.json()["detail"]["frozen"] is True

    r = client.delete(f"/api/equation/variables/{_iri_path(f'{BASE}#V_1')}")
    assert r.status_code == 409
    assert r.json()["detail"]["frozen"] is True

    r = client.delete(
        f"/api/equation/variables/{_iri_path(f'{BASE}#V_1')}"
        "?cascade=true")
    assert r.status_code == 409

    # Unfreeze → edits and delete work again.
    r = _put(client, _var("V_1", doc="new doc", frozen=False))
    assert r.status_code == 200, r.text
    r = client.delete(f"/api/equation/variables/{_iri_path(f'{BASE}#V_1')}")
    assert r.status_code == 200, r.text


def test_frozen_dependent_blocks_cascade(client):
    """A frozen variable inside the cone halts the whole cascade —
    nothing is deleted."""
    _post(client, _var("V_1"))
    _post(client, _var("V_2", frozen=True, equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    r = client.delete(
        f"/api/equation/variables/{_iri_path(f'{BASE}#V_1')}"
        "?cascade=true")
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["frozen"] is True
    assert detail["blockers"]

    remaining = _context_iris(client)
    assert f"{BASE}#V_1" in remaining
    assert f"{BASE}#V_2" in remaining


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


def test_additive_token_declarations_exempt_when_referenced(client):
    """Declaring carriesToken/tokenVector on a previously untracked but
    referenced variable is additive metadata — not a structural change."""
    _post(client, _var("V_1"))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    r = _put(client, _var(
        "V_1",
        tokens=["https://w3id.org/promo/ontology#token_mass"],
        token_vector={"token_mass": 1, "token_time": -1},
    ))
    assert r.status_code == 200, r.text


def test_altering_token_declarations_blocked_when_referenced(client):
    """Removing/changing carriesToken stays locked — port licensing is a
    real consumer.  ``token_vector`` alone is exempt (ruled 2026-11-11):
    the signature feeds only advisories, nothing gates on it."""
    _post(client, _var("V_1",
        tokens=["https://w3id.org/promo/ontology#token_mass"],
        token_vector={"token_mass": 1}))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    r = _put(client, _var("V_1"))  # drops both declarations
    assert r.status_code == 409
    locked = r.json()["detail"]["locked_fields"]
    assert "tokens" in locked and "token_vector" not in locked


def test_signature_only_change_exempt_when_referenced(client):
    """Ruled 2026-11-11: ``token_vector`` feeds only advisories — nothing
    gates on it — so signature-only edits pass the §18 lock on a
    referenced variable.  This is the sanctioned fix path for token
    advisories: membership-without-signature."""
    _post(client, _var("V_1",
        tokens=["https://w3id.org/promo/ontology#token_mass"],
        token_vector={"token_mass": 1}))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    # Clear the signature, keep the membership — the geometry-port fix.
    r = _put(client, _var("V_1",
        tokens=["https://w3id.org/promo/ontology#token_mass"],
        token_vector={}))
    assert r.status_code == 200, r.text


def test_port_membership_without_signature_legal(client):
    """Ruled 2026-11-11: a port may carry membership with an explicitly
    empty signature — licensed for the network, algebraically neutral
    (the geometry-port fix)."""
    r = client.post("/api/equation/variables", json=_var(
        "V_v",
        port_variable=True,
        tokens=["https://w3id.org/promo/ontology#token_mass"],
        token_vector={},
    ))
    assert r.status_code == 200, r.text


def test_signature_may_exceed_membership(client):
    """Composite signatures legitimately name networks the variable is
    not licensed for — a mass-flow signs ``{mass,time}`` but belongs to
    mass only (data-proven: ten persisted variables)."""
    r = client.post("/api/equation/variables", json=_var(
        "V_f",
        tokens=["https://w3id.org/promo/ontology#token_mass"],
        token_vector={"token_mass": 1, "token_time": -1},
    ))
    assert r.status_code == 200, r.text


def test_token_vector_key_form_not_a_change(client):
    """tokenVector keys interoperate by fragment: an IRI-keyed edit of a
    fragment-keyed stored vector is not a structural change."""
    _post(client, _var(
        "V_1",
        tokens=["https://w3id.org/promo/ontology#token_mass"],
        token_vector={"token_mass": 1, "token_time": -1},
    ))
    _post(client, _var("V_2", equations={
        "root": _eq("E_1", f"{BASE}#V_2", "V_1 * 2"),
    }))

    r = _put(client, _var(
        "V_1",
        tokens=["https://w3id.org/promo/ontology#token_mass"],
        token_vector={
            "https://w3id.org/promo/ontology#token_mass": 1,
            "https://w3id.org/promo/ontology#token_time": -1,
        },
    ))
    assert r.status_code == 200, r.text


def test_port_variable_without_token_rejected(client):
    """A port declaring no carriesToken can license no connection —
    the write path rejects it outright (§3 guard, ruled 2026-11-10)."""
    r = client.post("/api/equation/variables",
                    json=_var("V_p", port_variable=True))
    assert r.status_code == 400
    assert "carriesToken" in r.text


def test_token_vector_without_membership_rejected(client):
    """A signature with no membership is the half-declared state the
    persisted-data rule forbids — 400 on the write path too."""
    r = client.post("/api/equation/variables",
                    json=_var("V_1", token_vector={"token_mass": 1}))
    assert r.status_code == 400
    assert "carriesToken" in r.text


def test_token_vector_defaults_pure_signature(client):
    """carriesToken without tokenVector stamps the pure {member:1}
    signature at write time — /check still derives and warns."""
    tok = "https://w3id.org/promo/ontology#token_signal"
    r = client.post("/api/equation/variables",
                    json=_var("V_1", tokens=[tok]))
    assert r.status_code == 200, r.text
    assert r.json()["token_vector"] == {"signal": 1}
    # … and the default persists as a promo:tokenVector triple
    g = graph_store.get_store().dataset.graph(URIRef(BASE))
    tv = g.value(URIRef(f"{BASE}#V_1"), PROMO["tokenVector"])
    assert tv is not None and "signal" in str(tv)


def test_domain_backfill_not_a_move(client):
    """Records saved before IRI-backed domains store domain_iri=None; the
    write path derives it from the network name.  A plain save must not
    mistake the backfill for a domain move — which would 409 on
    references that live outside the editable graph."""
    from rdflib.namespace import RDF

    _post(client, _var("V_1"))
    # Emulate the legacy record: drop the derived inDomain triple.
    store = graph_store.get_store()
    onto = store.dataset.graph(URIRef(BASE))
    onto.remove((URIRef(f"{BASE}#V_1"), PROMO["inDomain"], None))
    # Referencing equation in a *foreign* graph — outside the editable
    # write graph, so a phantom move would be unfulfillable.
    artefact = store.dataset.graph(URIRef("https://example.org/lib"))
    eq = URIRef("https://example.org/lib#E_1")
    artefact.add((eq, RDF.type, PROMO["Equation"]))
    artefact.add((eq, PROMO["rhs"], Literal("V_1 * 2")))

    r = _put(client, _var("V_1", doc="edited"))
    assert r.status_code == 200, r.text
    assert "universe" in (r.json().get("domain_iri") or "")


def test_axisvalue_loaded_across_graphs(client):
    """axisValue on a variable in a non-ontology graph resolves to
    classifications — the AxisTerm/hasAxis resources live in the
    ontology graph, not the variable's own graph."""
    from rdflib import Graph, URIRef
    from rdflib.namespace import RDF
    from backend.ontology.rdf_context import scoped_context

    store = graph_store.get_store()
    onto = store.dataset.graph(URIRef(BASE))
    term = next(onto.subjects(PROMO["hasAxis"], None))
    artefact = store.dataset.graph(URIRef("https://example.org/lib"))
    artefact.add((URIRef("https://example.org/lib#v1"),
                  RDF.type, PROMO["Variable"]))
    artefact.add((URIRef("https://example.org/lib#v1"),
                  PROMO["axisValue"], term))

    var = scoped_context(store, None).variables()[
        "https://example.org/lib#v1"]
    axis = str(onto.value(term, PROMO["hasAxis"]))
    assert getattr(var, "classifications") == {axis: str(term)}
