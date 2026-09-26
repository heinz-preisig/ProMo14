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

import json
import re
from dataclasses import fields, is_dataclass
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, field_validator
from rdflib import URIRef, Literal
from rdflib.namespace import RDF, RDFS

from backend.core.graph_store import PROMO, get_store
from backend.ontology.models import VariableRecord
from backend.core.deps import editable_param, graph_param, resolve_graph
from backend.ontology.rdf_context import RdfContext, scoped_context

from .checker import INSTANTIATE_CLASSES, check
from .codegen import TARGETS, render
from .compile_space import CompileSpace, Index, Variable
from .context import DictContext
from .document import (
    PdfCompileError,
    build_document,
    compile_pdf,
    pdf_available,
    validate_latex_alias,
)

from .errors import VarError
from .parser import ParseError, parse
from .syntax import Instantiate, Node, Var
from .units import Units

import copy

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
    domain_iri: Optional[str] = None
    incidence_list: List[str] = Field(default_factory=list)
    doc: str = ""
    created: Optional[str] = None
    modified: Optional[str] = None


# Variable labels must be valid expression-language identifiers — the
# same rule the lexer applies (parser.py): letters, digits, underscore,
# not starting with a digit.  The ``!`` qualifier is for references,
# never part of a variable's own label.
_VARIABLE_LABEL_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class VariableIn(BaseModel):
    iri: str
    label: str
    network: str
    domain_iri: Optional[str] = None
    type: str = "state"
    units: List[int] = Field(default_factory=lambda: [0] * 8)
    index_structures: List[str] = Field(default_factory=list)
    internal_id: Optional[str] = None
    aliases: Dict[str, str] = Field(default_factory=dict)
    doc: str = ""
    port_variable: bool = False
    tokens: List[str] = Field(default_factory=list)
    value: Optional[str] = None  # pre-bound promo:value (constants)
    equations: Dict[str, EquationIn] = Field(default_factory=dict)
    # Multi-axis classifications: axis IRI -> axis term IRI.
    classifications: Dict[str, str] = Field(default_factory=dict)

    @field_validator("label")
    @classmethod
    def _label_is_identifier(cls, v: str) -> str:
        if not _VARIABLE_LABEL_RE.match(v):
            raise ValueError(
                f"invalid variable label {v!r}: must match "
                "[a-zA-Z_][a-zA-Z0-9_]*"
            )
        return v


class IndexIn(BaseModel):
    iri: str
    label: str
    network: str = "root"
    domain_iri: Optional[str] = None
    index_class: str = "index"
    aliases: Dict[str, str] = Field(default_factory=dict)
    token: Optional[str] = None
    short_name: Optional[str] = None
    sub_index_of: Optional[str] = None
    selector: Optional[str] = None


class CheckRequest(BaseModel):
    text: str
    variables: List[VariableIn] = Field(default_factory=list)
    indices: List[IndexIn] = Field(default_factory=list)
    variable_definition_network: str = "root"
    variable_definition_domain_iri: Optional[str] = None
    expression_definition_network: str = "root"
    expression_definition_domain_iri: Optional[str] = None
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


class GenerateRequest(CheckRequest):
    target: str = "python"  # "python" | "matlab" | "latex"


class GenerateResponse(BaseModel):
    ok: bool
    code: Optional[str] = None
    error: Optional[str] = None
    error_kind: Optional[str] = None
    candidates: Optional[List[Dict[str, Any]]] = None


class ContextResponse(BaseModel):
    variables: List[VariableIn] = Field(default_factory=list)
    indices: List[IndexIn] = Field(default_factory=list)
    network_tree: Dict[str, List[str]] = Field(default_factory=dict)
    # Classification axes with their terms — drives the per-axis
    # dropdowns in the variable editors.  Domains are included so the
    # UI can map a variable's network (a domain name) to axis ancestry.
    axes: List[Dict[str, Any]] = Field(default_factory=list)
    domains: List[Dict[str, Any]] = Field(default_factory=dict)
    # Host capabilities the UI adapts to — e.g. {"pdf": false} when no
    # TeX toolchain is installed (default Docker image).
    capabilities: Dict[str, bool] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/context", response_model=ContextResponse)
