"""LaTeX documentation — render the variable/equation context to a
printable document.

Ported from old-ProMo ``EquationEditor_v01`` Jinja templates
(``template_main/variables/equations.latex``): a landscape article with a
hyperlinked variables table (symbol, label, doc, type, units, equation
cross-refs) and an equations table (``lhs := rhs``, doc, layer), both
sectioned by network.  The old multi-file layout (one ``.tex`` per
ontology, ``\\input`` from a master) is collapsed into a single
self-contained document — an HTTP endpoint delivers one file.

Each equation's RHS is re-rendered through ``parse`` → ``check`` →
``codegen.render(.., "latex")`` so the document always reflects the
current expression language; a cached ``rhs_latex`` or a verbatim
fallback covers expressions that no longer parse/check.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import jinja2

from .checker import check
from .codegen import Renderer, tex_escape
from .compile_space import CompileSpace
from .parser import parse
from .syntax import Instantiate, Var

TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
# ``{{ name|tex }}`` — escape surface names (networks, labels) that land in
# LaTeX mode without a catcode safety net (e.g. \subsection titles).
_env.filters["tex"] = tex_escape


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Attribute-or-key access — equation records arrive as models or dicts."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _num(internal_id: str, prefix: str) -> str:
    """``V_12`` → ``12`` — the old templates key hyperlinks on the number."""
    return (internal_id or "").replace(prefix, "", 1)


def _var_symbol(var: Any, space: CompileSpace) -> str:
    """``\\mathit{label}_{N,t}`` — same shape as codegen's latex var name,
    but straight from the record (no name resolution needed).  A ``latex``
    alias is raw LaTeX and wins over the italicised label."""
    subs = [
        tex_escape(space.index_alias(i))
        for i in sorted(var.index_structures)
    ]
    alias = (_get(var, "aliases", {}) or {}).get("latex")
    if alias:
        base = alias
    else:
        label = tex_escape(var.label or var.iri)
        base = r"\mathit{%s}" % label
    # Brace the base: a verbatim alias may itself carry a subscript
    # (``r_z``) — ``{r_z}_{N}`` compiles, ``r_z_{N}`` is a double subscript.
    return "{%s}_{%s}" % (base, ",".join(subs)) if subs else base


def _rhs_latex(eq: Any, var: Any, ctx: Any) -> str:
    """Render an equation RHS to LaTeX: fresh check+render, then cached
    ``rhs_latex``, then a verbatim fallback."""
    rhs = _get(eq, "rhs", "")
    network = _get(eq, "network", None) or var.network
    if rhs:
        try:
            space = CompileSpace(
                ctx.variables(),
                ctx.indices(),
                variable_definition_network=var.network,
                expression_definition_network=network,
                accessible_networks=(
                    ctx.accessible_networks(network)
                    if hasattr(ctx, "accessible_networks")
                    else None
                ),
            )
            checked = check(parse(rhs), space, Var(var.label))
            # The equations table renders ``lhs := rhs`` itself — for an
            # Instantiate the rhs column is ``inst(proto)`` (ADR-008).
            if isinstance(checked.node, Instantiate):
                proto = Renderer(space, "latex", lhs=var.label).render(
                    checked.children[0])
                return r"\mathrm{inst}\left( %s \right)" % proto
            return Renderer(space, "latex", lhs=var.label).render(checked)
        except Exception:
            pass
    cached = _get(eq, "rhs_latex", "")
    if cached:
        return cached
    return r"\verb|%s|" % rhs if rhs else ""


def _inline_resources(tex: str) -> str:
    """Replace ``\\input{./resources/X}`` with the vendored file contents
    so the served document compiles standalone."""
    for name in ("defs", "defvars"):
        path = TEMPLATE_DIR / "resources" / ("%s.tex" % name)
        if path.exists():
            tex = tex.replace(
                "\\input{./resources/%s}" % name,
                "%% ---- inlined resources/%s.tex ----\n%s" % (
                    name, path.read_text()),
            )
    return tex


def build_document(ctx: Any) -> str:
    """Render the full LaTeX document for a context's variables/equations.

    ``ctx`` is a ``scoped_context`` result (RdfContext or DictContext):
    ``variables()``/``indices()`` return the compile-space objects.
    """
    variables = ctx.variables()
    indices = ctx.indices()
    # Symbol rendering only needs index aliases — the definition networks
    # are irrelevant here (per-equation spaces are built in _rhs_latex).
    space = CompileSpace(
        variables, indices,
        variable_definition_network="",
        expression_definition_network="",
    )

    var_groups: Dict[str, List[Dict[str, Any]]] = {}
    eq_groups: Dict[str, List[Dict[str, Any]]] = {}

    for var in sorted(
        variables.values(),
        key=lambda v: (v.network, v.type or "", v.internal_id or ""),
    ):
        eqs = _get(var, "equations", {}) or {}
        eq_ids = [
            _num(_get(e, "internal_id", ""), "E_")
            for e in eqs.values()
        ]
        var_groups.setdefault(var.network, []).append({
            "num": _num(var.internal_id, "V_"),
            "symbol": _var_symbol(var, space),
            "label": var.label or var.iri,
            "doc": (var.doc or "").replace("_", " "),
            "type": var.type or "",
            "units": var.units.pretty(),
            "eq_ids": [e for e in eq_ids if e],
        })

        for eq in eqs.values():
            net = _get(eq, "network", None) or var.network
            eq_groups.setdefault(net, []).append({
                "num": _num(_get(eq, "internal_id", ""), "E_"),
                "var_num": _num(var.internal_id, "V_"),
                "lhs": _var_symbol(var, space),
                "rhs": _rhs_latex(eq, var, ctx),
                "doc": (_get(eq, "doc", "") or "").replace("_", " "),
                "network": net.replace(">>>", "-->"),
            })

    template = _env.get_template("document.latex")
    return _inline_resources(
        template.render(var_groups=var_groups, eq_groups=eq_groups)
    )
