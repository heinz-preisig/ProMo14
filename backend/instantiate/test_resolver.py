"""Tests for the §16 arc sub-index membership resolver.

Engine tests run on plain dicts; the endpoint test seeds a small model
(capacity —arc— diffusion transport —arc— capacity) into a throwaway
store and checks the resolved membership.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rdflib import RDF, Literal, URIRef

from backend.core import graph_store
from backend.core.graph_store import PROMO
from backend.instantiate.resolver import (
    ArcInfo,
    NodeInfo,
    SubIndexInfo,
    arc_carrier,
    by_sub_index,
    resolve,
)
from backend.main import app

BASE = "https://w3id.org/promo/ontology"


def _et(frag: str) -> str:
    return f"{BASE}#etype_{frag}"


def _idx(frag: str) -> str:
    return f"{BASE}#{frag}"


# Seeded §16 structures (mirroring graph_store._seed_transport_mechanisms
# / _seed_arc_sub_indices):
PARENTS = {
    _et("mass_transport"): _et("transport_system"),
    _et("energy_transport"): _et("transport_system"),
    _et("diffusion_transport"): _et("mass_transport"),
    _et("convection_transport"): _et("mass_transport"),
    _et("heat_transport"): _et("energy_transport"),
    _et("radiation_transport"): _et("energy_transport"),
    _et("work_transport"): _et("energy_transport"),
}

SUB_INDICES = {
    _idx("idx_arc_mass"): SubIndexInfo(
        _idx("idx_arc_mass"), _idx("idx_arc"), _et("mass_transport"),
        "A_mass"),
    _idx("idx_arc_energy"): SubIndexInfo(
        _idx("idx_arc_energy"), _idx("idx_arc"), _et("energy_transport"),
        "A_energy"),
    _idx("idx_arc_diffusion"): SubIndexInfo(
        _idx("idx_arc_diffusion"), _idx("idx_arc"),
        _et("diffusion_transport"), "A_diff"),
    _idx("idx_arc_heat"): SubIndexInfo(
        _idx("idx_arc_heat"), _idx("idx_arc"), _et("heat_transport"),
        "A_heat"),
}


def test_arc_carrier_from_type_iri():
    assert arc_carrier("promo:ArcType/token-flow") == "token-flow"
    assert arc_carrier("promo:ArcType/reference") == "reference"
    assert arc_carrier(None) is None
    assert arc_carrier("") is None


def test_diffusion_arc_joins_leaf_and_token_partition():
    """capacity —arc— diffusion transport: A_diff + A_mass (transitive)."""
    nodes = {
        "n1": NodeInfo("n1", _et("lumped")),
        "n2": NodeInfo("n2", _et("diffusion_transport")),
    }
    arcs = {"a1": ArcInfo("a1", "n1", "n2", "token-flow")}
    out = resolve(nodes, arcs, SUB_INDICES, PARENTS)
    assert out[0].sub_indices == [
        _idx("idx_arc_diffusion"), _idx("idx_arc_mass")]
    assert _et("mass_transport") in out[0].touches
    assert _et("transport_system") in out[0].touches


def test_reference_arc_gets_no_membership():
    """A signal arc touching a transport resolves to nothing."""
    nodes = {
        "n1": NodeInfo("n1", _et("lumped")),
        "n2": NodeInfo("n2", _et("diffusion_transport")),
    }
    arcs = {"a1": ArcInfo("a1", "n1", "n2", "reference")}
    out = resolve(nodes, arcs, SUB_INDICES, PARENTS)
    assert out[0].sub_indices == []
    assert out[0].carrier == "reference"


def test_capacity_capacity_arc_has_no_membership():
    """No transport touched → base index only (empty sub-indices)."""
    nodes = {
        "n1": NodeInfo("n1", _et("lumped")),
        "n2": NodeInfo("n2", _et("distributed")),
    }
    arcs = {"a1": ArcInfo("a1", "n1", "n2", "token-flow")}
    out = resolve(nodes, arcs, SUB_INDICES, PARENTS)
    assert out[0].sub_indices == []


def test_transport_transport_arc_unions_both_ends():
    """diffusion —arc— heat: both mechanisms' sub-indices match."""
    nodes = {
        "n1": NodeInfo("n1", _et("diffusion_transport")),
        "n2": NodeInfo("n2", _et("heat_transport")),
    }
    arcs = {"a1": ArcInfo("a1", "n1", "n2", "token-flow")}
    out = resolve(nodes, arcs, SUB_INDICES, PARENTS)
    assert set(out[0].sub_indices) == {
        _idx("idx_arc_diffusion"), _idx("idx_arc_mass"),
        _idx("idx_arc_heat"), _idx("idx_arc_energy"),
    }


