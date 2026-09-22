"""Roundtrip test for the species artefact service (§20)."""

from fastapi.testclient import TestClient

from backend.core.graph_store import get_store
from backend.main import app

client = TestClient(app)


_n = [0]


def _fresh_species_graph() -> str:
    """Mint a unique Species artefact graph and return its IRI."""
    store = get_store()
    _n[0] += 1
    iri = store.mint_iri("https://example.org/test",
                         "species_doc_%d" % _n[0])
    store.create_artefact_graph(iri, "Species", label="test species")
    return str(iri)


def test_species_roundtrip():
    graph = _fresh_species_graph()
    doc = {
        "components": [
            {"iri": f"{graph}/Component_A", "label": "A"},
            {"iri": f"{graph}/Component_B", "label": "B"},
            {"iri": f"{graph}/Component_C", "label": "C"},
        ],
        "allocations": [
            {"iri": f"{graph}/Allocation_feed", "label": "feed",
             "members": [f"{graph}/Component_A", f"{graph}/Component_B"]},
        ],
        "reactions": [
            {"iri": f"{graph}/Reaction_r1", "label": "r1",
             "reactants": [f"{graph}/Component_A", f"{graph}/Component_B"],
             "products": [f"{graph}/Component_C"]},
        ],
    }
    r = client.put("/api/species/species",
                   params={"graph": graph}, json=doc)
    assert r.status_code == 200, r.text

    r = client.get("/api/species/species", params={"graph": graph})
    assert r.status_code == 200, r.text
    out = r.json()

    comps = {c["iri"]: c["label"] for c in out["components"]}
    assert comps == {f"{graph}/Component_A": "A",
                     f"{graph}/Component_B": "B",
                     f"{graph}/Component_C": "C"}

    alloc = {a["iri"]: a for a in out["allocations"]}
    assert alloc[f"{graph}/Allocation_feed"]["members"] == [
        f"{graph}/Component_A", f"{graph}/Component_B"]

    rxn = {x["iri"]: x for x in out["reactions"]}
    assert rxn[f"{graph}/Reaction_r1"]["reactants"] == [
        f"{graph}/Component_A", f"{graph}/Component_B"]
    assert rxn[f"{graph}/Reaction_r1"]["products"] == [
        f"{graph}/Component_C"]


def test_species_artefact_type_in_catalogue():
    """A Species graph classifies as ``species`` in the catalogue."""
    graph = _fresh_species_graph()
    r = client.get("/api/catalogue")
    assert r.status_code == 200
    lines = r.json()["lines"]
    match = [l for l in lines if l["iri"] == graph]
    assert match and match[0]["type"] == "species"
