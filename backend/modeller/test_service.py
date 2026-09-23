"""Tests for the modeller model persistence endpoints (ADR-007)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core import graph_store
from backend.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    """Yield a ``TestClient`` backed by a fresh store in a temp dir —
    ``/api/catalogue/new`` saves immediately, so an un-isolated store
    would leak test artefacts into the tracked ``data/ontology.trig``."""
    monkeypatch.setenv("PROMO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(graph_store, "_STORE", None)
    with TestClient(app) as c:
        yield c
    monkeypatch.setattr(graph_store, "_STORE", None)


def _doc():
    return {
        "nodes": [
            {"iri": "promo:Model/Node_1", "entityType": "promo:EntityType/capacity", "label": "Reactor"},
            {"iri": "promo:Model/Node_2", "entityType": "promo:EntityType/capacity", "label": "Tank"},
        ],
        "arcs": [
            {"iri": "promo:Arc/Arc_1", "sourceIri": "promo:Model/Node_1",
             "targetIri": "promo:Model/Node_2", "arcType": "promo:ArcType/token-flow",
             "referenceFrom": "promo:Model/Node_2",
             "referenceTo": "promo:Model/Node_1"},
        ],
        "composites": [
            {"treeId": 0, "label": "Root", "parentTreeId": None,
             "children": [{"id": 1, "iri": "promo:Model/Node_1"}, {"id": 2}],
             "layout": {"1": {"x": 0.0, "y": 0.0}, "2": {"x": 100.0, "y": 50.0}},
             "knots": {"promo:Arc/Arc_1": [{"x": 10.0, "y": 20.0}]},
             "openArcs": []},
            {"treeId": 2, "label": "Group", "parentTreeId": 0,
             "children": [{"id": 3, "iri": "promo:Model/Node_2"}],
             "layout": {"3": {"x": 5.0, "y": 5.0}}, "knots": {},
             "openArcs": [{"iri": "promo:Arc/Arc_9", "externalIri": "promo:Model/Node_1",
                           "arcType": "promo:ArcType/token-flow", "isSource": True,
                           "refToExternal": True}]},
        ],
        "rootTreeId": 0, "nextTreeId": 4, "arcCounter": 2,
    }


def test_empty_model(client):
    r = client.get("/api/modeller/model")
    assert r.status_code == 200
    doc = r.json()
    assert doc["nodes"] == [] and doc["arcs"] == [] and doc["composites"] == []


def test_put_get_roundtrip(client):
    doc = _doc()
    assert client.put("/api/modeller/model", json=doc).status_code == 200

    got = client.get("/api/modeller/model").json()
    assert {n["iri"] for n in got["nodes"]} == {"promo:Model/Node_1", "promo:Model/Node_2"}
    assert got["rootTreeId"] == 0
    assert got["nextTreeId"] == 4
    assert got["arcCounter"] == 2

    by_id = {c["treeId"]: c for c in got["composites"]}
    assert by_id[2]["parentTreeId"] == 0
    assert by_id[0]["children"] == [
        {"id": 1, "iri": "promo:Model/Node_1"}, {"id": 2, "iri": None}]
    assert by_id[0]["layout"]["2"] == {"x": 100.0, "y": 50.0}
    assert by_id[0]["knots"]["promo:Arc/Arc_1"] == [{"x": 10.0, "y": 20.0}]
    assert by_id[2]["openArcs"][0]["externalIri"] == "promo:Model/Node_1"

    # §15: reference direction persists on the arc, refToExternal on the
    # open arc (JSON literal inside the Composite).
    arc = got["arcs"][0]
    assert arc["referenceFrom"] == "promo:Model/Node_2"
    assert arc["referenceTo"] == "promo:Model/Node_1"
    assert by_id[2]["openArcs"][0]["refToExternal"] is True


def test_put_replaces(client):
    """A second PUT wipes the previous model content."""
    client.put("/api/modeller/model", json=_doc())
    client.put("/api/modeller/model", json={
        "nodes": [], "arcs": [], "composites": [
            {"treeId": 0, "label": "Root", "parentTreeId": None,
             "children": [], "layout": {}, "knots": {}, "openArcs": []}],
        "rootTreeId": 0, "nextTreeId": 1, "arcCounter": 1})
    got = client.get("/api/modeller/model").json()
    assert got["nodes"] == [] and got["arcs"] == []
    assert len(got["composites"]) == 1


def test_species_aliases(client):
    """§20: the model-local alias map (Component IRI → name) round-trips
    and is wiped with the document — its subjects are external IRIs, so
    the typed-subject wipe alone would leave stale aliases behind."""
    doc = _doc()
    doc["speciesAliases"] = {
        "http://example.org/species#A": "H2O",
        "http://example.org/species#B": "NaCl",
    }
    assert client.put("/api/modeller/model", json=doc).status_code == 200
    got = client.get("/api/modeller/model").json()
    assert got["speciesAliases"] == doc["speciesAliases"]

    # second PUT without aliases clears them
    client.put("/api/modeller/model", json=_doc())
    got = client.get("/api/modeller/model").json()
    assert got["speciesAliases"] == {}


def test_uses_species_pin(client):
    """§20: the artefact's usesSpecies pin round-trips through the
    document, and PUT preserves the graph IRI's self-description —
    the artefact type marker and other pins live on the graph IRI,
    which is itself typed promo:Model and so inside the wipe set."""
    from rdflib import RDF, URIRef
    from backend.core.graph_store import PROMO, get_store

    iri = "https://example.org/model-pin-test"
    assert client.post("/api/catalogue/new", json={
        "iri": iri, "type": "model",
        "uses": ["https://w3id.org/promo/ontology"],
        "uses_species": ["https://example.org/scheme"]}).status_code == 200

    doc = _doc()
    doc["usesSpecies"] = ["https://example.org/scheme"]
    r = client.put(f"/api/modeller/model?graph={iri}", json=doc)
    assert r.status_code == 200

    got = client.get(f"/api/modeller/model?graph={iri}").json()
    assert got["usesSpecies"] == ["https://example.org/scheme"]

    # graph-IRI self-description survived the PUT wipe
    g = get_store().dataset.graph(URIRef(iri))
    gid = g.identifier
    assert (gid, RDF.type, PROMO["Model"]) in g
    assert (gid, PROMO["usesOntology"],
            URIRef("https://w3id.org/promo/ontology")) in g

    # doc without the pin clears it (whole-document semantics)
    client.put(f"/api/modeller/model?graph={iri}", json=_doc())
    got = client.get(f"/api/modeller/model?graph={iri}").json()
    assert got["usesSpecies"] == []
