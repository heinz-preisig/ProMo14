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

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rdflib import URIRef
from rdflib.namespace import RDF, RDFS

from backend.core.graph_store import (
    ARTEFACT_TYPES, PROMO, SEED_FLOOR, get_store,
)

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
        "usesLibrary": [],
        "usesAssignment": [],
        "usesSpecies": [],
        "seedFloor": None,
        "staleFloor": False,
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
            line["usesLibrary"] = [
                str(o) for o in g.objects(gid, PROMO["usesLibrary"])]
            line["usesAssignment"] = [
                str(o) for o in g.objects(gid, PROMO["usesAssignment"])]
            line["usesSpecies"] = [
                str(o) for o in g.objects(gid, PROMO["usesSpecies"])]
            if atype == "ontology":
                # Seed-floor staleness (hub ticket #7): a draft
                # ontology whose floor stamp predates the current
                # floor is missing seed content — the hub shows an
                # update badge so the drift is visible and the fix
                # stays user-consented.  Frozen versions are excluded
                # by design (the file is the history).
                floor = g.value(gid, PROMO["seedFloor"])
                line["seedFloor"] = str(floor) if floor else None
                line["staleFloor"] = str(floor) != SEED_FLOOR

    for line in lines.values():
        line["versions"].sort(key=lambda v: v["version"])
    return {"seedFloor": SEED_FLOOR,
            "lines": sorted(lines.values(), key=lambda l: l["iri"])}


class NewArtefactRequest(BaseModel):
    iri: str
    type: str
    label: Optional[str] = None
    uses: List[str] = []
    uses_library: List[str] = []
    uses_assignment: List[str] = []
    uses_species: List[str] = []


class ForkRequest(BaseModel):
    source: str
    new_iri: Optional[str] = None
    label: Optional[str] = None


@router.post("/new")
def new_artefact(req: NewArtefactRequest) -> Dict[str, Any]:
    """Create an empty artefact line: type marker + ontology pins.

    Pins are born at creation (design doc: never retrofitted).  The new
    graph is persisted immediately so it survives restarts.
    """
    store = get_store()
    try:
        iri = store.create_artefact_graph(
            req.iri, req.type, label=req.label, uses=req.uses,
            uses_library=req.uses_library,
            uses_assignment=req.uses_assignment,
            uses_species=req.uses_species)
    except ValueError as exc:
        detail = str(exc)
        code = 422 if "unknown artefact type" in detail else 409
        raise HTTPException(status_code=code, detail=detail)
    store.save()
    return {"iri": str(iri)}


class PinsRequest(BaseModel):
    iri: str
    usesOntology: Optional[List[str]] = None
    usesLibrary: Optional[List[str]] = None
    usesAssignment: Optional[List[str]] = None
    usesSpecies: Optional[List[str]] = None


@router.put("/pins")
def update_pins(req: PinsRequest) -> Dict[str, Any]:
    """Replace an artefact's pin sets (drafts only).

    Each provided pin kind is replaced wholesale; absent kinds are left
    untouched.  Frozen version graphs are immutable (R5) — pin their
    draft line instead.
    """
    store = get_store()
    gid = URIRef(req.iri)
    g = store.dataset.graph(gid)
    if not len(g):
        raise HTTPException(status_code=404,
                            detail=f"no such artefact: {req.iri}")
    if store.is_frozen(g):
        raise HTTPException(status_code=403,
                            detail="frozen versions are read-only")
    for pred, targets in (
        (PROMO["usesOntology"], req.usesOntology),
        (PROMO["usesLibrary"], req.usesLibrary),
        (PROMO["usesAssignment"], req.usesAssignment),
        (PROMO["usesSpecies"], req.usesSpecies),
    ):
        if targets is None:
            continue
        g.remove((gid, pred, None))
        for t in targets:
            g.add((gid, pred, URIRef(t)))
    store.dirty = True
    return {"iri": req.iri}


@router.delete("/artefact")
def delete_artefact(iri: str) -> Dict[str, str]:
    store = get_store()
    gid = URIRef(iri)
    graph = store.dataset.graph(gid)
    if not len(graph):
        raise HTTPException(status_code=404,
                            detail=f"no such artefact: {iri}")
    if gid == store.ONTOLOGY_GRAPH_IRI:
        raise HTTPException(status_code=403,
                            detail="the core ontology cannot be deleted")
    if store.is_frozen(graph):
        raise HTTPException(status_code=403,
                            detail="frozen versions cannot be deleted")

    references = []
    for candidate in store.dataset.graphs():
        if candidate.identifier == gid:
            continue
        for predicate in (PROMO["usesOntology"], PROMO["usesLibrary"],
                          PROMO["usesAssignment"], PROMO["usesSpecies"],
                          PROMO["versionOf"]):
            if (None, predicate, gid) in candidate:
                references.append(str(candidate.identifier))
                break
    if references:
        raise HTTPException(
            status_code=409,
            detail="artefact is still referenced by: "
                   + ", ".join(sorted(set(references))),
        )

    store.dataset.remove_graph(gid)
    store.dirty = True
    store.save()
    return {"deleted": iri}


@router.post("/fork")
def fork_artefact(req: ForkRequest) -> Dict[str, Any]:
    """Fork an artefact graph into a new editable line.

    Copies the source (draft or frozen version), re-homes instance IRIs
    to the new graph's namespace, and stamps provenance
    (``promo:versionOf`` → source).  Default target IRI:
    ``{source}-fork``.
    """
    store = get_store()
    new_iri = req.new_iri or f"{req.source}-fork"
    try:
        iri = store.fork_graph(req.source, new_iri, label=req.label)
    except ValueError as exc:
        detail = str(exc)
        code = 404 if "nothing to fork" in detail else 409
        raise HTTPException(status_code=code, detail=detail)
    store.save()
    return {"iri": str(iri)}
