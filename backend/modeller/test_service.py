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


def test_referenced_composite_roundtrip(client):
    """§22: refersTo + override map round-trip on the composite; the
    usesModel pin set on the graph IRI is derived on PUT — a stale or
    incomplete client-sent list is ignored."""
    doc = _doc()
    doc["composites"][1]["refersTo"] = "https://example.org/submodel"
    doc["composites"][1]["overrides"] = {
        "species": "https://example.org/scheme-B"}
    doc["usesModel"] = ["https://example.org/stale"]  # ignored on PUT

    r = client.put("/api/modeller/model", json=doc)
    assert r.status_code == 200
    assert r.json()["usesModel"] == ["https://example.org/submodel"]

    got = client.get(f"/api/modeller/model?graph={MODEL}").json()
    by_id = {c["treeId"]: c for c in got["composites"]}
    assert by_id[2]["refersTo"] == "https://example.org/submodel"
    assert by_id[2]["overrides"] == {
        "species": "https://example.org/scheme-B"}
    assert by_id[0]["refersTo"] is None
    assert by_id[0]["overrides"] == {}
    assert got["usesModel"] == ["https://example.org/submodel"]

    # dropping the reference clears the derived pin
    doc["composites"][1]["refersTo"] = None
    doc["composites"][1]["overrides"] = {}
    client.put("/api/modeller/model", json=doc)
    got = client.get(f"/api/modeller/model?graph={MODEL}").json()
    assert got["usesModel"] == []


