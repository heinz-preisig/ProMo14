"""Tests for the ontology editor backend (``backend/ontology/service.py``).

Uses FastAPI's ``TestClient`` against a temporary data directory so that
the seeded default ontology is loaded fresh for each test session.
"""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from backend.core import graph_store
from backend.main import app


def _iri_path(iri: str) -> str:
    """URL-encode an IRI for use in a path parameter.

    Encodes ``#`` (which would be treated as a fragment) but keeps
    ``/`` unencoded so the FastAPI ``{iri:path}`` converter matches.
    """
    return quote(iri, safe="/:@!$&'()*+,;=-._~")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    """Yield a ``TestClient`` backed by a fresh store in a temp dir."""
    monkeypatch.setenv("PROMO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(graph_store, "_STORE", None)
    with TestClient(app) as c:
        yield c
    monkeypatch.setattr(graph_store, "_STORE", None)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Seeded default ontology
# ---------------------------------------------------------------------------

def test_seed_domains(client):
    r = client.get("/api/ontology/domains")
    assert r.status_code == 200
    domains = r.json()
    names = {d["name"] for d in domains}
    assert "physical" in names
    assert "information" in names
    phys = next(d for d in domains if d["name"] == "physical")
    assert phys["branch"] == "physical"
    info = next(d for d in domains if d["name"] == "information")
    assert info["branch"] == "information"


def test_seed_tokens(client):
    r = client.get("/api/ontology/tokens")
    assert r.status_code == 200
    tokens = r.json()
    labels = {t["label"] for t in tokens}
    assert "Energy" in labels
    assert "Mass" in labels
    assert "Momentum" in labels
    assert "Signal" in labels


def test_seed_axes(client):
    r = client.get("/api/ontology/axes")
    assert r.status_code == 200
    axes = r.json()
    assert len(axes) >= 2
    role_axes = [a for a in axes if a["name"] == "role"]
    assert len(role_axes) >= 2  # one per branch
    # Each role axis should have terms
    for ax in role_axes:
        assert len(ax["terms"]) > 0


def test_seed_entity_types(client):
    r = client.get("/api/ontology/entity-types")
    assert r.status_code == 200
    ets = r.json()
    labels = {et["label"] for et in ets}
    assert "Lumped" in labels
    assert "Distributed" in labels
    assert "Environment" in labels
    assert "Transport System" in labels
    # Check lumped entity type fields
    lumped = next(et for et in ets if et["label"] == "Lumped")
    assert lumped["temporal_type"] == "dynamic"
    assert lumped["spatial_type"] == "uniform"
    assert lumped["spatial_size"] == "finite"
    assert lumped["branch"] == "physical"


def test_seed_connection_rules(client):
    r = client.get("/api/ontology/connection-rules")
    assert r.status_code == 200
    rules = r.json()
    rule_types = {r["rule_type"] for r in rules}
    assert "physical-same" in rule_types
    assert "signal" in rule_types
    assert "access" in rule_types
    assert "sensor" in rule_types
    assert "actuation" in rule_types
    # physical-cross retired 2026-09-15 (token-flow + scope=cross can
    # never apply — cross-branch pairs share no tokens)
    assert "physical-cross" not in rule_types


def test_seed_scale_dimensions(client):
    r = client.get("/api/ontology/scale-dimensions")
    assert r.status_code == 200
    dims = r.json()
    names = {d["name"] for d in dims}
    assert "time" in names
    assert "length" in names
    # Time scale should have values with hierarchy
    time_dim = next(d for d in dims if d["name"] == "time")
    assert len(time_dim["values"]) > 0
    # Check for triple-domain children (constant/dynamic/event-dynamic)
    value_labels = {v["label"] for v in time_dim["values"]}
    assert "constant" in value_labels
    assert "dynamic" in value_labels
    assert "event-dynamic" in value_labels


def test_seed_context(client):
    r = client.get("/api/ontology/context")
    assert r.status_code == 200
    ctx = r.json()
    assert "domains" in ctx
    assert "axes" in ctx
    assert "entity_types" in ctx
    assert "connection_rules" in ctx
    assert "scale_dimensions" in ctx
    assert len(ctx["domains"]) >= 2


# ---------------------------------------------------------------------------
# Token CRUD
# ---------------------------------------------------------------------------

def test_token_create_list_delete(client):
    # Create
    r = client.post("/api/ontology/tokens", json={
        "iri": "", "label": "Test Token", "parent": None,
    })
    assert r.status_code == 200
    tok = r.json()
    assert tok["label"] == "Test Token"
    assert tok["iri"]
    iri = tok["iri"]

    # List — should include the new token
    r = client.get("/api/ontology/tokens")
    labels = {t["label"] for t in r.json()}
    assert "Test Token" in labels

    # Delete
    r = client.delete(f"/api/ontology/tokens/{_iri_path(iri)}")
    assert r.status_code == 200
    assert r.json()["deleted"] == iri

    # Verify gone
    r = client.get("/api/ontology/tokens")
    labels = {t["label"] for t in r.json()}
    assert "Test Token" not in labels


def test_token_create_with_parent(client):
    # Create parent
    r = client.post("/api/ontology/tokens", json={
        "iri": "", "label": "Parent Token", "parent": None,
    })
    parent_iri = r.json()["iri"]

    # Create child
    r = client.post("/api/ontology/tokens", json={
        "iri": "", "label": "Child Token", "parent": parent_iri,
    })
    assert r.status_code == 200
    assert r.json()["parent"] == parent_iri


# ---------------------------------------------------------------------------
# Domain CRUD
# ---------------------------------------------------------------------------

def test_domain_create_list_delete(client):
    r = client.post("/api/ontology/domains", json={
        "iri": "", "name": "thermo", "parent": None,
        "branch": None, "children": [], "tokens": [],
    })
    assert r.status_code == 200
    dom = r.json()
    assert dom["name"] == "thermo"
    assert dom["iri"]
    iri = dom["iri"]

    # List
    r = client.get("/api/ontology/domains")
    names = {d["name"] for d in r.json()}
    assert "thermo" in names

    # Delete
    r = client.delete(f"/api/ontology/domains/{_iri_path(iri)}")
    assert r.status_code == 200

    # Verify gone
    r = client.get("/api/ontology/domains")
    names = {d["name"] for d in r.json()}
    assert "thermo" not in names


def test_domain_create_with_tokens(client):
    # Create a token first
    r = client.post("/api/ontology/tokens", json={
        "iri": "", "label": "Entropy", "parent": None,
    })
    tok_iri = r.json()["iri"]

    # Create domain with token binding
    r = client.post("/api/ontology/domains", json={
        "iri": "", "name": "thermal", "parent": None,
        "branch": "physical", "children": [], "tokens": [tok_iri],
    })
    assert r.status_code == 200
    assert tok_iri in r.json()["tokens"]


def test_domain_create_subdomain(client):
    # Get physical domain IRI from seed
    r = client.get("/api/ontology/domains")
    phys = next(d for d in r.json() if d["name"] == "physical")
    phys_iri = phys["iri"]

    # Create subdomain
    r = client.post("/api/ontology/domains", json={
        "iri": "", "name": "mechanical", "parent": phys_iri,
        "branch": None, "children": [], "tokens": [],
    })
    assert r.status_code == 200
    assert r.json()["parent"] == phys_iri


# ---------------------------------------------------------------------------
# Index CRUD
# ---------------------------------------------------------------------------

def test_index_create_list_delete(client):
    r = client.post("/api/ontology/indices", json={
        "iri": "", "label": "Species Index", "short_name": "N",
        "network": "root", "index_class": "index",
        "internal_id": None, "aliases": {}, "token": None,
    })
    assert r.status_code == 200
    idx = r.json()
    assert idx["label"] == "Species Index"
    assert idx["iri"]
    iri = idx["iri"]

    # List
    r = client.get("/api/ontology/indices")
    labels = {i["label"] for i in r.json()}
    assert "Species Index" in labels

    # Delete
    r = client.delete(f"/api/ontology/indices/{_iri_path(iri)}")
    assert r.status_code == 200

    # Verify gone
    r = client.get("/api/ontology/indices")
    labels = {i["label"] for i in r.json()}
    assert "Species Index" not in labels


# ---------------------------------------------------------------------------
# Classification axis CRUD
# ---------------------------------------------------------------------------

def test_axis_create_list_delete(client):
    # Need a domain IRI — use seeded physical
    r = client.get("/api/ontology/domains")
    phys_iri = next(d["iri"] for d in r.json() if d["name"] == "physical")

    r = client.post("/api/ontology/axes", json={
        "iri": "", "domain": phys_iri, "name": "extensivity",
        "parent": None, "terms": [],
    })
    assert r.status_code == 200
    ax = r.json()
    assert ax["name"] == "extensivity"
    assert ax["domain"] == phys_iri
    iri = ax["iri"]

    # List
    r = client.get("/api/ontology/axes")
    names = {a["name"] for a in r.json()}
    assert "extensivity" in names

    # Delete
    r = client.delete(f"/api/ontology/axes/{_iri_path(iri)}")
    assert r.status_code == 200

    # Verify gone
    r = client.get("/api/ontology/axes")
    names = {a["name"] for a in r.json()}
    assert "extensivity" not in names


# ---------------------------------------------------------------------------
# Axis term CRUD
# ---------------------------------------------------------------------------

def test_axis_term_create_list_delete(client):
    # Get a seeded axis IRI
    r = client.get("/api/ontology/axes")
    axis_iri = next(a["iri"] for a in r.json() if a["name"] == "role")

    r = client.post("/api/ontology/axis-terms", json={
        "iri": "", "axis": axis_iri, "label": "accumulation",
        "parent": None,
    })
    assert r.status_code == 200
    term = r.json()
    assert term["label"] == "accumulation"
    assert term["axis"] == axis_iri
    iri = term["iri"]

    # List
    r = client.get("/api/ontology/axis-terms")
    labels = {t["label"] for t in r.json()}
    assert "accumulation" in labels

    # Delete
    r = client.delete(f"/api/ontology/axis-terms/{_iri_path(iri)}")
    assert r.status_code == 200

    # Verify gone
    r = client.get("/api/ontology/axis-terms")
    labels = {t["label"] for t in r.json()}
    assert "accumulation" not in labels


def test_axis_term_hierarchical(client):
    # Get a seeded axis IRI
    r = client.get("/api/ontology/axes")
    axis_iri = next(a["iri"] for a in r.json() if a["name"] == "role")

    # Create parent term
    r = client.post("/api/ontology/axis-terms", json={
        "iri": "", "axis": axis_iri, "label": "parent_term",
        "parent": None,
    })
    parent_iri = r.json()["iri"]

    # Create child term
    r = client.post("/api/ontology/axis-terms", json={
        "iri": "", "axis": axis_iri, "label": "child_term",
        "parent": parent_iri,
    })
    assert r.status_code == 200
    assert r.json()["parent"] == parent_iri


# ---------------------------------------------------------------------------
# Scale dimension CRUD
# ---------------------------------------------------------------------------

def test_scale_dimension_create_list_delete(client):
    # Need a domain IRI
    r = client.get("/api/ontology/domains")
    phys_iri = next(d["iri"] for d in r.json() if d["name"] == "physical")

    r = client.post("/api/ontology/scale-dimensions", json={
        "iri": "", "name": "pressure_scale", "domain": phys_iri,
        "parent": None, "values": [],
    })
    assert r.status_code == 200
    dim = r.json()
    assert dim["name"] == "pressure_scale"
    iri = dim["iri"]

    # List
    r = client.get("/api/ontology/scale-dimensions")
    names = {d["name"] for d in r.json()}
    assert "pressure_scale" in names

    # Delete
    r = client.delete(f"/api/ontology/scale-dimensions/{_iri_path(iri)}")
    assert r.status_code == 200

    # Verify gone
    r = client.get("/api/ontology/scale-dimensions")
    names = {d["name"] for d in r.json()}
    assert "pressure_scale" not in names


# ---------------------------------------------------------------------------
# Scale value CRUD
# ---------------------------------------------------------------------------

def test_scale_value_create_list_delete(client):
    # Get a seeded scale dimension IRI
    r = client.get("/api/ontology/scale-dimensions")
    time_dim_iri = next(d["iri"] for d in r.json() if d["name"] == "time")

    r = client.post("/api/ontology/scale-values", json={
        "iri": "", "dimension": time_dim_iri, "label": "picosecond",
        "parent": None,
    })
    assert r.status_code == 200
    val = r.json()
    assert val["label"] == "picosecond"
    assert val["dimension"] == time_dim_iri
    iri = val["iri"]

    # List
    r = client.get("/api/ontology/scale-values")
    labels = {v["label"] for v in r.json()}
    assert "picosecond" in labels

    # Delete
    r = client.delete(f"/api/ontology/scale-values/{_iri_path(iri)}")
    assert r.status_code == 200

    # Verify gone
    r = client.get("/api/ontology/scale-values")
    labels = {v["label"] for v in r.json()}
    assert "picosecond" not in labels


# ---------------------------------------------------------------------------
# Entity type CRUD
# ---------------------------------------------------------------------------

def test_entity_type_create_list_delete(client):
    r = client.post("/api/ontology/entity-types", json={
        "iri": "", "label": "Custom Type", "temporal_type": "dynamic",
        "spatial_type": "uniform", "spatial_size": "finite",
        "branch": "physical", "scale_values": [], "description": "A test type",
    })
    assert r.status_code == 200
    et = r.json()
    assert et["label"] == "Custom Type"
    assert et["temporal_type"] == "dynamic"
    assert et["description"] == "A test type"
    iri = et["iri"]

    # List
    r = client.get("/api/ontology/entity-types")
    labels = {e["label"] for e in r.json()}
    assert "Custom Type" in labels

    # Delete
    r = client.delete(f"/api/ontology/entity-types/{_iri_path(iri)}")
    assert r.status_code == 200

    # Verify gone
    r = client.get("/api/ontology/entity-types")
    labels = {e["label"] for e in r.json()}
    assert "Custom Type" not in labels


def test_entity_type_information_branch(client):
    r = client.post("/api/ontology/entity-types", json={
        "iri": "", "label": "Info Custom", "temporal_type": "dynamic",
        "spatial_type": None, "spatial_size": None,
        "branch": "information", "scale_values": [], "description": "",
    })
    assert r.status_code == 200
    et = r.json()
    assert et["branch"] == "information"
    assert et["spatial_type"] is None
    assert et["spatial_size"] is None


# ---------------------------------------------------------------------------
# Connection rule CRUD
# ---------------------------------------------------------------------------

def test_connection_rule_create_list_delete(client):
    r = client.post("/api/ontology/connection-rules", json={
        "iri": "", "rule_type": "signal", "source_domain": None,
        "target_domain": None, "shared_tokens": [],
        "direction": "unidirectional", "description": "Test signal rule",
    })
    assert r.status_code == 200
    rule = r.json()
    assert rule["rule_type"] == "signal"
    assert rule["direction"] == "unidirectional"
    iri = rule["iri"]

    # List
    r = client.get("/api/ontology/connection-rules")
    types = {r["rule_type"] for r in r.json()}
    assert "signal" in types  # seeded + new

    # Delete
    r = client.delete(f"/api/ontology/connection-rules/{_iri_path(iri)}")
    assert r.status_code == 200

    # Verify the specific one is gone (seeded signal rule still exists)
    r = client.get("/api/ontology/connection-rules")
    rules = r.json()
    assert iri not in {r["iri"] for r in rules}


def test_connection_rule_with_domains_and_tokens(client):
    # Create two domains and a token
    r = client.post("/api/ontology/domains", json={
        "iri": "", "name": "domain_a", "parent": None,
        "branch": "physical", "children": [], "tokens": [],
    })
    dom_a = r.json()["iri"]
    r = client.post("/api/ontology/domains", json={
        "iri": "", "name": "domain_b", "parent": None,
        "branch": "physical", "children": [], "tokens": [],
    })
    dom_b = r.json()["iri"]
    r = client.post("/api/ontology/tokens", json={
        "iri": "", "label": "Shared Quantity", "parent": None,
    })
    tok_iri = r.json()["iri"]

    # Create cross-domain rule
    r = client.post("/api/ontology/connection-rules", json={
        "iri": "", "rule_type": "physical-cross",
        "source_domain": dom_a, "target_domain": dom_b,
        "shared_tokens": [tok_iri],
        "direction": "bidirectional", "description": "Cross-domain test",
    })
    assert r.status_code == 200
    rule = r.json()
    assert rule["source_domain"] == dom_a
    assert rule["target_domain"] == dom_b
    assert tok_iri in rule["shared_tokens"]


# ---------------------------------------------------------------------------
# Save / persistence
# ---------------------------------------------------------------------------

def test_save_ontology(client):
    r = client.post("/api/ontology/save", json={"filename": "test_ontology.trig"})
    assert r.status_code == 200
    assert "test_ontology.trig" in r.json()["saved"]


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_delete_nonexistent_domain(client):
    r = client.delete(f"/api/ontology/domains/{_iri_path('https://w3id.org/promo/ontology#nonexistent')}")
    assert r.status_code == 404


def test_delete_nonexistent_token(client):
    r = client.delete(f"/api/ontology/tokens/{_iri_path('https://w3id.org/promo/ontology#nonexistent')}")
    assert r.status_code == 404


def test_delete_nonexistent_index(client):
    r = client.delete(f"/api/ontology/indices/{_iri_path('https://w3id.org/promo/ontology#nonexistent')}")
    assert r.status_code == 404


def test_delete_nonexistent_axis(client):
    r = client.delete(f"/api/ontology/axes/{_iri_path('https://w3id.org/promo/ontology#nonexistent')}")
    assert r.status_code == 404


def test_delete_nonexistent_entity_type(client):
    r = client.delete(f"/api/ontology/entity-types/{_iri_path('https://w3id.org/promo/ontology#nonexistent')}")
    assert r.status_code == 404


def test_delete_nonexistent_connection_rule(client):
    r = client.delete(f"/api/ontology/connection-rules/{_iri_path('https://w3id.org/promo/ontology#nonexistent')}")
    assert r.status_code == 404


def test_delete_nonexistent_scale_dimension(client):
    r = client.delete(f"/api/ontology/scale-dimensions/{_iri_path('https://w3id.org/promo/ontology#nonexistent')}")
    assert r.status_code == 404


def test_delete_nonexistent_scale_value(client):
    r = client.delete(f"/api/ontology/scale-values/{_iri_path('https://w3id.org/promo/ontology#nonexistent')}")
    assert r.status_code == 404


def test_delete_nonexistent_axis_term(client):
    r = client.delete(f"/api/ontology/axis-terms/{_iri_path('https://w3id.org/promo/ontology#nonexistent')}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Network (legacy) CRUD
# ---------------------------------------------------------------------------

def test_network_list(client):
    r = client.get("/api/ontology/networks")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_network_create(client):
    r = client.post("/api/ontology/networks", json={
        "iri": "", "name": "test_network", "parent": None,
        "label": None, "children": [],
    })
    assert r.status_code == 200
    assert r.json()["name"] == "test_network"
