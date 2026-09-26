"""Tests for ``backend/core/graph_store.py``."""

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF

from .graph_store import PROMO, RdfStore

ARTEFACT = "https://example.org/artefact"


def _graph_ids(path):
    """Non-empty graph IRIs in a .trig file."""
    probe = Dataset()
    probe.parse(str(path), format="trig")
    return {str(g.identifier) for g in probe.graphs() if len(g)}


def _store_with_equations(tmp_path, eq_ids):
    store = RdfStore(tmp_path)
    g = store.dataset.get_context(URIRef(ARTEFACT))
    store.add_variable_dict(g, {
        "iri": f"{ARTEFACT}#V_1",
        "label": "rho",
        "internal_id": "V_1",
        "network": "thermo",
        "equations": {
            eq_id: {"iri": "", "internal_id": eq_id, "rhs": "a + b"}
            for eq_id in eq_ids
        },
    })
    return store, g


def _equation_ids(g):
    return {
        str(g.value(s, PROMO["internalID"]))
        for s in g.subjects(RDF.type, PROMO["Equation"])
    }


def test_migrate_equation_ids_renumbers_epoch_ids(tmp_path):
    store, g = _store_with_equations(
        tmp_path, ["E_3", "E_1750000000000", "E_1789990282783"],
    )
    store._migrate_equation_ids()
    # E_3 is conforming and stays; the two epoch ids take the smallest
    # free numbers (sorted by IRI: E_1750… < E_1789…).
    assert _equation_ids(g) == {"E_1", "E_2", "E_3"}
    assert store.dirty


def test_migrate_equation_ids_is_idempotent(tmp_path):
    store, g = _store_with_equations(tmp_path, ["E_1750000000000"])
    store._migrate_equation_ids()
    store.dirty = False
    store._migrate_equation_ids()
    assert _equation_ids(g) == {"E_1"}
    assert not store.dirty


def test_migrate_equation_ids_noop_when_conforming(tmp_path):
    store, g = _store_with_equations(tmp_path, ["E_1", "E_2"])
    store._migrate_equation_ids()
    assert _equation_ids(g) == {"E_1", "E_2"}
    assert not store.dirty


def test_migrate_equation_iris_rehomes_promo_namespace(tmp_path):
    """promo#-minted equation IRIs move into the graph's own namespace
    ({graphIRI}#) — promo# is vocabulary only — and object references
    follow, including references from other graphs (assignment
    sequences)."""
    store = RdfStore(tmp_path)
    g = store.dataset.get_context(URIRef(ARTEFACT))
    var = URIRef(f"{ARTEFACT}#V_1")
    old = URIRef(f"{PROMO}E_7")
    g.add((var, RDF.type, PROMO["Variable"]))
    g.add((old, RDF.type, PROMO["Equation"]))
    g.add((old, PROMO["internalID"], Literal("E_7")))
    g.add((var, PROMO["hasEquation"], old))
    # A reference from a different graph (e.g. an assignment artefact).
    other = store.dataset.get_context(URIRef("https://example.org/asg"))
    res = URIRef("https://example.org/asg#a1")
    other.add((res, PROMO["hasBaseEquation"], old))

    store._migrate_equation_iris()

    new = URIRef(f"{ARTEFACT}#E_7")
    assert (new, RDF.type, PROMO["Equation"]) in g
    assert (old, None, None) not in g
    assert (var, PROMO["hasEquation"], new) in g
    assert (var, PROMO["hasEquation"], old) not in g
    assert (res, PROMO["hasBaseEquation"], new) in other
    assert store.dirty


def test_migrate_equation_iris_noop_when_conforming(tmp_path):
    """Equations minted via add_variable_dict already land under the
    artefact's namespace — the migration is a no-op."""
    store, g = _store_with_equations(tmp_path, ["E_1"])
    store._migrate_equation_iris()
    assert not store.dirty
    assert all(str(s).startswith(ARTEFACT)
               for s in g.subjects(RDF.type, PROMO["Equation"]))


def test_migrate_domain_membership_uses_universe_iri(tmp_path):
    store = RdfStore(tmp_path)
    graph = store.ontology_graph
    root = store.mint_iri(graph.identifier, "domain_root")
    physical = store.mint_iri(graph.identifier, "domain_physical")
    variable = store.mint_iri(graph.identifier, "V_1")
    graph.add((root, RDF.type, PROMO["Domain"]))
    graph.add((root, PROMO["name"], Literal("root")))
    graph.add((physical, RDF.type, PROMO["Domain"]))
    graph.add((physical, PROMO["name"], Literal("physical")))
    graph.add((physical, PROMO["parent"], root))
    graph.add((variable, RDF.type, PROMO["Variable"]))
    graph.add((variable, PROMO["network"], Literal("physical")))

    store._migrate_domain_membership()

    universe = store.mint_iri(graph.identifier, "domain_universe")
    assert (universe, RDF.type, PROMO["Domain"]) in graph
    assert graph.value(universe, PROMO["name"]) == Literal("universe")
    assert graph.value(physical, PROMO["parent"]) == universe
    assert graph.value(variable, PROMO["inDomain"]) == physical

    store.dirty = False
    store._migrate_domain_membership()
    assert not store.dirty


def test_save_fans_out_per_artefact_line(tmp_path):
    """Hub #4: save() writes one .trig per artefact line — the draft
    plus its frozen versions — named by the line IRI's last segment."""
    store = RdfStore(tmp_path)
    store.load()  # seeds the ontology line
    store.create_artefact_graph(
        "https://example.org/lib", "Library", label="lib",
        uses=[str(store.ONTOLOGY_GRAPH_IRI)])
    store.freeze_version("1.0", "https://example.org/lib")
    store.save()

    ont = tmp_path / "ontology.trig"
    lib = tmp_path / "lib.trig"
    assert ont.is_file() and lib.is_file()
    # ontology.trig holds only the ontology line; lib.trig holds the
    # draft plus its frozen version ("the file is the history").
    assert _graph_ids(ont) == {str(store.ONTOLOGY_GRAPH_IRI)}
    assert _graph_ids(lib) == {
        "https://example.org/lib", "https://example.org/lib/1.0"}
    assert not store.dirty


def test_load_splits_legacy_single_file(tmp_path):
    """Hub #4 migration: an ontology.trig holding the whole dataset is
    split into per-line files on first load."""
    store = RdfStore(tmp_path)
    store.load()
    store.create_artefact_graph("https://example.org/m", "Model")
    store.save("ontology.trig")  # legacy whole-dataset layout
    assert not (tmp_path / "m.trig").exists()

    fresh = RdfStore(tmp_path)
    fresh.load()
    assert (tmp_path / "m.trig").is_file()
    assert _graph_ids(tmp_path / "ontology.trig") == \
        {str(store.ONTOLOGY_GRAPH_IRI)}
    # the model graph survived the split
    assert len(fresh.dataset.graph(URIRef("https://example.org/m")))


def test_save_removes_stale_line_files(tmp_path):
    """A .trig whose line no longer exists is removed on save."""
    store = RdfStore(tmp_path)
    store.load()
    stale = tmp_path / "ghost.trig"
    stale.write_text(
        "<https://example.org/ghost> { "
        "<https://example.org/ghost> a <urn:x> }")
    store.save()
    assert not stale.exists()
