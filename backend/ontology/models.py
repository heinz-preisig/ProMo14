"""Pydantic models for the ontology editor API.

VariableRecord and EquationRecord extend the existing data model from
``docs/ontology-data-model.md`` — ``classifications`` is the only
 genuinely new field, replacing ``variable_class`` with a multi-axis map.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Domain tree
# ---------------------------------------------------------------------------


class NetworkRecord(BaseModel):
    """Legacy network record — kept for backward compat."""

    iri: str
    name: str
    label: Optional[str] = None
    parent: Optional[str] = None
    children: List[str] = Field(default_factory=list)


class DomainRecord(BaseModel):
    """Domain in the two-branch tree (physical / information)."""

    iri: str
    name: str
    label: Optional[str] = None
    parent: Optional[str] = None
    branch: Optional[str] = None  # "physical" or "information" (top-level only)
    children: List[str] = Field(default_factory=list)
    tokens: List[str] = Field(default_factory=list)  # token IRIs explicitly assigned to this domain
    inherited_tokens: List[str] = Field(default_factory=list)  # token IRIs inherited from ancestors (read-only)


# ---------------------------------------------------------------------------
# Classification axes
# ---------------------------------------------------------------------------


class ClassificationAxisRecord(BaseModel):
    iri: str
    domain: str  # domain IRI where this axis is defined
    name: str  # e.g. "role", "extensivity", "origin"
    parent: Optional[str] = None  # inherited from parent domain
    terms: List["AxisTermRecord"] = Field(default_factory=list)


class AxisTermRecord(BaseModel):
    iri: str
    axis: str  # axis IRI
    label: str
    parent: Optional[str] = None  # hierarchical (tree)


# ---------------------------------------------------------------------------
# Variables and equations (aligned with docs/ontology-data-model.md)
# ---------------------------------------------------------------------------


class EquationRecord(BaseModel):
    """Nested inside a variable, one per expression network."""

    iri: str
    internal_id: Optional[str] = None  # E_N code name
    lhs: str = ""  # variable IRI being defined
    rhs: str = ""  # token stream (global_ID form)
    rhs_latex: Optional[str] = None  # generated LaTeX, cached (nullable)
    equation_class: str = "generic"  # IRI of EquationClass node (hierarchical)
    network: str = "root"  # expression definition network
    incidence_list: List[str] = Field(default_factory=list)  # derived, cached
    doc: str = ""
    created: Optional[str] = None
    modified: Optional[str] = None


class VariableRecord(BaseModel):
    # Identity & naming (three-name pattern)
    iri: str
    label: str
    internal_id: Optional[str] = None
    aliases: Dict[str, str] = Field(default_factory=dict)
    # extensible: internal_code, latex, matlab, python, modelica, ...

    # Domain / location
    network: str = "root"
    classifications: Dict[str, str] = Field(default_factory=dict)
    # Replaces variable_class: map of axis IRI -> axis term IRI
    variable_class: Optional[str] = None  # legacy, kept for backward compat
    port_variable: bool = False
    imported: bool = False  # ontology-editor metadata

    # Semantics
    doc: str = ""
    units: List[int] = Field(default_factory=lambda: [0] * 8)
    tokens: List[str] = Field(default_factory=list)
    # Pre-bound value slot — universal constants carry it permanently;
    # parameters get it at the instantiation stage (ADR-008).
    value: Optional[str] = None

    # Index structure
    index_structures: List[str] = Field(default_factory=list)

    # Equations (nested, one per expression network)
    equations: Dict[str, EquationRecord] = Field(default_factory=dict)

    # Codegen metadata (not consumed by equation editor)
    compiled_lhs: Optional[Dict] = None
    memory: Optional[Dict] = None

    # Audit
    created: Optional[str] = None
    modified: Optional[str] = None


# ---------------------------------------------------------------------------
# Indices
# ---------------------------------------------------------------------------


class IndexRecord(BaseModel):
    iri: str
    label: str
    short_name: Optional[str] = None
    network: str = "root"
    index_class: str = "index"
    internal_id: Optional[str] = None
    aliases: Dict[str, str] = Field(default_factory=dict)
    token: Optional[str] = None


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


class TokenRecord(BaseModel):
    iri: str
    label: str
    parent: Optional[str] = None
    kind: Optional[Literal["conserved", "reference"]] = None


# ---------------------------------------------------------------------------
# Scales (first-class concept: time scale, length scale, user-defined)
# ---------------------------------------------------------------------------


class ScaleDimensionRecord(BaseModel):
    iri: str
    name: str  # e.g. "time", "length"
    domain: str  # domain IRI where this scale is defined
    parent: Optional[str] = None  # inherited from parent domain
    kind: Optional[Literal["structural", "content"]] = None
    values: List["ScaleValueRecord"] = Field(default_factory=list)


class ScaleValueRecord(BaseModel):
    iri: str
    dimension: str  # scale dimension IRI
    label: str  # e.g. "microscopic", "macroscopic"
    parent: Optional[str] = None  # hierarchical (tree)


# ---------------------------------------------------------------------------
# Entity types (CWA 17960 — seed/default, not hardcoded schema)
# ---------------------------------------------------------------------------


class EntityTypeRecord(BaseModel):
    iri: str
    label: str
    temporal_type: Literal["constant", "dynamic", "event-dynamic"]
    spatial_type: Optional[Literal["uniform", "distributed"]] = None  # physical only
    spatial_size: Optional[Literal["infinite", "finite", "infinitesimal"]] = None
    branch: str  # must match a top-level domain's branch label
    scale_values: List[str] = Field(default_factory=list)  # scale value IRIs
    description: str = ""
    parent: Optional[str] = None  # promo:parent — entity-type taxonomy


# ---------------------------------------------------------------------------
# Connection rules
# ---------------------------------------------------------------------------


class ConnectionRuleRecord(BaseModel):
    iri: str
    rule_type: str  # label, e.g. "physical-same" | "signal" | "access" | "sensor" | "actuation"
    source_domain: Optional[str] = None  # optional domain constraint
    target_domain: Optional[str] = None
    shared_tokens: List[str] = Field(default_factory=list)  # token IRIs
    direction: Optional[Literal["bidirectional", "unidirectional"]] = None
    carrier: Optional[Literal["token-flow", "reference"]] = None
    scope: Optional[Literal["same", "cross", "any"]] = None
    description: str = ""


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class SaveRequest(BaseModel):
    filename: str = "ontology.trig"


class PublishRequest(BaseModel):
    version: str
