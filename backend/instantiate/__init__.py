"""Instantiation — resolve a model artefact against the ontology.

The behaviour linker produces *assignments* (which equations, in which
order); instantiation turns a concrete model — nodes typed by entity
type, arcs typed by carrier — into the structures code generation
consumes: sub-index membership (§16) and, once per-contact reference
directions exist (§15), the signed incidence matrix ``F[N,A]``.
"""

from fastapi import APIRouter

router = APIRouter()

from . import service  # noqa: E402,F401  (registers endpoints)
