"""Shared FastAPI dependencies for graph selection
(docs/versioning-and-session-design.md R4/R5).

``graph_param`` is the read-side dependency — an absent ``?graph=``
falls back to the legacy working-ontology scope.  ``editable_param``
is the write-side guard: it requires an explicit, existing, editable
artefact graph.  ``resolve_graph`` maps either result to a dataset
graph.

These used to live in ``ontology.service`` and were imported by every
other service module; they have no ontology-specific content, so they
live in ``core``.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, Request
from rdflib import URIRef

from backend.core.graph_store import get_store
from backend.core.iri import canonical_graph_iri


def _graph_value(request: Request) -> Optional[str]:
    """The single ``?graph=`` value — a duplicated param must fail
    loud: scalar binding silently picks the last value, which can
    resolve reads *and* writes to the wrong artefact."""
    values = request.query_params.getlist("graph")
    if len(values) > 1:
        raise HTTPException(
            status_code=400,
            detail="multiple ?graph= params — ambiguous graph scope")
    return values[0] if values else None


def graph_param(request: Request) -> Optional[str]:
    """FastAPI dependency: the ``?graph=`` query param (a graph IRI).
    Normalised to the slash-free canonical form — ``…/library/``-era
    session URLs keep resolving after the §26 rename."""
    graph = _graph_value(request)
    return canonical_graph_iri(graph) if graph else graph


def editable_param(request: Request) -> Optional[str]:
    """Like ``graph_param`` but rejects frozen version graphs (R5) and
    graphs that were never created — and is *required* on writes.

    Writes must name their artefact explicitly (hub ticket #1): the
    legacy "no graph means the working ontology" default let writes
    silently land in the core graph.  Reads keep the legacy default
    via ``graph_param``; only mutating endpoints use this guard.

    A write must not materialize an artefact: creation goes through
    ``/api/catalogue/new`` or ``/fork`` so the type marker and
    ``usesOntology`` pins are born with it (hub ticket #3).  A properly
    created artefact is never empty — the marker triple is always
    stamped — so ``len(g) == 0`` means the IRI names nothing."""
    graph = _graph_value(request)
    if graph is None:
        raise HTTPException(
            status_code=400,
            detail="?graph= is required on writes — open the artefact "
                   "from the hub so the session carries its graph IRI")
    graph = canonical_graph_iri(graph)
    store = get_store()
    g = store.graph(graph)
    if not len(g):
        raise HTTPException(
            status_code=404,
            detail=f"no such artefact: {graph} — create it via the hub "
                   "(/api/catalogue/new) so its pins are born")
    try:
        store.assert_editable(g)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return graph


def resolve_graph(store, graph_iri: Optional[str]):
    """Resolve an optional graph IRI to a dataset graph (default: the
    working ontology).  Slash-terminated spellings normalise to the
    canonical slash-free identifier."""
    return store.ontology_graph if graph_iri is None \
        else store.dataset.graph(URIRef(canonical_graph_iri(graph_iri)))
