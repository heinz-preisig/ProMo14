"""Artefact catalogue — the hub's view of the dataset.

Lists **artefact lines** (docs/versioning-and-session-design.md): one
entry per artefact, grouping the working draft with its frozen version
graphs.  Graphs are classified by their artefact-type marker
(``<graphIRI> a promo:Ontology | Library | Assignment | Model | Glass``);
unmarked graphs are lightly inferred (a graph full of ``promo:Variable``
is a library) or reported as ``"graph"``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from rdflib import URIRef
from rdflib.namespace import RDF, RDFS

from backend.core.graph_store import ARTEFACT_TYPES, PROMO, get_store

router = APIRouter()


def _label(graph, iri: URIRef) -> str:
    """Display label for a graph: rdfs:label on the IRI, else the
    fragment / last path segment."""
    label = graph.value(iri, RDFS.label)
    if label:
        return str(label)
    text = str(iri)
    frag = text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return frag or text


def _artefact_type(graph, types: set) -> str:
    """Artefact type from the marker, with light inference for
    unmarked (legacy) graphs."""
    for t in ARTEFACT_TYPES:
        if PROMO[t] in types:
            return t.lower()
    if (None, RDF.type, PROMO["Variable"]) in graph:
        return "library"
    return "graph"


def _new_line(iri: str) -> Dict[str, Any]:
    return {
        "iri": iri,
        "type": "graph",
        "label": iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1],
        "status": "frozen",
        "versions": [],
        "usesOntology": [],
    }


@router.get("")
def catalogue() -> Dict[str, Any]:
    """Return artefact lines: drafts grouped with their versions."""
    store = get_store()
    lines: Dict[str, Dict[str, Any]] = {}

    for g in store.dataset.graphs():
        if not len(g):
            continue
        gid = g.identifier
        types = set(g.objects(gid, RDF.type))
        atype = _artefact_type(g, types)

        if PROMO["Version"] in types:
            base = g.value(gid, PROMO["versionOf"])
            base_iri = str(base) if base else str(gid)
            line = lines.setdefault(base_iri, _new_line(base_iri))
            if line["type"] == "graph":
                line["type"] = atype
            line["versions"].append({
                "version": str(g.value(gid, PROMO["versionInfo"]) or ""),
                "iri": str(gid),
                "published_on": (
                    str(g.value(gid, PROMO["publishedOn"]) or "") or None),
            })
        else:
            line = lines.setdefault(str(gid), _new_line(str(gid)))
            line["type"] = atype
            line["status"] = "draft"
            line["label"] = _label(g, gid)
            line["usesOntology"] = [
                str(o) for o in g.objects(gid, PROMO["usesOntology"])]

    for line in lines.values():
        line["versions"].sort(key=lambda v: v["version"])
    return {"lines": sorted(lines.values(), key=lambda l: l["iri"])}
