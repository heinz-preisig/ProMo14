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


def fix_request(report, label, action='adopt_derived', variable=None):
    r = row(report, label)
    return dict(revision=report['revision'], equation=r['equation'],
                variable=variable or r['variable'], action=action)


def test_report_classifies_and_is_read_only(client):
    add(client, 'a')
    add(client, 'good', 'a')
    add(client, 'stale', 'a', token_vector={'energy': 1})
    add(client, 'unknown', tokens=[], token_vector=None)
    add(client, 'untracked', 'unknown')
    add(client, 'broken', 'does_not_exist')
    add(client, 'badunits', 'a', units=[1, 0, 0, 0, 0, 0, 0, 0])
    add(client, 'badindices', 'a', index_structures=[f'{BASE}#idx_node'])
    store = graph_store.get_store()
    before = set(store.dataset.quads())
    store.dirty = False
    out = report(client)
    assert out['summary'] == dict(consistent=1, advisory=1, untracked=1, error=3)
    assert row(out, 'good')['status'] == 'consistent'
    assert row(out, 'untracked')['status'] == 'untracked'
    assert row(out, 'untracked')['operands'][0]['tokens'] is None
    assert row(out, 'broken')['status'] == 'error'
    assert row(out, 'badunits')['findings'][0]['code'] == 'units_mismatch'
    assert row(out, 'badindices')['findings'][0]['code'] == 'indices_mismatch'
    assert set(store.dataset.quads()) == before
    assert store.dirty is False
    assert report(client)['revision'] == out['revision']


def test_fix_only_writes_signature_and_rechecks(client):
    add(client, 'a')
    add(client, 'stale', 'a', token_vector={'energy': 1})
    add(client, 'consumer', 'stale')
    out = report(client)
    store = graph_store.get_store()
    graph = store.ontology_graph
    before = set(graph)
    response = client.post('/api/equation/consistency/fix', json=fix_request(out, 'stale'))
    assert response.status_code == 200, response.text
    assert row(response.json(), 'stale')['status'] == 'consistent'
    assert row(response.json(), 'consumer')['status'] == 'consistent'
    changed = before.symmetric_difference(set(graph))
    assert len(changed) == 2
    assert all(s == URIRef(f'{BASE}#stale') and p == PROMO['tokenVector'] for s, p, _ in changed)
    assert store.dirty


def test_stale_and_forged_fixes_rejected(client):
    add(client, 'a')
    add(client, 'stale', 'a', token_vector={'energy': 1})
    out = report(client)
    r = client.post('/api/equation/consistency/fix', json=fix_request(out, 'stale', action='rewrite_equation'))
    assert r.status_code == 400
    add(client, 'a', token_vector={'momentum': 1})
    r = client.post('/api/equation/consistency/fix', json=fix_request(out, 'stale'))
    assert r.status_code == 409
    assert 'out of date' in r.text


@pytest.mark.parametrize('frozen_equation', [False, True])
def test_frozen_correction_blocked(client, frozen_equation):
    add(client, 'a')
    add(client, 'stale', 'a', token_vector={'energy': 1}, frozen=not frozen_equation)
    if frozen_equation:
        graph_store.get_store().ontology_graph.set((URIRef(f'{BASE}#E_stale'), PROMO['frozen'], Literal(True)))
    out = report(client)
    fixes = row(out, 'stale')['findings'][0]['fixes']
    assert fixes[0]['blocked']
    r = client.post('/api/equation/consistency/fix', json=fix_request(out, 'stale'))
    assert r.status_code == 409


def test_pinned_scope_report_does_not_shadow_owning_graph(client):
    add(client, 'a')
    add(client, 'stale', 'a', token_vector={'energy': 1})
    store = graph_store.get_store()
    library = 'https://example.org/library'
    graph = store.graph(library)
    graph.add((URIRef(library), RDF.type, PROMO['Library']))
    graph.add((URIRef(library), PROMO['usesOntology'], URIRef(BASE)))
    unrelated = store.graph('https://example.org/unrelated')
    unrelated.add((URIRef('https://example.org/unrelated#v'), RDF.type, PROMO['Variable']))
    out = report(client, library)
    assert len(out['equations']) == 1
    r = row(out, 'stale')
    assert r['graphs'] == [BASE]
    assert r['findings'][0]['fixes'][0]['blocked']
    response = client.post('/api/equation/consistency/fix', params={'graph': library}, json=fix_request(out, 'stale'))
    assert response.status_code == 409
    assert not list(graph.triples((URIRef(f'{BASE}#stale'), None, None)))


