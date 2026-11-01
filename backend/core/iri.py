"""§26 instance-IRI shapes — the single definition site.

An instance IRI is absolute and lives under its owning artefact's
namespace (docs/behaviour-linker-design-discussion.md §26).  Two
join conventions, each expressed once here:

- ``#`` — fragment: members of an artefact's *vocabulary*
  (variables, equations, ontology terms): ``{graph}#name``.
- ``/`` — subordinate resources under another IRI: ``{graph}/Model``,
  ``{graph}/Composite_2``, ``{graph}/Node_3``, ``{graph}/Arc_7``,
  ``{eq}/expression``, ``{base}/assignments``.

Artefact graph IRIs are slash-free names (``…/model``), so the
``{graph}/x`` join yields uniform paths for every member.

Synthesised (not stored) shapes:

- ``promo#ArcType/<carrier>`` — vocabulary-namespace arc types derived
  from connection-rule carriers.
- ``{ontology}#F_<mech>`` — seeded incidence-factor variables.

Mirrors ``packages/semantic/src/iris.ts`` for the shapes clients mint.
"""

from __future__ import annotations

from typing import Optional, Union

from rdflib import URIRef

from .vocab import PROMO

VOCAB_NS = str(PROMO)   # "https://w3id.org/promo#"

Base = Union[str, URIRef]


def vocab_iri(base: Base, fragment: str) -> URIRef:
    """``{base}#{fragment}`` — a member of an artefact's vocabulary."""
    b = str(base).rstrip("#")
    return URIRef(f"{b}#{fragment}")


def canonical_graph_iri(iri: Union[str, URIRef]) -> str:
    """Artefact graph IRIs are slash-free names — strips a trailing
    ``/`` so ``?graph=…/library/``-era spellings still resolve."""
    return str(iri).rstrip("/")


def child_iri(base: Base, segment: str) -> URIRef:
    """``{base}/{segment}`` — a resource subordinate to ``base``."""
    return URIRef(str(base).rstrip("/") + "/" + segment)


def local_name(iri: Union[str, URIRef]) -> str:
    """The trailing fragment of any shape — after ``#`` or ``/``."""
    return str(iri).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def is_absolute(iri: Union[str, URIRef]) -> bool:
    """§26 write-boundary test: absolute ``http(s)`` spelling only."""
    return str(iri).startswith(("http://", "https://"))


# -- vocabulary members -------------------------------------------------

def variable_iri(graph: Base, internal_id: str) -> URIRef:
    """``{graph}#{internal_id}`` — a variable.  Keyed on the internal
    ID, not the label, so a rename touches no reference."""
    return vocab_iri(graph, internal_id)


def equation_iri(graph: Base, internal_id: str) -> URIRef:
    """``{graph}#{E_n}`` — an equation; keyed by its internal ID."""
    return vocab_iri(graph, internal_id)


def f_factor_iri(ontology_base: Base, mechanism: str) -> URIRef:
    """``{ontology}#F_{mech}`` — seeded incidence-factor variable."""
    return vocab_iri(ontology_base, f"F_{mechanism}")


# -- model artefact -----------------------------------------------------

def model_iri(graph: Base) -> URIRef:
    """``{graph}/Model`` — the document root."""
    return child_iri(graph, "Model")


def model_node_iri(graph: Base, node_id: Union[int, str]) -> URIRef:
    """``{graph}/Node_{id}`` — a model topology node."""
    return child_iri(graph, f"Node_{node_id}")


def model_arc_iri(graph: Base, counter: Union[int, str]) -> URIRef:
    """``{graph}/Arc_{counter}`` — a model topology arc."""
    return child_iri(graph, f"Arc_{counter}")


def composite_iri(graph: Base, tree_id: int) -> URIRef:
    """``{graph}/Composite_{tree_id}`` — deterministic (ADR-007)."""
    return child_iri(graph, f"Composite_{tree_id}")


def occurrence_prefix(composite: Base) -> str:
    """``{composite}/`` — instance path prefix for §22 occurrences."""
    return str(composite) + "/"


# -- subordinate resources ----------------------------------------------

def expression_iri(equation: Base) -> URIRef:
    """``{equation}/expression`` — canonical RHS root resource."""
    return child_iri(equation, "expression")


def assignments_graph_iri(base: Base) -> str:
    """``{base}/assignments`` — the artefact's behaviour-assignment graph."""
    return str(child_iri(base, "assignments"))


def assignment_iri(assignments_graph: Base, entity_type: str) -> URIRef:
    """``{assignments}#assignment_{etype-frag}`` — one assignment resource."""
    frag = local_name(entity_type)
    return vocab_iri(assignments_graph, f"assignment_{frag}")


# -- synthesised vocabulary shapes ---------------------------------------

def arc_type_iri(carrier: Optional[str]) -> str:
    """``promo#ArcType/<carrier>`` — synthesised, never a stored subject."""
    return f"{VOCAB_NS}ArcType/{carrier or 'generic'}"


def vocab_ns_iri(local: str) -> str:
    """``promo#{local}`` — expand a bare local name into vocabulary space."""
    return VOCAB_NS + local
