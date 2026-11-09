"""§33 standalone boundary — phantom-closure overlay (``_phantom_overlay``).

The artefact's declared open arcs (root composite interface) are
closed by materializing the imagined peer as an instantiation-scoped
node: severed arcs get the peer at their dangling endpoint, authored
terminals mint peer + arc, undeclared terminals report ``unclosed``.
"""

import json

from rdflib import RDF, Graph, Literal, URIRef

from backend.core.graph_store import PROMO
from backend.instantiate.builder import (
    AssignmentInfo,
    EqInfo,
    VarInfo,
)
from backend.instantiate.resolver import ArcInfo, NodeInfo
from backend.instantiate.service import _phantom_overlay

G = "http://test/model"


def _graph(open_arcs):
    g = Graph()
    model = URIRef(f"{G}/Model")
    comp = URIRef(f"{G}/Composite_0")
    g.add((model, RDF.type, PROMO["Model"]))
    g.add((model, PROMO["rootComposite"], comp))
    if open_arcs:
        g.add((comp, PROMO["openArcs"],
               Literal(json.dumps(open_arcs))))
    return g


def _anchor():
    return NodeInfo(iri=f"{G}#N1", entity_type="et:t")


def test_severed_port_materializes_phantom_at_dangling_endpoint():
    # extraction leaves the boundary arc pointing at the dropped
    # peer's IRI — the phantom fills that slot, the arc is untouched.
    nodes = {f"{G}#N1": _anchor()}
    arcs = {f"{G}#A1": ArcInfo(
        iri=f"{G}#A1", source=f"{G}#N1", target=f"{G}#N9")}
    oa = {"iri": f"{G}#A1", "externalIri": f"{G}#N1",
          "arcType": "at:tf", "phantomEntityType": "et:cap"}
    variables = {"v:p": VarInfo(iri="v:p", port_variable=True)}
    equations = {"e:q": EqInfo(iri="e:q", lhs="v:p")}
    assignments = [AssignmentInfo(
        entity_type="et:cap", sequence=["e:q"], ports=["v:in"])]

    b = _phantom_overlay(_graph([oa]), nodes, arcs, assignments,
                         variables, equations, {})

    assert b[0].status == "phantom-closed"
    assert b[0].peer_node == f"{G}#N9"
    assert nodes[f"{G}#N9"].entity_type == "et:cap"
    # boundary-condition provider: exports + consumed ports are fix-in
    assert nodes[f"{G}#N9"].fixes == ["v:p", "v:in"]


def test_authored_port_mints_peer_and_arc():
    # isSource: the missing end is the arc's source; refToExternal
    # False → the reference direction points at the phantom.
    nodes = {f"{G}#N1": _anchor()}
    arcs = {}
    oa = {"iri": f"{G}#oa1", "externalIri": f"{G}#N1",
          "arcType": "at:sig", "isSource": True,
          "refToExternal": False, "phantomEntityType": "et:ctl"}

    b = _phantom_overlay(_graph([oa]), nodes, arcs, [], {}, {}, {})

    peer = f"{G}#oa1/peer"
    assert nodes[peer].entity_type == "et:ctl"
    arc = arcs[f"{G}#oa1"]
    assert arc.source == peer
    assert arc.target == f"{G}#N1"
    assert arc.reference_from == f"{G}#N1"
    assert arc.reference_to == peer
    assert b[0].status == "phantom-closed"


def test_terminal_without_declared_peer_reports_unclosed():
    nodes = {f"{G}#N1": _anchor()}
    arcs = {}
    oa = {"iri": f"{G}#oa1", "externalIri": f"{G}#N1"}

    b = _phantom_overlay(_graph([oa]), nodes, arcs, [], {}, {}, {})

    assert b[0].status == "unclosed"
    assert len(nodes) == 1          # nothing materialized
    assert arcs == {}


def test_already_bound_arc_reports_bound():
    # the open-arc record outlived a reconnection: no phantom needed.
    nodes = {f"{G}#N1": _anchor(),
             f"{G}#N2": NodeInfo(iri=f"{G}#N2", entity_type="et:cap")}
    arcs = {f"{G}#A1": ArcInfo(
        iri=f"{G}#A1", source=f"{G}#N1", target=f"{G}#N2")}
    oa = {"iri": f"{G}#A1", "externalIri": f"{G}#N1",
          "phantomEntityType": "et:cap"}

    b = _phantom_overlay(_graph([oa]), nodes, arcs, [], {}, {}, {})

    assert b[0].status == "bound"
    assert b[0].peer_node == f"{G}#N2"
    assert len(nodes) == 2


def test_no_interface_no_boundary():
    nodes = {f"{G}#N1": _anchor()}
    b = _phantom_overlay(_graph([]), nodes, {}, [], {}, {}, {})
    assert b == []
    g = Graph()                      # no Model subject at all
    assert _phantom_overlay(g, nodes, {}, [], {}, {}, {}) == []
