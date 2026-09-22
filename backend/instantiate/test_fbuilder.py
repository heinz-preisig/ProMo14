"""Tests for the §15 F-builder (signed node–arc incidence matrices).

Engine tests run on plain dicts; the endpoint test seeds a small model
(capacity —arc— diffusion transport —arc— capacity) into a throwaway
store and checks the emitted matrices.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rdflib import RDF, RDFS, Literal, URIRef

from backend.core import graph_store
from backend.core.graph_store import PROMO
from backend.instantiate.fbuilder import build
from backend.instantiate.resolver import (
    ArcInfo,
    NodeInfo,
    SubIndexInfo,
    resolve,
)
from backend.main import app

BASE = "https://w3id.org/promo/ontology"


def _et(frag: str) -> str:
    return f"{BASE}#etype_{frag}"


def _idx(frag: str) -> str:
    return f"{BASE}#{frag}"


PARENTS = {
    _et("mass_transport"): _et("transport_system"),
    _et("diffusion_transport"): _et("mass_transport"),
    _et("heat_transport"): _et("energy_transport"),
    _et("energy_transport"): _et("transport_system"),
}

SUB_INDICES = {
    _idx("idx_arc_mass"): SubIndexInfo(
        _idx("idx_arc_mass"), _idx("idx_arc"), _et("mass_transport"),
        "A_mass"),
    _idx("idx_arc_diffusion"): SubIndexInfo(
        _idx("idx_arc_diffusion"), _idx("idx_arc"),
        _et("diffusion_transport"), "A_diff"),
}


def _build(nodes, arcs, sub_indices=SUB_INDICES):
    memberships = resolve(nodes, arcs, sub_indices, PARENTS)
    return build(nodes, arcs, memberships, sub_indices)


def _dense(m):
    """Expand a sparse Incidence into a dense dict {(node, arc): sign}."""
    return {
        (m.nodes[r], m.arcs[c]): s for r, c, s in m.entries
    }


def test_base_matrix_signs_follow_reference_direction():
    """+1 at reference_to, -1 at reference_from; draw order default."""
    nodes = {
        "n1": NodeInfo("n1", _et("lumped")),
        "n2": NodeInfo("n2", _et("diffusion_transport")),
        "n3": NodeInfo("n3", _et("lumped")),
    }
    arcs = {
        # a1: n1 → n2 (draw order); a2: reversed — ref n3 → n2.
        "a1": ArcInfo("a1", "n1", "n2", "token-flow"),
        "a2": ArcInfo("a2", "n2", "n3", "token-flow",
                      reference_from="n3", reference_to="n2"),
    }
    rep = _build(nodes, arcs)
    base = _dense(rep.base)
    assert rep.base.arcs == ["a1", "a2"]
    assert rep.base.nodes == ["n1", "n2", "n3"]
    # a1: out of n1, into n2
    assert base[("n1", "a1")] == -1
    assert base[("n2", "a1")] == +1
    # a2: reversed — out of n3, into n2 (draw order n2→n3 ignored)
    assert base[("n3", "a2")] == -1
    assert base[("n2", "a2")] == +1
    assert ("n2", "a2") in base and ("n1", "a2") not in base


def test_sub_index_matrices_restrict_columns():
    """F_diff has only diffusion-member arcs as columns."""
    nodes = {
        "n1": NodeInfo("n1", _et("lumped")),
        "n2": NodeInfo("n2", _et("diffusion_transport")),
        "n3": NodeInfo("n3", _et("heat_transport")),
        "n4": NodeInfo("n4", _et("lumped")),
    }
    arcs = {
        "a1": ArcInfo("a1", "n1", "n2", "token-flow"),   # diffusion
        "a2": ArcInfo("a2", "n3", "n4", "token-flow"),   # heat
    }
    rep = _build(nodes, arcs)
    by_index = {m.index: m for m in rep.sub_indices}
    diff = by_index[_idx("idx_arc_diffusion")]
    assert diff.short_name == "A_diff"
    assert diff.arcs == ["a1"]
    assert _dense(diff) == {("n1", "a1"): -1, ("n2", "a1"): +1}
    mass = by_index[_idx("idx_arc_mass")]
    assert mass.arcs == ["a1"]          # diffusion ⊂ mass
    # base covers both token-flow arcs
    assert rep.base.arcs == ["a1", "a2"]


def test_reference_arcs_excluded_from_base():
    nodes = {
        "n1": NodeInfo("n1", _et("lumped")),
        "n2": NodeInfo("n2", _et("diffusion_transport")),
    }
    arcs = {
        "a1": ArcInfo("a1", "n1", "n2", "token-flow"),
        "a2": ArcInfo("a2", "n1", "n2", "reference"),
    }
    rep = _build(nodes, arcs)
    assert rep.base.arcs == ["a1"]


def test_dangling_arc_is_skipped():
    nodes = {"n1": NodeInfo("n1", _et("lumped"))}
    arcs = {"a1": ArcInfo("a1", "n1", None, "token-flow")}
    rep = _build(nodes, arcs)
    assert rep.skipped == ["a1"]
    assert _dense(rep.base) == {}   # no half-signed column


def test_self_loop_emits_both_signs():
    nodes = {"n1": NodeInfo("n1", _et("lumped"))}
    arcs = {"a1": ArcInfo("a1", "n1", "n1", "token-flow")}
    rep = _build(nodes, arcs)
    assert sorted(rep.base.entries) == [(0, 0, -1), (0, 0, +1)]


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


def test_incidence_endpoint(client):
    """capacity —a1→ diffusion —a2→ capacity, a2 reversed (ref c2→t1)."""
    store = graph_store.get_store()
    g = store.ontology_graph
    base = str(store.ONTOLOGY_GRAPH_IRI)

    def node(frag, et_frag, label):
        iri = URIRef(f"{base}/ModelNode_{frag}")
        g.add((iri, RDF.type, PROMO["ModelNode"]))
        g.add((iri, PROMO["entityType"], URIRef(_et(et_frag))))
        g.add((iri, RDFS.label, Literal(label)))
        return str(iri)

    def arc(frag, src, tgt, carrier, rf=None, rt=None):
        iri = URIRef(f"{base}/ModelArc_{frag}")
        g.add((iri, RDF.type, PROMO["ModelArc"]))
        g.add((iri, PROMO["source"], URIRef(src)))
        g.add((iri, PROMO["target"], URIRef(tgt)))
        g.add((iri, PROMO["arcType"], Literal(f"promo:ArcType/{carrier}")))
        if rf:
            g.add((iri, PROMO["referenceFrom"], URIRef(rf)))
        if rt:
            g.add((iri, PROMO["referenceTo"], URIRef(rt)))
        return str(iri)

    n1 = node("c1", "lumped", "C1")
    n2 = node("t1", "diffusion_transport", "T")
    n3 = node("c2", "lumped", "C2")
    arc("a1", n1, n2, "token-flow")
    arc("a2", n2, n3, "token-flow", rf=n3, rt=n2)   # reversed

    r = client.get("/api/instantiate/incidence")
    assert r.status_code == 200
    body = r.json()

    b = body["base"]
    assert b["arcs"] == [f"{base}/ModelArc_a1", f"{base}/ModelArc_a2"]
    assert b["nodes"] == [n1, n3, n2]   # sorted by IRI: c1 < c2 < t1
    dense = {(b["nodes"][r], b["arcs"][c]): s for r, c, s in b["entries"]}
    # a1: c1 → T; a2 reversed: c2 → T  (through-path)
    assert dense[(n1, f"{base}/ModelArc_a1")] == -1
    assert dense[(n2, f"{base}/ModelArc_a1")] == +1
    assert dense[(n3, f"{base}/ModelArc_a2")] == -1
    assert dense[(n2, f"{base}/ModelArc_a2")] == +1
    # transport row sums to +2 → net inflow convention holds
    assert body["labels"][n1] == "C1"
    assert body["labels"][_idx("idx_arc_diffusion")] == "A_diff"

    subs = {m["index"]: m for m in body["sub_indices"]}
    assert subs[_idx("idx_arc_diffusion")]["arcs"] == [
        f"{base}/ModelArc_a1", f"{base}/ModelArc_a2"]