def test_extract_submodel(client):
    """§22 move semantics: subtree → new artefact; host gets a
    referenced composite; boundary arcs become open arcs on both
    sides; pins are inherited."""
    doc = _doc()
    # grow the doc: a composite (treeId 2) holding Node_2, plus a
    # second arc Node_2 -> Node_1 inside... use the existing shape:
    # composite 2 contains Node_2; Arc_1 Node_1->Node_2 crosses the
    # boundary.
    assert client.put("/api/modeller/model", json=doc).status_code == 200

    r = client.post(f"/api/modeller/extract-submodel?graph={MODEL}",
                    json={"iri": "https://example.org/sub",
                          "treeNodeIds": [2], "label": "Inner"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["iri"] == "https://example.org/sub"
    assert body["movedNodes"] == 1
    assert body["boundaryArcs"] == 1
    comp_id = body["compositeTreeId"]

    # host: Node_2 gone, referenced composite in place, boundary arc
    # stays as an open arc on the new composite
    host = client.get(f"/api/modeller/model?graph={MODEL}").json()
    assert {n["iri"] for n in host["nodes"]} == {"promo:Model/Node_1"}
    assert len(host["arcs"]) == 1  # boundary arc kept (dangling end)
    by_id = {c["treeId"]: c for c in host["composites"]}
    assert by_id[comp_id]["refersTo"] == "https://example.org/sub"
    assert by_id[comp_id]["parentTreeId"] == 0
    open_arc = by_id[comp_id]["openArcs"][0]
    assert open_arc["iri"] == "promo:Arc/Arc_1"
    assert open_arc["externalIri"] == "promo:Model/Node_1"
    assert open_arc["isSource"] is False   # removed end was the target
    # Arc_1 referenceTo = Node_1 (outside) → ref points to external
    assert open_arc["refToExternal"] is True
    assert host["usesModel"] == ["https://example.org/sub"]

    # submodel: Node_2 moved, root composite carries its side of the
    # boundary arc; pins inherited from the host artefact
    sub = client.get(
        "/api/modeller/model?graph=https://example.org/sub").json()
    assert {n["iri"] for n in sub["nodes"]} == {"promo:Model/Node_2"}
    sub_root = {c["treeId"]: c for c in sub["composites"]}[sub["rootTreeId"]]
    assert len(sub_root["openArcs"]) == 1
    s_open = sub_root["openArcs"][0]
    assert s_open["iri"] == "promo:Arc/Arc_1"
    assert s_open["externalIri"] == "promo:Model/Node_2"
    assert s_open["isSource"] is True      # missing end was the source
    assert s_open["refToExternal"] is False  # ref points away from inside
    assert sub["usesSpecies"] == []

    from backend.core.graph_store import PROMO, get_store
    g = get_store().dataset.graph(URIRef("https://example.org/sub"))
    assert (URIRef("https://example.org/sub"), PROMO["usesOntology"],
            URIRef(str(get_store().ONTOLOGY_GRAPH_IRI))) in g


def test_reference_dag_and_cycles(client):
    """§22: /references walks the usesModel DAG and reports
    transitive self-references as reference-cycle loops."""
    store = graph_store.get_store()
    for iri in ("https://example.org/m-a", "https://example.org/m-b"):
        store.create_artefact_graph(iri, "Model")

    def pin(iri, ref):
        doc = {"nodes": [], "arcs": [],
               "composites": [
                   {"treeId": 0, "label": "Root", "parentTreeId": None,
                    "children": [{"id": 1}],
                    "layout": {}, "knots": {}, "openArcs": []},
                   {"treeId": 1, "label": "sub", "parentTreeId": 0,
                    "children": [], "layout": {}, "knots": {},
                    "openArcs": [], "refersTo": ref}],
               "rootTreeId": 0, "nextTreeId": 2, "arcCounter": 1}
        assert client.put(
            f"/api/modeller/model?graph={iri}", json=doc).status_code == 200

    pin("https://example.org/m-a", "https://example.org/m-b")
    pin("https://example.org/m-b", "https://example.org/m-a")

    r = client.get("/api/modeller/references?graph=https://example.org/m-a")
    assert r.status_code == 200
    body = r.json()
    assert body["dag"]["https://example.org/m-a"] == ["https://example.org/m-b"]
    assert body["dag"]["https://example.org/m-b"] == ["https://example.org/m-a"]
    assert body["cycles"] == [
        ["https://example.org/m-a", "https://example.org/m-b",
         "https://example.org/m-a"]]


def test_catalogue_referenced_by(client):
    """The catalogue's referencedBy index lets the hub warn 'N models
    reference this', and delete_artefact blocks on usesModel pins."""
    doc = _doc()
    doc["composites"][1]["refersTo"] = "https://example.org/used"
    client.put("/api/modeller/model", json=doc)
    graph_store.get_store().create_artefact_graph(
        "https://example.org/used", "Model")
    client.put("/api/modeller/model?graph=https://example.org/used",
               json=_doc())

    cat = client.get("/api/catalogue").json()
    used = next(l for l in cat["lines"]
                if l["iri"] == "https://example.org/used")
    assert used["referencedBy"] == [MODEL]
    host = next(l for l in cat["lines"] if l["iri"] == MODEL)
    assert host["usesModel"] == ["https://example.org/used"]

    r = client.delete("/api/catalogue/artefact?iri=https://example.org/used")
    assert r.status_code == 409
    assert MODEL in r.json()["detail"]


def test_dissolve_roundtrip(client):
    """§22: extract then dissolve restores the topology — nodes and
    the boundary arc are whole again, the composite is inline with
    dissolvedFrom provenance."""
    doc = _doc()
    client.put("/api/modeller/model", json=doc)
    client.post(f"/api/modeller/extract-submodel?graph={MODEL}",
                json={"iri": "https://example.org/sub",
                      "treeNodeIds": [2], "label": "Inner"})
    host = client.get(f"/api/modeller/model?graph={MODEL}").json()
    comp_id = next(c["treeId"] for c in host["composites"]
                   if c.get("refersTo"))

    r = client.post(f"/api/modeller/dissolve?graph={MODEL}",
                    json={"treeNodeId": comp_id})
    assert r.status_code == 200, r.text
    assert r.json()["dissolved"] == "https://example.org/sub"

    got = client.get(f"/api/modeller/model?graph={MODEL}").json()
    assert {n["iri"] for n in got["nodes"]} == {
        "promo:Model/Node_1", "promo:Model/Node_2"}
    assert len(got["arcs"]) == 1  # boundary arc, deduplicated by IRI
    by_id = {c["treeId"]: c for c in got["composites"]}
    comp = by_id[comp_id]
    assert comp["refersTo"] is None
    assert comp["dissolvedFrom"] == "https://example.org/sub"
    assert comp["openArcs"] == []
    # the extracted subtree is preserved: comp holds the nested
    # "Inner" composite, which owns Node_2 as a leaf child
    inner_id = comp["children"][0]["id"]
    inner = by_id[inner_id]
    assert inner["parentTreeId"] == comp_id
    assert {ch.get("iri") for ch in inner["children"]} == {
        "promo:Model/Node_2"}
    assert got["usesModel"] == []

    # dissolving an inline composite is a 422
    r = client.post(f"/api/modeller/dissolve?graph={MODEL}",
                    json={"treeNodeId": comp_id})
    assert r.status_code == 422


def test_extract_submodel_rejects(client):
    client.put("/api/modeller/model", json=_doc())
    # the root composite cannot be extracted
    r = client.post(f"/api/modeller/extract-submodel?graph={MODEL}",
                    json={"iri": "https://example.org/x",
                          "treeNodeIds": [0]})
    assert r.status_code == 422
    # non-composite ids are rejected
    r = client.post(f"/api/modeller/extract-submodel?graph={MODEL}",
                    json={"iri": "https://example.org/x",
                          "treeNodeIds": [99]})
    assert r.status_code == 422


def test_instantiation_expands_reference(client):
    """§22 per-occurrence instantiation: the referenced artefact's
    topology joins the host scope under comp/inner instance paths,
    and the boundary arc's dangling end re-points at the occurrence
    instance."""
    client.put("/api/modeller/model", json=_doc())
    client.post(f"/api/modeller/extract-submodel?graph={MODEL}",
                json={"iri": "https://example.org/sub",
                      "treeNodeIds": [2], "label": "Inner"})
    host = client.get(f"/api/modeller/model?graph={MODEL}").json()
    comp_id = next(c["treeId"] for c in host["composites"]
                   if c.get("refersTo"))
    comp_iri = f"{MODEL}/Composite_{comp_id}"

    r = client.get(f"/api/instantiate/incidence?graph={MODEL}")
    assert r.status_code == 200, r.text
    base = r.json()["base"]
    occ_node = f"{comp_iri}/promo:Model/Node_2"
    assert occ_node in base["nodes"]
    # the boundary arc connects host Node_1 to the occurrence instance
    row_nodes = base["nodes"]
    assert "promo:Model/Node_1" in row_nodes
    assert len(base["entries"]) == 2
    touched = {row_nodes[r_] for r_, _, _ in base["entries"]}
    assert touched == {"promo:Model/Node_1", occ_node}

    # cycles report a reference-cycle problem instead of recursing
    store = graph_store.get_store()
    g = store.dataset.graph(URIRef("https://example.org/sub"))
    comp = URIRef("https://example.org/sub/Composite_99")
    g.add((comp, RDF.type, graph_store.PROMO["Composite"]))
    g.add((comp, graph_store.PROMO["refersTo"], URIRef(MODEL)))
    r = client.get(f"/api/instantiate/model?graph={MODEL}")
    assert r.status_code == 200
    kinds = {p["kind"] for p in r.json()["problems"]}
    assert "reference-cycle" in kinds


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
