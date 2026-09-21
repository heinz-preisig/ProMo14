"""Tests for ``backend/core/graph_store.py``."""

from rdflib import URIRef
from rdflib.namespace import RDF

from .graph_store import PROMO, RdfStore

ARTEFACT = "https://example.org/artefact"


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
