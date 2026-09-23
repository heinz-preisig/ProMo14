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
from rdflib import URIRef
from rdflib.namespace import RDF

from backend.core import graph_store
from backend.main import app
from backend.ontology.rdf_context import RdfContext


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
    # Create a token first (label must not collide with a seed token —
    # auto-mint collisions are 409 under the unified namespace).
    r = client.post("/api/ontology/tokens", json={
        "iri": "", "label": "Test Quantity", "parent": None,
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
    # rule_type must not collide with a seed rule — auto-mint
    # collisions are 409 under the unified namespace.
    r = client.post("/api/ontology/connection-rules", json={
        "iri": "", "rule_type": "signal-test", "source_domain": None,
        "target_domain": None, "shared_tokens": [],
        "direction": "unidirectional", "description": "Test signal rule",
    })
    assert r.status_code == 200
    rule = r.json()
    assert rule["rule_type"] == "signal-test"
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
# Connection rule resolution
# ---------------------------------------------------------------------------

def _domain_iri(client, name: str) -> str:
    r = client.get("/api/ontology/domains")
    return next(d["iri"] for d in r.json() if d["name"] == name)


def _token_iri(client, label: str) -> str:
    r = client.get("/api/ontology/tokens")
    return next(t["iri"] for t in r.json() if t["label"] == label)


def _resolve(client, source: str, target: str):
    r = client.get("/api/ontology/resolve-connection",
                   params={"source": source, "target": target})
    assert r.status_code == 200
    return r.json()["rules"]


def test_resolve_same_branch(client):
    phys = _domain_iri(client, "physical")
    rules = _resolve(client, phys, phys)
    types = {r["rule_type"] for r in rules}
    assert types == {"physical-same", "access"}
    ps = next(r for r in rules if r["rule_type"] == "physical-same")
    assert ps["matched_tokens"]  # licensed physical tokens reported


def test_resolve_cross_branch(client):
    """scope=cross must fire across the branch boundary (C1 contract)."""
    phys = _domain_iri(client, "physical")
    info = _domain_iri(client, "information")
    rules = _resolve(client, phys, info)
    assert [r["rule_type"] for r in rules] == ["sensor"]
    rules = _resolve(client, info, phys)
    assert [r["rule_type"] for r in rules] == ["actuation"]


def test_resolve_information_same_branch(client):
    info = _domain_iri(client, "information")
    rules = _resolve(client, info, info)
    assert [r["rule_type"] for r in rules] == ["signal"]


def test_resolve_bidirectional_swapped_match(client):
    """An asymmetric bidirectional rule matching only via the swapped
    pair must resolve (previously crashed with ValueError -> 500)."""
    phys = _domain_iri(client, "physical")
    info = _domain_iri(client, "information")
    signal = _token_iri(client, "Signal")
    r = client.post("/api/ontology/connection-rules", json={
        "iri": "", "rule_type": "bidir-x",
        "source_domain": phys, "target_domain": info,
        "shared_tokens": [signal],
        "direction": "bidirectional", "carrier": "reference",
        "scope": "any", "description": "asymmetric bidirectional",
    })
    assert r.status_code == 200
    rule_iri = r.json()["iri"]
    # Query swapped: info->phys matches only via the bidirectional swap.
    rules = _resolve(client, info, phys)
    assert rule_iri in {r["iri"] for r in rules}


def test_resolve_empty_shared_tokens_never_applies(client):
    """Empty sharedTokens = no token licensed = rule never applies."""
    phys = _domain_iri(client, "physical")
    r = client.post("/api/ontology/connection-rules", json={
        "iri": "", "rule_type": "dead-rule",
        "source_domain": phys, "target_domain": phys,
        "shared_tokens": [],
        "direction": "bidirectional", "carrier": "token-flow",
        "scope": "same", "description": "no token licensed",
    })
    assert r.status_code == 200
    dead_iri = r.json()["iri"]
    rules = _resolve(client, phys, phys)
    assert dead_iri not in {r["iri"] for r in rules}


def test_resolve_unrelated_token_not_licensed(client):
    """A rule token on a disjoint token tree licenses nothing."""
    phys = _domain_iri(client, "physical")
    r = client.post("/api/ontology/tokens", json={
        "iri": "", "label": "Alien Quantity", "parent": None})
    assert r.status_code == 200
    alien = r.json()["iri"]
    r = client.post("/api/ontology/connection-rules", json={
        "iri": "", "rule_type": "alien-rule",
        "source_domain": phys, "target_domain": phys,
        "shared_tokens": [alien],
        "direction": "bidirectional", "carrier": "token-flow",
        "scope": "same", "description": "token bound nowhere",
    })
    assert r.status_code == 200
    alien_rule = r.json()["iri"]
    rules = _resolve(client, phys, phys)
    assert alien_rule not in {r["iri"] for r in rules}


# ---------------------------------------------------------------------------
# Validation (contract invariants)
# ---------------------------------------------------------------------------

def test_domain_cycle_rejected(client):
    r = client.post("/api/ontology/domains", json={
        "iri": "", "name": "cyc_a", "parent": None,
        "branch": None, "children": [], "tokens": []})
    a = r.json()["iri"]
    r = client.post("/api/ontology/domains", json={
        "iri": "", "name": "cyc_b", "parent": a,
        "branch": None, "children": [], "tokens": []})
    b = r.json()["iri"]
    # Reparenting a under b would create a cycle.
    r = client.post("/api/ontology/domains", json={
        "iri": a, "name": "cyc_a", "parent": b,
        "branch": None, "children": [], "tokens": []})
    assert r.status_code == 422


def test_domain_branch_invariant(client):
    phys = _domain_iri(client, "physical")
    # Unset branch is inherited from the top-level ancestor.
    r = client.post("/api/ontology/domains", json={
        "iri": "", "name": "thermal_sub", "parent": phys,
        "branch": None, "children": [], "tokens": []})
    assert r.status_code == 200
    assert r.json()["branch"] == "physical"
    # A mismatching branch is rejected.
    r = client.post("/api/ontology/domains", json={
        "iri": "", "name": "bad_branch", "parent": phys,
        "branch": "information", "children": [], "tokens": []})
    assert r.status_code == 422


def test_domain_dangling_refs_rejected(client):
    bogus = "https://w3id.org/promo/ontology#nonexistent"
    r = client.post("/api/ontology/domains", json={
        "iri": "", "name": "orphan_x", "parent": bogus,
        "branch": None, "children": [], "tokens": []})
    assert r.status_code == 422
    r = client.post("/api/ontology/domains", json={
        "iri": "", "name": "bad_tok", "parent": None,
        "branch": None, "children": [], "tokens": [bogus]})
    assert r.status_code == 422


def test_iri_collision_409(client):
    payload = {"iri": "", "label": "Dup Token", "parent": None}
    r = client.post("/api/ontology/tokens", json=payload)
    assert r.status_code == 200
    # Same label auto-mints the same IRI -> collision.
    r = client.post("/api/ontology/tokens", json=payload)
    assert r.status_code == 409


def test_vocab_literal_rejected(client):
    r = client.post("/api/ontology/connection-rules", json={
        "iri": "", "rule_type": "bad-scope",
        "source_domain": None, "target_domain": None,
        "shared_tokens": [], "direction": "unidirectional",
        "carrier": "reference", "scope": "bogus", "description": ""})
    assert r.status_code == 422


def test_entity_type_temporal_consistency(client):
    """temporal_type must agree with a bound temporal-triple leaf."""
    r = client.get("/api/ontology/scale-values")
    dyn = next(v["iri"] for v in r.json() if v["label"] == "dynamic")
    base = {"iri": "", "label": "Temporal Check", "spatial_type": None,
            "spatial_size": None, "branch": "physical",
            "scale_values": [dyn], "description": ""}
    r = client.post("/api/ontology/entity-types",
                    json={**base, "temporal_type": "constant"})
    assert r.status_code == 422
    r = client.post("/api/ontology/entity-types",
                    json={**base, "temporal_type": "dynamic"})
    assert r.status_code == 200


def test_freeze_version(client):
    """freeze_version copies the working graph under a version IRI and
    refuses to re-freeze (published versions are immutable)."""
    store = graph_store.get_store()
    working = store.ontology_graph
    v_iri = store.freeze_version("9.9-test")
    vg = store.dataset.graph(v_iri)
    assert len(vg) >= len(working)
    assert (v_iri, RDF.type,
            graph_store.PROMO["Version"]) in vg
    assert (v_iri, graph_store.PROMO["versionOf"],
            store.ONTOLOGY_GRAPH_IRI) in vg
    with pytest.raises(ValueError):
        store.freeze_version("9.9-test")


def test_publish_and_versions(client):
    r = client.post("/api/ontology/publish", json={"version": "1.1"})
    assert r.status_code == 200
    assert r.json()["version_iri"].endswith("/1.1")
    r = client.post("/api/ontology/publish", json={"version": "1.1"})
    assert r.status_code == 409
    r = client.post("/api/ontology/publish", json={"version": "v2"})
    assert r.status_code == 422
    r = client.get("/api/ontology/versions")
    versions = r.json()["versions"]
    assert any(v["version"] == "1.1" for v in versions)
    assert r.json()["suggested_next"] == "1.2"


def test_export_version(client):
    client.post("/api/ontology/publish", json={"version": "1.1"})
    r = client.get("/api/ontology/export?version=1.1")
    assert r.status_code == 200
    assert "text/turtle" in r.headers["content-type"]
    assert "promo:Version" in r.text
    r = client.get("/api/ontology/export?version=9.9")
    assert r.status_code == 404


def test_artefact_type_markers(client):
    """Graphs self-describe: the working ontology is typed
    promo:Ontology; a frozen version carries both promo:Version and the
    source's artefact type on its own IRI."""
    store = graph_store.get_store()
    g = store.ontology_graph
    assert (g.identifier, RDF.type, graph_store.PROMO["Ontology"]) in g
    v_iri = store.freeze_version("8.8-test")
    vg = store.dataset.graph(v_iri)
    assert (v_iri, RDF.type, graph_store.PROMO["Version"]) in vg
    assert (v_iri, RDF.type, graph_store.PROMO["Ontology"]) in vg


def test_frozen_graph_read_only(client):
    """R5: assert_editable rejects frozen version graphs."""
    store = graph_store.get_store()
    store.assert_editable(store.ontology_graph)  # draft: no raise
    v_iri = store.freeze_version("7.7-test")
    vg = store.dataset.graph(v_iri)
    assert store.is_frozen(vg)
    with pytest.raises(ValueError):
        store.assert_editable(vg)


def test_catalogue(client):
    """The catalogue groups drafts with their frozen versions."""
    r = client.get("/api/catalogue")
    assert r.status_code == 200
    lines = r.json()["lines"]
    onto = [l for l in lines
            if l["iri"] == str(graph_store.RdfStore.ONTOLOGY_GRAPH_IRI)]
    assert len(onto) == 1
    assert onto[0]["type"] == "ontology"
    assert onto[0]["status"] == "draft"
    assert onto[0]["versions"] == []

    client.post("/api/ontology/publish", json={"version": "1.1"})
    lines = client.get("/api/catalogue").json()["lines"]
    onto = [l for l in lines
            if l["iri"] == str(graph_store.RdfStore.ONTOLOGY_GRAPH_IRI)][0]
    assert [v["version"] for v in onto["versions"]] == ["1.1"]
    assert onto["versions"][0]["iri"].endswith("/1.1")


def test_rdf_context_scoped(client):
    """R4: graph_iris scopes resolution — vocabulary comes from the
    given graph(s), not the working draft."""
    store = graph_store.get_store()
    v_iri = store.freeze_version("6.6-test")

    scoped = RdfContext(store, graph_iris=[v_iri])
    assert len(scoped.domains()) > 0  # frozen copy supplies vocabulary

    # An empty foreign graph yields an empty vocabulary — the working
    # draft does not leak into a scoped context.
    empty = RdfContext(store, graph_iris=["https://example.org/empty"])
    assert empty.domains() == []
    assert empty.entity_types() == []


def test_graph_param_scopes_reads(client):
    """?graph= selects the artefact a request operates on."""
    store = graph_store.get_store()
    v_iri = store.freeze_version("5.5-test")
    r = client.get(f"/api/ontology/domains?graph={v_iri}")
    assert r.status_code == 200
    assert len(r.json()) > 0  # frozen copy serves reads
    r = client.get("/api/ontology/domains?graph=https://example.org/none")
    assert r.json() == []  # unknown graph: empty, not the working draft


def test_graph_param_blocks_frozen_writes(client):
    """R5 enforced: mutations with ?graph=<frozen> get 403."""
    store = graph_store.get_store()
    v_iri = store.freeze_version("4.4-test")
    r = client.post(
        f"/api/ontology/tokens?graph={v_iri}",
        json={"iri": "", "label": "X", "parent": None, "kind": None})
    assert r.status_code == 403
    r = client.delete(f"/api/ontology/domains/"
                      f"{_iri_path('https://w3id.org/promo/ontology#domain_root')}"
                      f"?graph={v_iri}")
    assert r.status_code == 403


def test_catalogue_new_and_fork(client):
    """POST /new creates a pinned artefact line; POST /fork copies a
    graph with re-homed IRIs and provenance."""
    store = graph_store.get_store()
    base = str(store.ONTOLOGY_GRAPH_IRI)

    r = client.post("/api/catalogue/new", json={
        "iri": "https://example.org/lib1", "type": "library",
        "label": "My library", "uses": [base]})
    assert r.status_code == 200
    g = store.dataset.graph("https://example.org/lib1")
    assert (g.identifier, RDF.type, graph_store.PROMO["Library"]) in g
    assert (g.identifier, graph_store.PROMO["usesOntology"],
            URIRef(base)) in g

    # unknown type -> 422; existing graph -> 409
    assert client.post("/api/catalogue/new", json={
        "iri": "https://example.org/x", "type": "bogus"}).status_code == 422
    assert client.post("/api/catalogue/new", json={
        "iri": "https://example.org/lib1",
        "type": "library"}).status_code == 409

    # Fork the working ontology: instance IRIs re-homed, provenance set.
    r = client.post("/api/catalogue/fork", json={
        "source": base, "new_iri": "https://example.org/my-onto",
        "label": "My ontology"})
    assert r.status_code == 200
    fg = store.dataset.graph("https://example.org/my-onto")
    assert len(fg) > 0
    assert (fg.identifier, RDF.type, graph_store.PROMO["Ontology"]) in fg
    assert (fg.identifier, graph_store.PROMO["versionOf"],
            URIRef(base)) in fg
    # Instance IRIs re-homed: no subject under the source namespace.
    assert not any(str(s).startswith(f"{base}#") for s in fg.subjects())
    assert any(str(s).startswith("https://example.org/my-onto#")
               for s in fg.subjects())

    # Catalogue shows the new line as a draft ontology.
    lines = client.get("/api/catalogue").json()["lines"]
    forked = [l for l in lines if l["iri"] == "https://example.org/my-onto"]
    assert len(forked) == 1
    assert forked[0]["type"] == "ontology"
    assert forked[0]["status"] == "draft"

    # Forking a frozen version works too (frozen graphs are read-only
    # sources, not un-forkable).
    v_iri = store.freeze_version("3.3-test")
    r = client.post("/api/catalogue/fork", json={"source": str(v_iri)})
    assert r.status_code == 200
    assert r.json()["iri"] == f"{v_iri}-fork"


def test_catalogue_species_pins(client):
    """§20: usesSpecies pins — stamped at creation, replaceable via
    PUT /pins (drafts only), copied on fork, shown on the line."""
    store = graph_store.get_store()

    r = client.post("/api/catalogue/new", json={
        "iri": "https://example.org/scheme", "type": "species",
        "label": "Scheme"})
    assert r.status_code == 200
    r = client.post("/api/catalogue/new", json={
        "iri": "https://example.org/m1", "type": "model",
        "uses_species": ["https://example.org/scheme"]})
    assert r.status_code == 200

    lines = client.get("/api/catalogue").json()["lines"]
    m1 = [l for l in lines if l["iri"] == "https://example.org/m1"][0]
    assert m1["usesSpecies"] == ["https://example.org/scheme"]

    # PUT /pins replaces the named set only.
    client.put("/api/catalogue/pins", json={
        "iri": "https://example.org/m1",
        "usesSpecies": ["https://example.org/other-scheme"]})
    g = store.dataset.graph("https://example.org/m1")
    pins = {str(o) for o in g.objects(
        g.identifier, graph_store.PROMO["usesSpecies"])}
    assert pins == {"https://example.org/other-scheme"}

    # Unknown artefact -> 404; frozen graph -> 403.
    assert client.put("/api/catalogue/pins", json={
        "iri": "https://example.org/none",
        "usesSpecies": []}).status_code == 404
    v_iri = store.freeze_version("9.9-test")
    assert client.put("/api/catalogue/pins", json={
        "iri": str(v_iri),
        "usesSpecies": ["https://example.org/x"]}).status_code == 403

    # Fork carries the pin.
    r = client.post("/api/catalogue/fork", json={
        "source": "https://example.org/m1",
        "new_iri": "https://example.org/m2"})
    assert r.status_code == 200
    fg = store.dataset.graph("https://example.org/m2")
    assert (fg.identifier, graph_store.PROMO["usesSpecies"],
            URIRef("https://example.org/other-scheme")) in fg


def test_equation_context_scoped_by_pins(client):
    """R4 end-to-end: /api/equation/context?graph=<lib> resolves the
    library plus its transitive usesOntology pins — and nothing else."""
    store = graph_store.get_store()
    base = str(store.ONTOLOGY_GRAPH_IRI)

    # A library pinned to the working ontology.
    client.post("/api/catalogue/new", json={
        "iri": "https://example.org/lib", "type": "library",
        "uses": [base]})
    r = client.get("/api/equation/context?graph=https://example.org/lib")
    assert r.status_code == 200
    # The pinned ontology's vocabulary is in scope (its indices are
    # visible); an unrelated graph's would not be.
    assert len(r.json()["indices"]) > 0

    # A library with no pins sees only its own (empty) content.
    client.post("/api/catalogue/new", json={
        "iri": "https://example.org/lonely", "type": "library"})
    r = client.get(
        "/api/equation/context?graph=https://example.org/lonely")
    assert r.json()["indices"] == []
    assert r.json()["variables"] == []

    # Writes land in the library graph, not the ontology.
    r = client.post(
        "/api/equation/variables?graph=https://example.org/lib",
        json={"iri": "", "label": "Lv", "network": "root",
              "type": "state", "units": [0] * 8, "index_structures": [],
              "aliases": {}, "doc": "", "port_variable": False,
              "tokens": [], "equations": {}})
    assert r.status_code == 200
    assert r.json()["iri"].startswith("https://example.org/lib#")
    lib = store.dataset.graph("https://example.org/lib")
    assert any(s.startswith("https://example.org/lib#")
               for s in map(str, lib.subjects(
                   RDF.type, graph_store.PROMO["Variable"])))


def test_entity_type_branch_checked(client):
    r = client.post("/api/ontology/entity-types", json={
        "iri": "", "label": "Bad Branch", "temporal_type": "dynamic",
        "spatial_type": None, "spatial_size": None,
        "branch": "bogus", "scale_values": [], "description": ""})
    assert r.status_code == 422


def test_rule_dangling_refs_rejected(client):
    bogus = "https://w3id.org/promo/ontology#nonexistent"
    r = client.post("/api/ontology/connection-rules", json={
        "iri": "", "rule_type": "bad-src",
        "source_domain": bogus, "target_domain": None,
        "shared_tokens": [], "direction": "unidirectional",
        "carrier": "reference", "scope": "any", "description": ""})
    assert r.status_code == 422
    r = client.post("/api/ontology/connection-rules", json={
        "iri": "", "rule_type": "bad-tok",
        "source_domain": None, "target_domain": None,
        "shared_tokens": [bogus], "direction": "unidirectional",
        "carrier": "reference", "scope": "any", "description": ""})
    assert r.status_code == 422


def test_token_cycle_rejected(client):
    r = client.post("/api/ontology/tokens", json={
        "iri": "", "label": "Tok A", "parent": None})
    a = r.json()["iri"]
    r = client.post("/api/ontology/tokens", json={
        "iri": "", "label": "Tok B", "parent": a})
    b = r.json()["iri"]
    r = client.post("/api/ontology/tokens", json={
        "iri": a, "label": "Tok A", "parent": b})
    assert r.status_code == 422


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
