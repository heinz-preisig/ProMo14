"""Pydantic models for the ontology editor API."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class NetworkRecord(BaseModel):
    iri: str
    name: str
    label: Optional[str] = None
    parent: Optional[str] = None
    children: List[str] = Field(default_factory=list)


class VariableRecord(BaseModel):
    iri: str
    label: str
    network: str = "root"
    variable_class: str = "state"
    units: List[int] = Field(default_factory=lambda: [0] * 8)
    index_structures: List[str] = Field(default_factory=list)
    internal_id: Optional[str] = None
    aliases: Dict[str, str] = Field(default_factory=dict)
    doc: str = ""
    port_variable: bool = False
    tokens: List[str] = Field(default_factory=list)


class IndexRecord(BaseModel):
    iri: str
    label: str
    short_name: Optional[str] = None
    network: str = "root"
    index_class: str = "index"
    internal_id: Optional[str] = None
    aliases: Dict[str, str] = Field(default_factory=dict)
    token: Optional[str] = None


class TokenRecord(BaseModel):
    iri: str
    label: str
    parent: Optional[str] = None


class EquationRecord(BaseModel):
    iri: str
    lhs: str
    rhs_tokens: List[str] = Field(default_factory=list)
    equation_class: str = "generic"
    network: str = "root"
    doc: str = ""


class SaveRequest(BaseModel):
    filename: str = "ontology.trig"