def context_endpoint(
    graph_iri: Optional[str] = Depends(graph_param),
) -> ContextResponse:
    """Load the equation context from the RDF graph store.

    ``?graph=<iri>`` scopes resolution to the artefact plus its
    transitive ``usesOntology`` pin set (R4); absent, the legacy
    dataset-wide scope applies.
    """
    ctx = scoped_context(get_store(), graph_iri)

    variables = []
    for v in ctx.variables().values():
        variables.append(
            VariableIn(
                iri=v.iri,
                label=v.label,
                network=v.network,
                domain_iri=v.domain_iri,
                type=v.type,
                units=v.units.as_list(),
                index_structures=v.index_structures,
                internal_id=v.internal_id,
                aliases=v.aliases,
                doc=v.doc,
                port_variable=v.port_variable,
                tokens=v.tokens,
                value=getattr(v, "value", None),
                equations=getattr(v, "equations", {}),
                classifications=getattr(v, "classifications", {}),
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
                domain_iri=i.domain_iri,
                index_class=i.index_class,
                aliases=i.aliases,
                token=i.token,
                short_name=short,
                sub_index_of=i.sub_index_of,
                selector=i.selector,
            )
        )

    return ContextResponse(
        variables=variables,
        indices=indices,
        network_tree=ctx.tree(),
        axes=ctx.axes(),
        domains=ctx.domains(),
        capabilities={"pdf": pdf_available()},
    )


@router.post("/parse", response_model=ParseResponse)
def parse_endpoint(req: ParseRequest) -> ParseResponse:
    try:
        node = parse(req.text)
    except ParseError as e:
        return ParseResponse(ok=False, error=str(e))
    return ParseResponse(ok=True, ast=node_to_dict(node))


def _build_space(req: CheckRequest) -> CompileSpace:
    """Assemble the ``CompileSpace`` a request's expression runs against."""
    variables = {
        v.iri: Variable(
            iri=v.iri,
            label=v.label,
            network=v.network,
            domain_iri=v.domain_iri,
            type=v.type,
            units=Units.from_list(v.units),
            index_structures=v.index_structures,
            internal_id=v.internal_id,
            aliases=v.aliases,
            doc=v.doc,
            port_variable=v.port_variable,
            tokens=v.tokens,
            value=v.value,
        )
        for v in req.variables
    }
    indices = {
        i.iri: Index(
            iri=i.iri,
            label=i.label,
            network=i.network,
            domain_iri=i.domain_iri,
            index_class=i.index_class,
            aliases=i.aliases,
            token=i.token,
            sub_index_of=i.sub_index_of,
            selector=i.selector,
        )
        for i in req.indices
    }
    ctx = DictContext(variables, indices, tree=req.network_tree)
    return CompileSpace(
        ctx.variables(),
        ctx.indices(),
        variable_definition_network=req.variable_definition_network,
        variable_definition_domain_iri=req.variable_definition_domain_iri,
        expression_definition_network=req.expression_definition_network,
        expression_definition_domain_iri=req.expression_definition_domain_iri,
        accessible_networks=ctx.accessible_networks(req.expression_definition_network),
        network_tree=ctx.tree(),
    )


@router.post("/check", response_model=CheckResponse)
def check_endpoint(req: CheckRequest) -> CheckResponse:
    space = _build_space(req)

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


