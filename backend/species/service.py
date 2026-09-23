"""Species artefact persistence — §20.

The artefact graph (``?graph=``) is one species/reaction document —
the *vocabulary* the species-agnostic modeller references.  ``GET``
reads it back into a ``SpeciesDocument``; ``PUT`` replaces the graph's
species content wholesale (same whole-document pattern as the
modeller, ADR-007).

RDF shape:

- ``promo:Species`` — the artefact-type marker on the graph IRI (the
  catalogue classifies the line ``species``).
- ``promo:Component`` — one per chemical species: ``internalID``,
  ``label``.  (``Component`` not ``Species`` so members don't collide
  with the artefact marker; matches the ``component_mass`` token.)
- ``promo:Allocation`` — a named species set a reservoir injects:
  ``member`` → Component IRI (multi-valued).
- ``promo:Reaction`` — a stoichiometric rule: ``reactant`` /
  ``product`` → Component IRI (multi-valued).  For distribution only
  the species sets matter; coefficients are a kinetics concern,
  bound when the reaction's equation is instantiated (§20 open).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import Depends
from pydantic import BaseModel, Field
from rdflib import RDF, RDFS, Literal, URIRef

from backend.core.graph_store import PROMO, get_store
from backend.ontology.service import editable_param, graph_param, resolve_graph

from . import router

_SPECIES_TYPES = ("Component", "Allocation", "Reaction")


# ---------------------------------------------------------------------------
# Document schema
# ---------------------------------------------------------------------------


class ComponentDoc(BaseModel):
    iri: str
    label: str = ""


class AllocationDoc(BaseModel):
    iri: str
    label: str = ""
    members: List[str] = Field(default_factory=list)   # Component IRIs


class ReactionDoc(BaseModel):
    iri: str
    label: str = ""
    reactants: List[str] = Field(default_factory=list)  # Component IRIs
    products: List[str] = Field(default_factory=list)   # Component IRIs


class SpeciesDocument(BaseModel):
    components: List[ComponentDoc] = Field(default_factory=list)
    allocations: List[AllocationDoc] = Field(default_factory=list)
    reactions: List[ReactionDoc] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _one(graph, s, p) -> Optional[str]:
    v = graph.value(s, p)
    return str(v) if v is not None else None


def _members(graph, s, p) -> List[str]:
    return sorted(str(o) for o in graph.objects(s, p))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/species", response_model=SpeciesDocument)
def get_species(graph_iri: Optional[str] = Depends(graph_param)
                ) -> SpeciesDocument:
    """Load the artefact graph's species document (empty doc if none)."""
    store = get_store()
    graph = resolve_graph(store, graph_iri)

    doc = SpeciesDocument()
    for s in graph.subjects(RDF.type, PROMO["Component"]):
        doc.components.append(ComponentDoc(
            iri=str(s), label=_one(graph, s, RDFS.label) or ""))
    for s in graph.subjects(RDF.type, PROMO["Allocation"]):
        doc.allocations.append(AllocationDoc(
            iri=str(s), label=_one(graph, s, RDFS.label) or "",
            members=_members(graph, s, PROMO["member"])))
    for s in graph.subjects(RDF.type, PROMO["Reaction"]):
        doc.reactions.append(ReactionDoc(
            iri=str(s), label=_one(graph, s, RDFS.label) or "",
            reactants=_members(graph, s, PROMO["reactant"]),
            products=_members(graph, s, PROMO["product"])))
    return doc


@router.put("/species", response_model=SpeciesDocument)
def put_species(
    doc: SpeciesDocument,
    graph_iri: Optional[str] = Depends(editable_param),
) -> SpeciesDocument:
    """Replace the artefact graph's species content with ``doc``."""
    store = get_store()
    graph = resolve_graph(store, graph_iri)

    for t in _SPECIES_TYPES:
        for s in list(graph.subjects(RDF.type, PROMO[t])):
            graph.remove((s, None, None))

    for c in doc.components:
        s = URIRef(c.iri)
        graph.add((s, RDF.type, PROMO["Component"]))
        if c.label:
            graph.set((s, RDFS.label, Literal(c.label)))
        graph.set((s, PROMO["internalID"],
                   Literal(c.iri.rsplit("/", 1)[-1])))

    for a in doc.allocations:
        s = URIRef(a.iri)
        graph.add((s, RDF.type, PROMO["Allocation"]))
        if a.label:
            graph.set((s, RDFS.label, Literal(a.label)))
        graph.set((s, PROMO["internalID"],
                   Literal(a.iri.rsplit("/", 1)[-1])))
        for m in a.members:
            graph.add((s, PROMO["member"], URIRef(m)))

    for r in doc.reactions:
        s = URIRef(r.iri)
        graph.add((s, RDF.type, PROMO["Reaction"]))
        if r.label:
            graph.set((s, RDFS.label, Literal(r.label)))
        graph.set((s, PROMO["internalID"],
                   Literal(r.iri.rsplit("/", 1)[-1])))
        for m in r.reactants:
            graph.add((s, PROMO["reactant"], URIRef(m)))
        for m in r.products:
            graph.add((s, PROMO["product"], URIRef(m)))

    return doc
