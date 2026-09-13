"""FastAPI service for the equation editor.

Endpoints (mounted under ``/api/equation`` by ``backend.main``):

- ``POST /parse`` — syntax-only parse; returns the AST as JSON.
- ``POST /check`` — parse + semantic check against a caller-supplied
  compile context (variables, indices, networks). Returns inferred units,
  index structures and the variable incidence list.

The check endpoint takes the context in the request body for now; once the
ontology/graph store lands it will resolve the context from a graph IRI
instead.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from rdflib import URIRef

from backend.core.graph_store import get_store
from backend.ontology.models import VariableRecord
from backend.ontology.rdf_context import RdfContext

from .checker import check
from .compile_space import CompileSpace, Index, Variable
from .context import DictContext

from .errors import VarError
from .parser import ParseError, parse
from .syntax import Node, Var
from .units import Units

router = APIRouter()


# ---------------------------------------------------------------------------
# AST serialisation
# ---------------------------------------------------------------------------

def node_to_dict(node: Node) -> Dict[str, Any]:
    """Serialise a ``syntax.Node`` tree to plain JSON-able dicts."""
    if not is_dataclass(node):
        return {"type": type(node).__name__, "value": node}
    out: Dict[str, Any] = {"type": type(node).__name__}
    for f in fields(node):
        v = getattr(node, f.name)
        if isinstance(v, tuple):
            out[f.name] = [node_to_dict(x) for x in v]
        elif is_dataclass(v):
            out[f.name] = node_to_dict(v)
        elif v is None or isinstance(v, (str, int, float, bool)):
            out[f.name] = v
        else:
            out[f.name] = str(v)
    return out


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ParseRequest(BaseModel):
    text: str


class ParseResponse(BaseModel):
    ok: bool
    ast: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class EquationIn(BaseModel):
    iri: str = ""
    internal_id: Optional[str] = None
    lhs: str = ""
    rhs: str = ""
    rhs_latex: Optional[str] = None
    equation_class: Optional[str] = None
    network: Optional[str] = None
    incidence_list: List[str] = Field(default_factory=list)
    doc: str = ""
    created: Optional[str] = None
    modified: Optional[str] = None


class VariableIn(BaseModel):
    iri: str
    label: str
    network: str
    type: str = "state"
    units: List[int] = Field(default_factory=lambda: [0] * 8)
    index_structures: List[str] = Field(default_factory=list)
    internal_id: Optional[str] = None
    aliases: Dict[str, str] = Field(default_factory=dict)
    doc: str = ""
    port_variable: bool = False
    tokens: List[str] = Field(default_factory=list)
    equations: Dict[str, EquationIn] = Field(default_factory=dict)


class IndexIn(BaseModel):
    iri: str
    label: str
    network: str = "root"
    index_class: str = "index"
    aliases: Dict[str, str] = Field(default_factory=dict)
    token: Optional[str] = None
    short_name: Optional[str] = None


class CheckRequest(BaseModel):
    text: str
    variables: List[VariableIn] = Field(default_factory=list)
    indices: List[IndexIn] = Field(default_factory=list)
    variable_definition_network: str = "root"
    expression_definition_network: str = "root"
    lhs: Optional[str] = None  # LHS variable label, needed for Root()
    # parent -> children domain tree; used to compute accessible networks
    network_tree: Dict[str, List[str]] = Field(default_factory=dict)


class CheckResponse(BaseModel):
    ok: bool
    units: Optional[List[int]] = None
    units_pretty: Optional[str] = None
    indices: Optional[List[str]] = None
    incidence: Optional[List[str]] = None
    label: Optional[str] = None
    error: Optional[str] = None
    error_kind: Optional[str] = None
    candidates: Optional[List[Dict[str, Any]]] = None  # AmbiguousVariableError


class ContextResponse(BaseModel):
    variables: List[VariableIn] = Field(default_factory=list)
    indices: List[IndexIn] = Field(default_factory=list)
    network_tree: Dict[str, List[str]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/context", response_model=ContextResponse)
def context_endpoint() -> ContextResponse:
    """Load the equation context from the RDF graph store in PROMO_DATA_DIR."""
    ctx = RdfContext(get_store())

    variables = []
    for v in ctx.variables().values():
        variables.append(
            VariableIn(
                iri=v.iri,
                label=v.label,
                network=v.network,
                type=v.type,
                units=v.units.as_list(),
                index_structures=v.index_structures,
                internal_id=v.internal_id,
                aliases=v.aliases,
                doc=v.doc,
                port_variable=v.port_variable,
                tokens=v.tokens,
                equations=getattr(v, "equations", {}),
            )
        )

    indices = []
    for i in ctx.indices().values():
        short = i.aliases.get("internal_code")
        if not short and i.label:
            short = i.label[0]
        indices.append(
            IndexIn(
                iri=i.iri,
                label=i.label,
                network=i.network,
                index_class=i.index_class,
                aliases=i.aliases,
                token=i.token,
                short_name=short,
            )
        )

    return ContextResponse(
        variables=variables,
        indices=indices,
        network_tree=ctx.tree(),
    )


@router.post("/parse", response_model=ParseResponse)
def parse_endpoint(req: ParseRequest) -> ParseResponse:
    try:
        node = parse(req.text)
    except ParseError as e:
        return ParseResponse(ok=False, error=str(e))
    return ParseResponse(ok=True, ast=node_to_dict(node))


@router.post("/check", response_model=CheckResponse)
def check_endpoint(req: CheckRequest) -> CheckResponse:
    variables = {
        v.iri: Variable(
            iri=v.iri,
            label=v.label,
            network=v.network,
            type=v.type,
            units=Units.from_list(v.units),
            index_structures=v.index_structures,
            internal_id=v.internal_id,
            aliases=v.aliases,
            doc=v.doc,
            port_variable=v.port_variable,
            tokens=v.tokens,
        )
        for v in req.variables
    }
    indices = {
        i.iri: Index(
            iri=i.iri,
            label=i.label,
            network=i.network,
            index_class=i.index_class,
            aliases=i.aliases,
            token=i.token,
        )
        for i in req.indices
    }
    ctx = DictContext(variables, indices, tree=req.network_tree)
    space = CompileSpace(
        ctx.variables(),
        ctx.indices(),
        variable_definition_network=req.variable_definition_network,
        expression_definition_network=req.expression_definition_network,
        accessible_networks=ctx.accessible_networks(
            req.expression_definition_network
        ),
    )

    try:
        node = parse(req.text)
        lhs = Var(req.lhs) if req.lhs else None
        checked = check(node, space, lhs)
    except ParseError as e:
        return CheckResponse(ok=False, error=str(e), error_kind="parse")
    except VarError as e:
        resp = CheckResponse(
            ok=False, error=str(e), error_kind=type(e).__name__
        )
        if hasattr(e, "candidates"):
            resp.candidates = e.candidates
        return resp

    return CheckResponse(
        ok=True,
        units=checked.units.as_list(),
        units_pretty=checked.units.pretty(),
        indices=checked.indices,
        incidence=sorted(checked.incidence),
        label=checked.label,
    )


# ---------------------------------------------------------------------------
# Variable CRUD (variables and their nested equations live in the equation editor)
# ---------------------------------------------------------------------------


@router.post("/variables", response_model=VariableRecord)
def create_variable(record: VariableRecord) -> VariableRecord:
    """Create a new variable (with nested equations) in the ontology graph."""
    store = get_store()
    if not record.iri:
        record.iri = str(store.mint_iri("http://example.org/ontology", record.internal_id or store.next_internal_id("V")))
    if not record.internal_id:
        record.internal_id = store.next_internal_id("V")

    var = record.model_dump()
    if var.get("variable_class"):
        var["type"] = var["variable_class"]
    store.add_variable_dict(store.ontology_graph, var)
    return record


@router.put("/variables/{iri:path}", response_model=VariableRecord)
def update_variable(iri: str, record: VariableRecord) -> VariableRecord:
    """Replace a variable in the ontology graph."""
    store = get_store()
    graph = store.ontology_graph

    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Variable not found")

    graph.remove((subject, None, None))
    record.iri = iri
    store.add_variable_dict(graph, record.model_dump())
    return record


@router.delete("/variables/{iri:path}")
def delete_variable(iri: str) -> Dict[str, str]:
    """Delete a variable from the ontology graph."""
    store = get_store()
    graph = store.ontology_graph
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Variable not found")
    graph.remove((subject, None, None))
    return {"deleted": iri}