@router.post("/generate", response_model=GenerateResponse)
def generate_endpoint(req: GenerateRequest) -> GenerateResponse:
    """Parse + check + render an expression to a codegen target.

    Same context contract as ``/check``; the target selects the output
    language (``python`` | ``matlab`` | ``latex``).
    """
    if req.target not in TARGETS:
        return GenerateResponse(
            ok=False,
            error="unknown target %r (expected one of %s)" % (req.target, TARGETS),
            error_kind="target",
        )
    space = _build_space(req)

    try:
        node = parse(req.text)
        lhs = Var(req.lhs) if req.lhs else None
        checked = check(node, space, lhs)
        code = render(checked, space, req.target, lhs=req.lhs)
    except ParseError as e:
        return GenerateResponse(ok=False, error=str(e), error_kind="parse")
    except VarError as e:
        resp = GenerateResponse(
            ok=False, error=str(e), error_kind=type(e).__name__
        )
        if hasattr(e, "candidates"):
            resp.candidates = e.candidates
        return resp

    return GenerateResponse(ok=True, code=code)


@router.get("/document")
def document_endpoint(
    format: str = "tex",
    graph_iri: Optional[str] = Depends(graph_param),
) -> Response:
    """Printable LaTeX document of the context's variables and equations.

    Ported from old-ProMo's EquationEditor_v01 Jinja templates: a
    landscape article with hyperlinked variable/equation tables sectioned
    by network.  ``?graph=`` scopes the context as in ``/context``.
    ``?format=pdf`` compiles the source with pdflatex and returns the
    PDF inline (browser tab = viewer); a compile failure returns the
    log tail as plain text.
    """
    ctx = scoped_context(get_store(), graph_iri)
    tex = build_document(ctx)
    if format == "pdf":
        try:
            pdf = compile_pdf(tex)
        except PdfCompileError as exc:
            return PlainTextResponse(
                "LaTeX compile failed:\n\n%s" % exc, status_code=500)
        return Response(
            pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'inline; filename="document.pdf"'
            },
        )
    return PlainTextResponse(
        tex,
        media_type="application/x-latex",
        # inline keeps the open-in-tab preview; the filename gives the
        # browser's Save-As a compilable .tex name (not .latex).
        headers={
            "Content-Disposition": 'inline; filename="document.tex"'
        },
    )


# ---------------------------------------------------------------------------
# Variable CRUD (variables and their nested equations live in the equation editor)
# ---------------------------------------------------------------------------


def _instantiate_protos(record: VariableRecord) -> List[str]:
    """Auto-classify ``Instantiate`` equations on the record and return the
    prototype labels they reference (ADR-008)."""
    protos: List[str] = []
    for eq in record.equations.values():
        try:
            node = parse(eq.rhs or "")
        except ParseError:
            continue
        if isinstance(node, Instantiate):
            eq.equation_class = "instantiate"
            protos.append(node.var.name)
    return protos


def _proto_iri(graph, label: str, network: Optional[str]) -> Optional[URIRef]:
    """Resolve a prototype label to a variable IRI in ``graph`` —
    same-network match preferred."""
    candidates = [
        s for s in graph.subjects(RDF.type, PROMO["Variable"])
        if str(graph.value(s, RDFS.label) or "") == label
    ]
    if not candidates:
        return None
    for s in candidates:
        if str(graph.value(s, PROMO["network"]) or "") == (network or ""):
            return s
    return candidates[0]


def _link_instances(graph, var_iri: URIRef, protos: List[str],
                    network: str) -> None:
    """Write ``promo:instanceOf`` links from the new variable to each
    prototype it instantiates (ADR-008)."""
    for name in protos:
        qnet, _, qlabel = name.partition("!")
        proto = _proto_iri(graph, qlabel or name, qnet or network)
        if proto is not None:
            graph.add((var_iri, PROMO["instanceOf"], proto))


def _class_from_classifications(graph, classifications) -> Optional[str]:
    """Derive the legacy ``variableClass`` from the classifications map.

    Any classified term labelled ``constant``|``parameter`` wins (the
    same rule the lexer applies (parser.py): letters, digits, underscore,
    not starting with a digit.  The ``!`` qualifier is for references,
    never part of a variable's own label.
    """
    if not classifications:
        return None
    for term_iri in classifications.values():
        label = graph.value(URIRef(term_iri), RDFS.label)
        if label is not None and str(label) in INSTANTIATE_CLASSES:
            return str(label)
    return "state"