def test_sum_mismatch_identifies_operands(client):
    add(client, 'a')
    add(client, 'b', token_vector={'energy': 1})
    add(client, 'sum', 'a + b')
    r = row(report(client), 'sum')
    assert r['status'] == 'advisory'
    assert {v['label']: v['tokens'] for v in r['operands']} == {'a': {'mass': 1}, 'b': {'energy': 1}}
    assert any('mismatch in sum' in f['message'] for f in r['findings'])
    assert r['conflicts'] == [[{'expression': 'a', 'tokens': {'mass': 1}},
                                {'expression': 'b', 'tokens': {'energy': 1}}]]


def test_explicit_empty_lhs_mismatch_and_neutral_fix(client):
    add(client, 'a')
    add(client, 'empty_lhs', 'a', token_vector={})
    out = report(client)
    assert row(out, 'empty_lhs')['status'] == 'advisory'
    assert row(out, 'empty_lhs')['findings'][0]['code'] == 'token_signature_mismatch'
    add(client, 'ratio', 'a . inv(a)', token_vector={})
    out = report(client)
    req = fix_request(out, 'ratio', 'clear_signature', f'{BASE}#a')
    response = client.post('/api/equation/consistency/fix', json=req)
    assert response.status_code == 200, response.text
    raw = graph_store.get_store().ontology_graph.value(URIRef(f'{BASE}#a'), PROMO['tokenVector'])
    assert json.loads(str(raw)) == {}
    assert row(response.json(), 'empty_lhs')['derived']['tokens'] == {}


def test_frozen_graph_and_missing_graph_write_guards(client):
    add(client, 'a')
    add(client, 'stale', 'a', token_vector={'energy': 1})
    out = report(client)
    client.graph_iri = None
    response = client.post('/api/equation/consistency/fix', json=fix_request(out, 'stale'))
    assert response.status_code == 400
    graph_store.get_store().ontology_graph.add((URIRef(BASE), RDF.type, PROMO['Version']))
    out = report(client)
    response = client.post('/api/equation/consistency/fix', params={'graph': BASE}, json=fix_request(out, 'stale'))
    assert response.status_code == 403


def test_no_membership_is_not_silently_added(client):
    add(client, 'a')
    add(client, 'missing', 'a', tokens=[], token_vector=None)
    out = report(client)
    finding = next(f for f in row(out, 'missing')['findings'] if f['code'] == 'missing_signature')
    assert finding['fixes'][0]['blocked']
    response = client.post('/api/equation/consistency/fix', json=fix_request(out, 'missing'))
    assert response.status_code == 409


def test_reordered_indices_not_a_structural_mismatch(client):
    indices = [f'{BASE}#idx_node', f'{BASE}#idx_species']
    add(client, 'a', index_structures=indices)
    add(client, 'permuted', 'a', index_structures=indices[::-1])
    assert row(report(client), 'permuted')['status'] == 'consistent'


def test_disagreeing_alternative_definitions_block_adoption(client):
    add(client, 'a')
    add(client, 'b', token_vector={'energy': 1})
    v = add(client, 'alternatives', 'a', token_vector={'momentum': 1})
    v['equations']['E_alternative_b'] = dict(
        iri=f'{BASE}#E_alternative_b', internal_id='E_alternative_b',
        lhs=v['iri'], rhs='b', network='universe')
    response = client.post('/api/equation/variables', json=v)
    assert response.status_code == 200, response.text
    out = report(client)
    findings = row(out, 'alternatives')['findings']
    fixes = [fix for f in findings for fix in f['fixes']]
    assert fixes and all('Alternative definitions' in f['blocked'] for f in fixes)
    response = client.post('/api/equation/consistency/fix', json=fix_request(out, 'alternatives'))
    assert response.status_code == 409