def test_untyped_arc_resolves_permissively():
    nodes = {
        "n1": NodeInfo("n1", _et("lumped")),
        "n2": NodeInfo("n2", _et("heat_transport")),
    }
    arcs = {"a1": ArcInfo("a1", "n1", "n2", None)}
    out = resolve(nodes, arcs, SUB_INDICES, PARENTS)
    assert set(out[0].sub_indices) == {
        _idx("idx_arc_heat"), _idx("idx_arc_energy")}


def test_reference_direction_defaults_to_draw_order():
    nodes = {
        "n1": NodeInfo("n1", _et("lumped")),
        "n2": NodeInfo("n2", _et("diffusion_transport")),
    }
    arcs = {"a1": ArcInfo("a1", "n1", "n2", "token-flow")}
    out = resolve(nodes, arcs, SUB_INDICES, PARENTS)
    assert out[0].reference_from == "n1"
    assert out[0].reference_to == "n2"


def test_reference_direction_uses_stored_orientation():
    """§15: explicit referenceFrom/To override draw order."""
    nodes = {
        "n1": NodeInfo("n1", _et("lumped")),
        "n2": NodeInfo("n2", _et("diffusion_transport")),
    }
    arcs = {"a1": ArcInfo("a1", "n1", "n2", "token-flow",
                          reference_from="n2", reference_to="n1")}
    out = resolve(nodes, arcs, SUB_INDICES, PARENTS)
    assert out[0].reference_from == "n2"
    assert out[0].reference_to == "n1"


def test_by_sub_index_inverts():
    nodes = {
        "n1": NodeInfo("n1", _et("lumped")),
        "n2": NodeInfo("n2", _et("diffusion_transport")),
        "n3": NodeInfo("n3", _et("lumped")),
    }
    arcs = {
        "a1": ArcInfo("a1", "n1", "n2", "token-flow"),
        "a2": ArcInfo("a2", "n2", "n3", "token-flow"),
    }
    inv = by_sub_index(resolve(nodes, arcs, SUB_INDICES, PARENTS))
    assert inv[_idx("idx_arc_diffusion")] == ["a1", "a2"]
    assert inv[_idx("idx_arc_mass")] == ["a1", "a2"]
    assert _idx("idx_arc_heat") not in inv


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


def test_arc_indices_endpoint(client):
    """Seed a capacity—diffusion—capacity model and resolve it."""
    store = graph_store.get_store()
    g = store.ontology_graph  # model lives in the working graph here
    base = str(store.ONTOLOGY_GRAPH_IRI)

    def node(frag, et_frag):
        iri = URIRef(f"{base}/ModelNode_{frag}")
        g.add((iri, RDF.type, PROMO["ModelNode"]))
        g.add((iri, PROMO["entityType"], URIRef(_et(et_frag))))
        return str(iri)

    def arc(frag, src, tgt, carrier):
        iri = URIRef(f"{base}/ModelArc_{frag}")
        g.add((iri, RDF.type, PROMO["ModelArc"]))
        g.add((iri, PROMO["source"], URIRef(src)))
        g.add((iri, PROMO["target"], URIRef(tgt)))
        g.add((iri, PROMO["arcType"],
               Literal(f"promo:ArcType/{carrier}")))
        return str(iri)

    n1 = node("c1", "lumped")
    n2 = node("t1", "diffusion_transport")
    n3 = node("c2", "lumped")
    arc("a1", n1, n2, "token-flow")
    arc("a2", n2, n3, "token-flow")

    r = client.get("/api/instantiate/arc-indices")
    assert r.status_code == 200
    body = r.json()
    by_arc = {a["arc"]: a for a in body["arcs"]}
    diff = _idx("idx_arc_diffusion")
    mass = _idx("idx_arc_mass")
    assert diff in by_arc[f"{base}/ModelArc_a1"]["sub_indices"]
    assert mass in by_arc[f"{base}/ModelArc_a1"]["sub_indices"]
    assert body["by_sub_index"][diff] == [
        f"{base}/ModelArc_a1", f"{base}/ModelArc_a2"]