def _resolve_record_domains(store, graph_iri: Optional[str], record: VariableRecord) -> None:
    domains = scoped_context(store, graph_iri).domains()
    by_iri = {domain["iri"]: domain for domain in domains}
    by_name = {domain["name"]: domain for domain in domains}

    def resolve(name: Optional[str], iri: Optional[str]) -> "tuple[str, str]":
        domain = by_iri.get(iri) if iri else by_name.get("universe" if name == "root" else name)
        if domain is None:
            raise HTTPException(
                status_code=422,
                detail={"field": "domain_iri", "message": "Unknown domain"},
            )
        return domain["name"], domain["iri"]

    record.network, record.domain_iri = resolve(record.network, record.domain_iri)
    for equation in record.equations.values():
        equation.network, equation.domain_iri = resolve(
            equation.network or record.network,
            equation.domain_iri or (record.domain_iri if equation.network == record.network else None),
        )


@router.post("/variables", response_model=VariableRecord)
def create_variable(
    record: VariableRecord,
    graph_iri: Optional[str] = Depends(editable_param),
) -> VariableRecord:
    """Create a new variable (with nested equations) in the selected
    artefact graph (default: the working ontology)."""
    _validate_variable_latex(record)
    store = get_store()
    _resolve_record_domains(store, graph_iri, record)
    graph = resolve_graph(store, graph_iri)

    if not record.iri:
        record.iri = str(store.mint_iri(graph.identifier, record.internal_id or store.next_internal_id("V")))
    if not record.internal_id:
        record.internal_id = store.next_internal_id("V")

    # POST doubles as the editor's update path (the frontend never PUTs):
    # enforce the mutability guard and replace — not merge — when the
    # variable already exists.
    move_plan = _plan_domain_move(store, graph, record.iri, record, graph_iri)
    _guard_structural_edit(store, graph, record.iri, record, graph_iri,
                           domain_move_planned=bool(move_plan))
    _remove_variable(graph, URIRef(record.iri))

    protos = _instantiate_protos(record)
    var = record.model_dump()
    # Bridge: the legacy variableClass literal is what checker/builder
    # read (INSTANTIATE_CLASSES).  Derive it from the classifications —
    # a term labelled constant|parameter on any axis wins; classified
    # but neither means a solved variable ("state").  Unclassified
    # variables keep the explicit variable_class.
    derived_class = _class_from_classifications(graph, record.classifications)
    if derived_class is not None:
        var["variable_class"] = derived_class
        var["type"] = derived_class
    elif var.get("variable_class"):
        var["type"] = var["variable_class"]
    var_iri = store.add_variable_dict(graph, var)
    _link_instances(graph, var_iri, protos, record.network)
    _apply_domain_move(graph, move_plan)
    return record


@router.put("/variables/{iri:path}", response_model=VariableRecord)
def update_variable(
    iri: str,
    record: VariableRecord,
    graph_iri: Optional[str] = Depends(editable_param),
) -> VariableRecord:
    """Replace a variable in the selected artefact graph.

    Structural fields are locked while the variable is referenced by an
    equation — changing them then returns 409 with the referencers.
    """
    _validate_variable_latex(record)
    store = get_store()
    _resolve_record_domains(store, graph_iri, record)
    graph = resolve_graph(store, graph_iri)

    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Variable not found")

    move_plan = _plan_domain_move(store, graph, iri, record, graph_iri)
    _guard_structural_edit(store, graph, iri, record, graph_iri,
                           domain_move_planned=bool(move_plan))
    _remove_variable(graph, subject)
    record.iri = iri
    protos = _instantiate_protos(record)
    var_iri = store.add_variable_dict(graph, record.model_dump())
    _link_instances(graph, var_iri, protos, record.network)
    _apply_domain_move(graph, move_plan)
    return record


