"""ProMo vocabulary constants and literal helpers.

Namespaces, artefact-type markers, seed tables and the shared
``_as_literal`` coercion — pure data, no store behaviour.  Split out
of ``graph_store`` so the persistence/seed mixins and the store share
one definition site.
"""

from __future__ import annotations

import json
import re
from typing import Any

from rdflib import Literal, Namespace

PROMO = Namespace("https://w3id.org/promo#")
PROMOLG = Namespace("https://w3id.org/promo/language#")
QUDT = Namespace("http://qudt.org/schema/qudt/")

# Artefact-type markers (docs/versioning-and-session-design.md): every
# artefact graph carries ``<graphIRI> a promo:<Type>`` so the catalogue
# can classify it.  ``promo:Version`` marks frozen graphs separately.
ARTEFACT_TYPES = ("Ontology", "Library", "Assignment", "Model", "Glass",
                  "Species")

# Universal constants seeded into every ontology (ADR-008): pre-bound
# value slots, class ``constant``, network ``root`` — visible from every
# expression network via ancestor-chain resolution.  ``value`` is the
# code-surface literal; ``latex`` is the document-surface alias.
#   (fragment, label, value, latex alias)
SEED_CONSTANTS = (
    ("const_zero", "zero", "0", "0"),
    ("const_one", "one", "1", "1"),
    ("const_half", "half", "0.5", r"\frac{1}{2}"),
)

# Seed-floor revision stamped as ``promo:seedFloor`` on every graph the
# migratable seed sequence (``apply_seed_floor``) has run against.
# Bump when any ``_seed_*`` step's content changes so the catalogue can
# flag draft ontology forks that predate the current floor.
SEED_FLOOR = "2026-09"

# Legacy prefixes used in old TriG files.
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

# Conforming equation ids: ``E_1`` … ``E_999999``.  Anything else
# (notably legacy ``E_<epoch-ms>`` ids minted by the equation editor)
# is renumbered by ``_migrate_equation_ids``.
_EQUATION_ID_RE = re.compile(r"^E_(\d{1,6})$")

# ProMo14 ontology vocabulary extensions (see docs/ontology-editor-v1-ticket.md)
#
# Domain tree
#   promo:Domain            — a domain in the tree (replaces promo:Network)
#   promo:branch            — "physical" or "information" (top-level only)
#   promo:hasToken          — links a domain to tokens that live in it
#
# Classification axes
#   promo:ClassificationAxis — an axis definition
#   promo:axisName          — axis label (e.g. "role", "extensivity")
#   promo:AxisTerm          — a term in an axis hierarchy
#   promo:axisValue         — links a variable to an axis term
#   promo:hasAxis           — links a domain to an axis it defines
#
# Scale dimensions and values (first-class concept)
#   promo:ScaleDimension   — a scale dimension (time scale, length scale, user-defined)
#   promo:scaleName        — dimension name (e.g. "time", "length")
#   promo:dimensionKind    — "structural" | "content"  (structural dims compose
#                          entity types; content dims bind per model-node
#                          instance, e.g. phase as constitutive selector)
#   promo:hasDomain        — links a scale dimension to the domain where it is defined
#   promo:ScaleValue       — a value in a scale dimension's hierarchical tree
#   promo:hasScale         — links a scale value to its dimension
#   promo:scaleValueLabel  — label for a scale value (e.g. "microscopic", "macroscopic")
#
# Tokens
#   promo:Token            — a token type (what lives in a domain)
#   promo:tokenKind        — "conserved" | "reference"  (conserved tokens
#                          accumulate and ride token-flow arcs; reference
#                          tokens expose variable access on reference arcs)
#
# Entity type taxonomy (CWA 17960 — seed/default, not hardcoded schema)
#   promo:EntityType        — an entity type
#   promo:temporalType     — "constant" | "dynamic" | "event-dynamic"
#   promo:spatialType      — "uniform" | "distributed" (physical only)
#   promo:spatialSize      — "infinite" | "finite" | "infinitesimal" (physical only)
#   promo:hasScaleValue    — links an entity type to its scale value(s)
#
# Connection rules
#   promo:ConnectionRule    — a connection rule definition
#   promo:ruleType          — "physical-same" | "physical-cross" | "signal"
#   promo:sharedTokens      — tokens that must be shared for physical rules
#
# Equation classes (hierarchical)
#   promo:EquationClass     — an equation class node
#   promo:equationClass     — links an equation to its class (IRI, not string)
#
# Equations (nested in variable's named graph)
#   promo:Equation         — one equation (LHS variable + RHS expression)
#   promo:hasEquation      — links a variable to its equation(s)
#   promo:lhs              — the variable IRI being defined
#   promo:rhs              — the expression token stream (string)
#   promo:rhsLatex         — generated LaTeX of the RHS (cached)
#   promo:incidenceList     — list of variable IRIs in the RHS (JSON array)
UNIT_FIELDS = [
    "time",
    "length",
    "mass",
    "current",
    "temperature",
    "amount",
    "light",
    "nil",
]


def _as_literal(value: Any) -> Literal:
    if isinstance(value, bool):
        return Literal(value, datatype=XSD.boolean)
    if isinstance(value, int):
        return Literal(value, datatype=XSD.integer)
    if isinstance(value, float):
        return Literal(value, datatype=XSD.double)
    if isinstance(value, (list, dict)):
        return Literal(json.dumps(value))
    return Literal(str(value))
