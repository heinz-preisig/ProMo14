import json

import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import RDF

from backend.core import graph_store
from backend.core.graph_store import PROMO
from backend.main import app
from backend.testing import GraphClient


BASE = 'https://w3id.org/promo/ontology'


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('PROMO_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(graph_store, '_STORE', None)
    with GraphClient(app, graph_iri=BASE) as client:
        yield client
    monkeypatch.setattr(graph_store, '_STORE', None)


def add(client, tag, rhs=None, **over):
    v = dict(iri=f'{BASE}#{tag}', label=tag, internal_id=tag,
             network='universe', units=[0] * 8, tokens=[f'{BASE}#token_mass'],
             token_vector={'mass': 1})
    if rhs is not None:
        eid = 'E_' + tag
        v['equations'] = {eid: dict(iri=f'{BASE}#{eid}', internal_id=eid,
                                   lhs=v['iri'], rhs=rhs, network='universe')}
    v.update(over)
    r = client.post('/api/equation/variables', json=v)
    assert r.status_code == 200, r.text
    return r.json()


def report(client, graph=BASE):
    r = client.get('/api/equation/consistency', params={'graph': graph})
    assert r.status_code == 200, r.text
    return r.json()


def row(report, label):
    return next(r for r in report['equations'] if r['label'] == label)


def test_report_classifies_structural_errors_and_is_read_only(client):
    add(client, 'a')
    add(client, 'good', 'a')
    add(client, 'different_metadata', 'a', token_vector={'energy': 1})
    add(client, 'unknown', tokens=[], token_vector=None)
    add(client, 'no_signature', 'unknown')
    add(client, 'broken', 'does_not_exist')
    add(client, 'badunits', 'a', units=[1, 0, 0, 0, 0, 0, 0, 0])
    add(client, 'badindices', 'a', index_structures=[f'{BASE}#idx_node'])
    store = graph_store.get_store()
    before = set(store.dataset.quads())
    store.dirty = False
    out = report(client)
    assert out['summary'] == dict(consistent=3, error=3)
    assert row(out, 'different_metadata')['status'] == 'consistent'
    assert row(out, 'no_signature')['status'] == 'consistent'
    assert row(out, 'broken')['status'] == 'error'
    assert row(out, 'badunits')['findings'][0]['code'] == 'units_mismatch'
    assert row(out, 'badindices')['findings'][0]['code'] == 'indices_mismatch'
    assert all('tokens' not in r['declared'] for r in out['equations'])
    assert set(store.dataset.quads()) == before
    assert store.dirty is False
    assert report(client)['revision'] == out['revision']


def test_pinned_scope_report_does_not_shadow_owning_graph(client):
    add(client, 'a')
    add(client, 'output', 'a')
    store = graph_store.get_store()
    library = 'https://example.org/library'
    graph = store.graph(library)
    graph.add((URIRef(library), RDF.type, PROMO['Library']))
    graph.add((URIRef(library), PROMO['usesOntology'], URIRef(BASE)))
    unrelated = store.graph('https://example.org/unrelated')
    unrelated.add((URIRef('https://example.org/unrelated#v'), RDF.type, PROMO['Variable']))
    out = report(client, library)
    assert len(out['equations']) == 1
    assert row(out, 'output')['graphs'] == [BASE]
    assert not list(graph.triples((URIRef(f'{BASE}#output'), None, None)))


def test_reordered_indices_not_a_structural_mismatch(client):
    indices = [f'{BASE}#idx_node', f'{BASE}#idx_species']
    add(client, 'a', index_structures=indices)
    add(client, 'permuted', 'a', index_structures=indices[::-1])
    assert row(report(client), 'permuted')['status'] == 'consistent'


def test_token_signature_fix_endpoint_removed(client):
    assert client.post('/api/equation/consistency/fix', json={}).status_code in (404, 405)