# ---------------------------------------------------------------------------
# Variable mutability — usage guard
# ---------------------------------------------------------------------------
# Policy (design doc §18): while a variable is referenced by an equation its
# structural fields are locked — units, index structures, tokens,
# classifications, port_variable, network and the reference-key names
# (internal_id, global_ID, internal_code).  Surface names (label, latex,
# doc, codegen aliases) and the value slot stay free.  Usage is scanned
# dataset-wide: ``usesOntology`` pins make references cross-artefact.

_STRUCTURAL_ALIASES = ("global_ID", "internal_code")


def _reference_tokens(var) -> List[str]:
    """Surface forms by which an rhs token stream can denote ``var``."""
    toks = {var.iri, var.internal_id}
    toks.update(var.aliases.get(k) for k in _STRUCTURAL_ALIASES)
    return sorted(t for t in toks if t)


def _token_in_rhs(rhs: str, token: str) -> bool:
    """Whole-token match — ``V_1`` must not match inside ``V_12``."""
    return re.search(
        r"(?<![A-Za-z0-9_])" + re.escape(token) + r"(?![A-Za-z0-9_])",
        rhs,
    ) is not None


def _variable_references(store, iri: str) -> List[Dict[str, str]]:
    """Equations referencing variable ``iri``, scanned over all graphs.

    ``via`` is ``lhs`` for the variable's own defining equation(s) and
    ``incidence``/``rhs`` for foreign references.
    """
    subject = URIRef(iri)
    var = RdfContext(store).variables().get(iri)
    tokens = _reference_tokens(var) if var is not None else [iri]
    refs: List[Dict[str, str]] = []
    for g in store.dataset.graphs():
        for eq in g.subjects(RDF.type, PROMO["Equation"]):
            via = None
            if g.value(eq, PROMO["lhs"]) == subject:
                via = "lhs"
            else:
                inc = g.value(eq, PROMO["incidenceList"])
                if inc is not None:
                    try:
                        if iri in json.loads(str(inc)):
                            via = "incidence"
                    except (TypeError, ValueError):
                        pass
                if via is None:
                    rhs = g.value(eq, PROMO["rhs"])
                    if rhs is not None and any(
                        _token_in_rhs(str(rhs), t) for t in tokens
                    ):
                        via = "rhs"
            if via is not None:
                refs.append({
                    "equation": str(eq),
                    "graph": str(g.identifier),
                    "via": via,
                })
    return refs


def _rewrite_reference(rhs: str, old, destination: str) -> str:
    """Qualify occurrences that can denote ``old`` with its destination."""
    qualified = f"{destination}!{old.label}"
    candidates = [f"{old.network}!{old.label}", old.label]
    candidates.extend(_reference_tokens(old))
    rewritten = rhs
    for token in sorted(set(candidates), key=len, reverse=True):
        if token and token != qualified:
            rewritten = re.sub(
                r"(?<![A-Za-z0-9_!])" + re.escape(token)
                + r"(?![A-Za-z0-9_])",
                qualified,
                rewritten,
            )
    return rewritten


