"""§20 gesture admissibility — capability-gated species placements.

The ontology declares *what* a node may host via ``promo:capability`` on
entity types, inherited through ``promo:parent`` ancestry:

- ``species_source``    — a node may carry ``promo:speciesAllocation``
- ``reaction_host``     — a node may carry ``promo:hostsReaction``
- ``species_transport`` — a node's adjacent arcs may carry
  ``promo:permeable`` restrictions

The UI hides inadmissible controls; this module is the authoritative
backend gate — ``PUT /api/modeller/model`` rejects violations, and
instantiation reports them, so a malformed request or stale client cannot
persist an illegal placement.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from rdflib import RDF, URIRef

from .graph_store import PROMO

SPECIES_SOURCE = "species_source"
REACTION_HOST = "reaction_host"
SPECIES_TRANSPORT = "species_transport"


def entity_capabilities(store, graph_iri) -> Dict[str, Set[str]]:
    """entity-type IRI → capability fragments, inherited through
    ``promo:parent`` ancestry across the artefact's resolution scope."""
    direct: Dict[str, Set[str]] = {}
    parents: Dict[str, str] = {}
    for gi in store.resolution_scope(graph_iri):
        g = store.dataset.graph(gi)
        for et in g.subjects(RDF.type, PROMO["EntityType"]):
            acc = direct.setdefault(str(et), set())
            for c in g.objects(et, PROMO["capability"]):
                frag = str(c).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
                acc.add(frag[4:] if frag.startswith("cap_") else frag)
            p = g.value(et, PROMO["parent"])
            if p is not None:
                parents[str(et)] = str(p)
    out: Dict[str, Set[str]] = {}
    for et in direct:
        acc, cur, seen = set(), et, set()
        while cur and cur not in seen:
            seen.add(cur)
            acc |= direct.get(cur, set())
            cur = parents.get(cur)
        out[et] = acc
    return out


def violations(
    store,
    graph_iri,
    nodes: List[Tuple[str, Optional[str], Optional[str], List[str]]],
    arcs: List[Tuple[str, Optional[str], Optional[str], Optional[List[str]]]],
) -> List[str]:
    """Check gesture admissibility for a candidate model document.

    ``nodes`` items are ``(iri, entity_type, allocation, reactions)``;
    ``arcs`` items are ``(iri, source, target, permeable-or-None)``.
    Returns human-readable violation strings — empty means admissible.
    """
    caps = entity_capabilities(store, graph_iri)
    node_caps = {iri: caps.get(et or "", set())
                 for iri, et, _a, _r in nodes}
    problems: List[str] = []

    for iri, et, allocation, reactions in nodes:
        c = node_caps[iri]
        if allocation and SPECIES_SOURCE not in c:
            problems.append(
                f"node {iri}: species allocation requires the "
                f"'{SPECIES_SOURCE}' capability (entity type {et or '?'})")
        if reactions and REACTION_HOST not in c:
            problems.append(
                f"node {iri}: hosting reactions requires the "
                f"'{REACTION_HOST}' capability (entity type {et or '?'})")

    for iri, src, tgt, permeable in arcs:
        if permeable is None:
            continue
        transported = (
            SPECIES_TRANSPORT in node_caps.get(src or "", set())
            or SPECIES_TRANSPORT in node_caps.get(tgt or "", set()))
        if not transported:
            problems.append(
                f"arc {iri}: permeability requires a '{SPECIES_TRANSPORT}' "
                f"capability on either endpoint")

    return problems


def graph_violations(store, model_graph) -> List[str]:
    """Admissibility of the gestures already persisted on a model graph —
    the instantiation gate for data that bypassed the modeller."""
    nodes = []
    for s in model_graph.subjects(RDF.type, PROMO["ModelNode"]):
        et = model_graph.value(s, PROMO["entityType"])
        alloc = model_graph.value(s, PROMO["speciesAllocation"])
        rxns = [str(r) for r in
                model_graph.objects(s, PROMO["hostsReaction"])]
        et_str = str(et) if et else None
        nodes.append((str(s), et_str, str(alloc) if alloc else None, rxns))
    arcs = []
    for s in model_graph.subjects(RDF.type, PROMO["ModelArc"]):
        perm = sorted(str(p) for p in
                      model_graph.objects(s, PROMO["permeable"]))
        # None = unrestricted (no gesture); an explicit set is a gesture.
        # An empty set is a restrict-nothing gesture that round-trips as
        # absent — a known persistence limitation (see ModelArcDoc docs).
        has_perm = (s, PROMO["permeable"], None) in model_graph
        arcs.append((
            str(s),
            str(model_graph.value(s, PROMO["source"])) or None,
            str(model_graph.value(s, PROMO["target"])) or None,
            perm if has_perm else None))
    return violations(store, model_graph.identifier, nodes, arcs)
