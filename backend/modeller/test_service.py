"""Tests for the modeller model persistence endpoints (ADR-007)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rdflib import RDF, Literal, URIRef
from backend.core import graph_store
from backend.main import app
from backend.testing import GraphClient


MODEL = "https://example.org/test-model"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    """Yield a ``GraphClient`` bound to a fresh ``promo:Model`` artefact
    in a temp-dir store — ``/api/catalogue/new`` saves immediately, so
    an un-isolated store would leak test artefacts into the tracked
    ``data/ontology.trig``."""
    monkeypatch.setenv("PROMO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(graph_store, "_STORE", None)
    with GraphClient(app) as c:
        store = graph_store.get_store()
        store.create_artefact_graph(
            MODEL, "Model", label="test model",
            uses=[str(store.ONTOLOGY_GRAPH_IRI)])
        c.graph_iri = MODEL
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
    r = client.get(f"/api/modeller/model?graph={MODEL}")
    assert r.status_code == 200
    doc = r.json()
    assert doc["nodes"] == [] and doc["arcs"] == [] and doc["composites"] == []


def test_put_get_roundtrip(client):
    doc = _doc()
    assert client.put("/api/modeller/model", json=doc).status_code == 200

    got = client.get(f"/api/modeller/model?graph={MODEL}").json()
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
    got = client.get(f"/api/modeller/model?graph={MODEL}").json()
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
    got = client.get(f"/api/modeller/model?graph={MODEL}").json()
    assert got["speciesAliases"] == doc["speciesAliases"]

    # second PUT without aliases clears them
    client.put("/api/modeller/model", json=_doc())
    got = client.get(f"/api/modeller/model?graph={MODEL}").json()
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


def test_put_rejects_uncreated_graph(client):
    """Hub #3: a write must not materialize an artefact — ``?graph=``
    naming a graph that was never created via ``/api/catalogue/new``
    or ``/fork`` gets a 404, so the type marker and ``usesOntology``
    pins are always born at creation."""
    iri = "https://example.org/never-created"
    r = client.put(f"/api/modeller/model?graph={iri}", json=_doc())
    assert r.status_code == 404
    assert "no such artefact" in r.json()["detail"]


def test_behaviour_entity_types_from_pinned_library(client):
    store = graph_store.get_store()
    library = "https://example.org/library"
    assignments_iri = library + "/assignments"
    store.create_artefact_graph(
        library, "Library", uses=[str(store.ONTOLOGY_GRAPH_IRI)]
    )
    model_graph = store.dataset.graph(URIRef(MODEL))
    model_graph.add((
        URIRef(MODEL), graph_store.PROMO["usesLibrary"], URIRef(library)
    ))
    model_graph.add((
        URIRef(MODEL), graph_store.PROMO["usesAssignment"],
        URIRef(assignments_iri)
    ))
    store.create_artefact_graph(
        assignments_iri, "Assignment",
        uses=[str(store.ONTOLOGY_GRAPH_IRI)], uses_library=[library],
    )
    assignments = store.dataset.graph(URIRef(assignments_iri))
    for name, entity_type, closed in (
        ("defined", "https://example.org/entity/defined", True),
        ("unfinished", "https://example.org/entity/unfinished", False),
    ):
        resource = URIRef(f"{assignments_iri}#{name}")
        assignments.add((
            resource, RDF.type, graph_store.PROMO["BehaviourAssignment"]
        ))
        assignments.add((
            resource, graph_store.PROMO["forEntityType"], URIRef(entity_type)
        ))
        assignments.add((
            resource, graph_store.PROMO["closed"], Literal(closed)
        ))

    response = client.get(
        f"/api/modeller/behaviour-entity-types?graph={MODEL}"
    )

    assert response.status_code == 200
    assert response.json() == ["https://example.org/entity/defined"]


# --- §20 gesture admissibility -------------------------------------------------

ONTO = "https://w3id.org/promo/ontology"
ET_ENV = f"{ONTO}#etype_environment"       # species_source
ET_LUMPED = f"{ONTO}#etype_lumped"         # reaction_host
ET_CONV = f"{ONTO}#etype_convection_transport"  # species_transport (via parent)
ALLOC = "https://example.org/scheme#feed"
RXN = "https://example.org/scheme#r1"
COMPONENT = "https://example.org/scheme#H2O"


def _species_doc(env_alloc=None, env_rxns=None, lump_alloc=None,
                 lump_rxns=None, arc_perm=None, conv_endpoint=False):
    """Minimal model: an Environment and a Lumped tank (optionally a
    Convection pipe on the arc endpoint) with §20 gestures."""
    nodes = [
        {"iri": "promo:Model/Env", "entityType": ET_ENV,
         "label": "Environment",
         "speciesAllocation": env_alloc, "reactions": env_rxns or []},
        {"iri": "promo:Model/Tank", "entityType": ET_LUMPED,
         "label": "Tank",
         "speciesAllocation": lump_alloc, "reactions": lump_rxns or []},
    ]
    target = "promo:Model/Tank"
    if conv_endpoint:
        nodes.append({"iri": "promo:Model/Pipe", "entityType": ET_CONV,
                      "label": "Pipe"})
        target = "promo:Model/Pipe"
    doc = _doc()
    doc["nodes"] = nodes
    doc["arcs"] = [{"iri": "promo:Arc/Arc_1", "sourceIri": "promo:Model/Env",
                    "targetIri": target, "arcType": "promo:ArcType/token-flow",
                    "permeable": arc_perm}]
    return doc


def test_species_gesture_admissibility(client):
    """PUT /model enforces the ontology capability gates — a rejected
    document leaves the graph untouched."""
    # Admissible baseline: allocation on environment, reaction on a
    # capacity, permeability on an arc touching species transport.
    r = client.put("/api/modeller/model", json=_species_doc(
        env_alloc=ALLOC, lump_rxns=[RXN], arc_perm=[COMPONENT],
        conv_endpoint=True))
    assert r.status_code == 200

    # Reactions on the environment → no reaction_host.
    r = client.put("/api/modeller/model",
                   json=_species_doc(env_rxns=[RXN]))
    assert r.status_code == 422
    assert "reaction_host" in r.json()["detail"]

    # Allocation on a capacity → no species_source.
    r = client.put("/api/modeller/model",
                   json=_species_doc(lump_alloc=ALLOC))
    assert r.status_code == 422
    assert "species_source" in r.json()["detail"]

    # Permeability between two non-transport endpoints → no
    # species_transport.
    r = client.put("/api/modeller/model",
                   json=_species_doc(arc_perm=[COMPONENT]))
    assert r.status_code == 422
    assert "species_transport" in r.json()["detail"]


def test_instantiation_reports_inadmissible_gestures(client):
    """The /model report flags persisted gesture violations — the safety
    net for artefacts that bypassed the save gate."""
    store = graph_store.get_store()
    g = store.dataset.graph(URIRef(MODEL))
    node = URIRef("promo:Model/Env")
    g.add((node, RDF.type, graph_store.PROMO["ModelNode"]))
    g.add((node, graph_store.PROMO["entityType"], URIRef(ET_ENV)))
    g.add((node, graph_store.PROMO["hostsReaction"], URIRef(RXN)))

    r = client.get(f"/api/instantiate/model?graph={MODEL}")
    assert r.status_code == 200
    kinds = {p["kind"] for p in r.json()["problems"]}
    assert "inadmissible-gesture" in kinds