def _plan_domain_move(store, graph, iri: str, record: VariableRecord,
                      graph_iri: Optional[str]) -> List["tuple[URIRef, str, List[str], str]"]:
    """Return validated equation rewrites needed to preserve a moved variable."""
    if (URIRef(iri), None, None) not in graph:
        return []
    old = scoped_context(store, graph_iri).variables().get(iri)
    if old is None or (old.domain_iri == record.domain_iri
                       and old.network == record.network):
        return []

    context = scoped_context(store, graph_iri)
    variables = dict(context.variables())
    moved = copy.copy(old)
    moved.network = record.network
    moved.domain_iri = record.domain_iri
    variables[iri] = moved
    blocked: List[Dict[str, str]] = []
    for equation in record.equations.values():
        if equation.network == old.network:
            equation.network = record.network
            equation.domain_iri = record.domain_iri
        equation_network = equation.network or record.network
        space = CompileSpace(
            variables,
            context.indices(),
            variable_definition_network=record.network,
            expression_definition_network=equation_network,
            accessible_networks=context.accessible_networks(equation_network),
            network_tree=context.tree(),
        )
        try:
            checked = check(parse(equation.rhs), space, Var(record.label))
        except (ParseError, VarError) as exc:
            blocked.append({
                "equation": equation.iri,
                "graph": str(graph.identifier),
                "via": "lhs",
                "error": str(exc),
            })
            continue
        before = set(equation.incidence_list)
        if before and before != set(checked.incidence):
            blocked.append({
                "equation": equation.iri,
                "graph": str(graph.identifier),
                "via": "lhs",
                "error": "moving the defining equation would change an input binding",
            })
            continue
        equation.incidence_list = sorted(checked.incidence)
        equation.rhs_latex = render(checked, space, "latex")

    plan: List["tuple[URIRef, str, List[str], str]"] = []
    for ref in _variable_references(store, iri):
        if ref["via"] == "lhs":
            continue
        if ref["graph"] != str(graph.identifier):
            blocked.append(ref)
            continue
        equation = URIRef(ref["equation"])
        rhs = str(graph.value(equation, PROMO["rhs"]) or "")
        rewritten = _rewrite_reference(rhs, old, record.network)
        if rewritten == rhs:
            blocked.append(ref)
        else:
            equation_network = str(graph.value(equation, PROMO["network"])
                                   or "universe")
            space = CompileSpace(
                variables,
                context.indices(),
                variable_definition_network=equation_network,
                expression_definition_network=equation_network,
                accessible_networks=context.accessible_networks(equation_network),
                network_tree=context.tree(),
            )
            try:
                checked = check(parse(rewritten), space)
            except (ParseError, VarError) as exc:
                blocked.append({**ref, "error": str(exc)})
                continue
            if iri not in checked.incidence:
                blocked.append({**ref, "error": "rewritten reference changed binding"})
                continue
            stored_incidence = graph.value(equation, PROMO["incidenceList"])
            if stored_incidence is not None:
                try:
                    before = set(json.loads(str(stored_incidence)))
                except (TypeError, ValueError):
                    before = set()
                if before and before != set(checked.incidence):
                    blocked.append({**ref, "error": "other variable bindings would change"})
                    continue
            latex = render(checked, space, "latex")
            plan.append((equation, rewritten, sorted(checked.incidence), latex))
    if blocked:
        raise HTTPException(status_code=409, detail={
            "message": (
                "Domain move cannot preserve %d reference(s); they are "
                "outside the editable graph or cannot be qualified"
                % len(blocked)
            ),
            "locked_fields": ["network", "domain_iri"],
            "references": blocked,
        })
    return plan


def _apply_domain_move(
    graph, plan: List["tuple[URIRef, str, List[str], str]"],
) -> None:
    for equation, rhs, incidence, latex in plan:
        graph.set((equation, PROMO["rhs"], Literal(rhs)))
        graph.set((equation, PROMO["incidenceList"], Literal(json.dumps(incidence))))
        graph.set((equation, PROMO["rhsLatex"], Literal(latex)))


def _remove_variable(graph, subject: URIRef) -> None:
    """Remove a variable *and* its equation nodes — equations are nested
    records; dropping only the variable's triples would orphan rhs
    references that still mention other variables."""
    for eq in list(graph.objects(subject, PROMO["hasEquation"])):
        graph.remove((eq, None, None))
    graph.remove((subject, None, None))


def _guard_structural_edit(store, graph, iri: str,
                           record: VariableRecord,
                           graph_iri: Optional[str] = None,
                           domain_move_planned: bool = False) -> None:
    """409 when ``record`` changes structural fields of a variable that
    equations reference.  No-op when the variable does not exist in
    ``graph`` (plain create).

    ``old`` is resolved in the write-graph's own scope — the same view
    the editor fetched and submitted — not dataset-wide: a shadow copy
    in an artefact graph would otherwise diff against the ontology
    copy and produce phantom locked-field 409s."""
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        return
    old = scoped_context(store, graph_iri).variables().get(iri)
    changed = _structural_changes(old, record) if old is not None else []
    refs = _variable_references(store, iri)
    foreign_refs = [ref for ref in refs if ref["via"] != "lhs"]
    allowed = {"classifications", "variable_class"}
    if not foreign_refs or domain_move_planned:
        allowed.add("network")
        allowed.add("domain_iri")
    blocked = [field for field in changed if field not in allowed]
    if refs and blocked:
        raise HTTPException(status_code=409, detail={
            "message": (
                "Variable is referenced by %d equation(s); "
                "structural field(s) locked: %s"
                % (len(refs), ", ".join(blocked))
            ),
            "locked_fields": blocked,
            "references": refs,
        })


def _structural_changes(old, record: VariableRecord) -> List[str]:
    """Structural fields differing between the stored variable and the
    incoming record.  ``global_ID`` falls back to the IRI fragment (the
    reader's convention), so an absent alias is not a change."""
    fragment = record.iri.split("#")[-1].split("/")[-1]
    pairs = [
        ("units",
         old.units.as_list() if getattr(old, "units", None) else [0] * 8,
         list(record.units)),
        ("index_structures",
         sorted(getattr(old, "index_structures", [])),
         sorted(record.index_structures)),
        ("tokens",
         sorted(getattr(old, "tokens", [])),
         sorted(record.tokens)),
        ("classifications",
         dict(getattr(old, "classifications", {})),
         dict(record.classifications)),
        ("variable_class", getattr(old, "type", None),
         record.variable_class or None),
        ("port_variable", bool(getattr(old, "port_variable", False)),
         bool(record.port_variable)),
        ("network", getattr(old, "network", None), record.network),
        ("domain_iri", getattr(old, "domain_iri", None), record.domain_iri),
        ("internal_id", getattr(old, "internal_id", None),
         record.internal_id),
        ("alias:global_ID",
         getattr(old, "aliases", {}).get("global_ID") or fragment,
         record.aliases.get("global_ID") or fragment),
        ("alias:internal_code",
         getattr(old, "aliases", {}).get("internal_code"),
         record.aliases.get("internal_code")),
    ]
    return [name for name, before, after in pairs if before != after]


@router.get("/variables/{iri:path}/references")
def variable_references(iri: str) -> Dict[str, Any]:
    """Equations referencing the variable — lets the editor lock
    structural fields proactively (``used``) and explain 409s."""
    store = get_store()
    refs = _variable_references(store, iri)
    return {"iri": iri, "used": bool(refs), "references": refs}


@router.delete("/variables/{iri:path}")
def delete_variable(
    iri: str,
    graph_iri: Optional[str] = Depends(editable_param),
) -> Dict[str, str]:
    """Delete a variable from the selected artefact graph.

    Blocked (409) while *other* variables' equations reference it; its
    own equations are deleted with it.
    """
    store = get_store()
    graph = resolve_graph(store, graph_iri)
    subject = URIRef(iri)
    if (subject, None, None) not in graph:
        raise HTTPException(status_code=404, detail="Variable not found")
    refs = [r for r in _variable_references(store, iri) if r["via"] != "lhs"]
    if refs:
        raise HTTPException(status_code=409, detail={
            "message": (
                "Variable is referenced by %d equation(s) — remove the "
                "referencing equations first" % len(refs)
            ),
            "references": refs,
        })
    _remove_variable(graph, subject)
    return {"deleted": iri}


def _validate_variable_latex(record: VariableRecord) -> None:
    alias = (record.aliases or {}).get("latex", "").strip()
    if not alias:
        return
    error = validate_latex_alias(alias)
    if error:
        raise HTTPException(
            status_code=422,
            detail={"field": "aliases.latex", "message": error},
        )
