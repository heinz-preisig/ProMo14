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

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import jinja2

from .checker import check
from .codegen import Renderer, tex_append_subscripts, tex_brace_subscripts, tex_doc, tex_escape, tex_suggest_alias
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
# ``{{ doc|texdoc }}`` — prose cells: full text-mode escaping,
# $...$ spans pass through so authored inline math still works.
_env.filters["texdoc"] = tex_doc


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
        base = tex_brace_subscripts(alias)
    else:
        label = tex_suggest_alias(var.label or var.iri)
        base = label
    # Brace the base: a verbatim alias may itself carry a subscript
    # (``r_z``) — ``{r_z}_{N}`` compiles, ``r_z_{N}`` is a double subscript.
    return tex_append_subscripts(base, subs)


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


def _breakable_math(tex: str) -> str:
    """Make a rendered expression wrappable in its table column.

    TeX cannot break a line inside ``\\left( ... \\right)`` — the
    renderer wraps nearly every subexpression in them, so long
    equations overflow no matter how the column is sized.  Peel the
    whole-span outer group (top-level operators become break points),
    then demote every remaining ``\\left(``/``\\right)`` to a plain
    paren — grouping is preserved, only auto-sizing is lost, and every
    operator in the formula is a legal break point."""
    if tex.startswith(r"\verb"):
        return tex
    while True:
        t = tex.strip()
        if not (t.startswith(r"\left(") and t.endswith(r"\right)")):
            break
        depth = 0
        peeled = False
        for m in re.finditer(r"\\left\(|\\right\)", t):
            depth += 1 if m.group() == r"\left(" else -1
            if depth == 0:
                if m.end() == len(t):   # opener's match closes the string
                    tex = t[len(r"\left("):m.start()]
                    peeled = True
                break
        if not peeled:
            break                       # not whole-span or unbalanced
    return tex.strip().replace(r"\left(", "(").replace(r"\right)", ")")


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


def validate_latex_alias(alias: str) -> Optional[str]:
    base = tex_brace_subscripts(alias.strip())
    symbol = tex_append_subscripts(base, [r"A\_validation", "N", "S"])
    depth = 0
    escaped = False
    for char in symbol:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return "unexpected closing brace"
    if escaped:
        return "incomplete command at end of alias"
    if depth:
        return "unclosed brace"
    if not pdf_available():
        return None
    source = (
        r"\documentclass{article}" "\n"
        r"\begin{document}" "\n"
        r"$%s$" "\n"
        r"\end{document}" "\n"
    ) % symbol
    try:
        compile_pdf(source)
    except PdfCompileError as exc:
        for line in str(exc).splitlines():
            if line.startswith("!"):
                return line[1:].strip()
        return str(exc).splitlines()[0]
    return None


class PdfCompileError(Exception):
    """LaTeX → PDF compilation failed; the message carries the log tail."""


def pdf_available() -> bool:
    """Whether this host can compile PDFs — gates the UI's PDF link and
    is reported via ``/context`` capabilities.  Requires a TeX Live
    toolchain (pdflatex); absent in the default Docker image unless
    built with ``WITH_TEX=true``."""
    return shutil.which("pdflatex") is not None


def _log_tail(work: Path, stdout: str) -> str:
    """Extract the useful part of a failed pdflatex run: the first ``!``
    error block if present, else the last lines of the log."""
    log = work / "document.log"
    text = log.read_text(errors="replace") if log.exists() else stdout
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("!"):
            return "\n".join(lines[i:i + 15])
    return "\n".join(lines[-30:])


def compile_pdf(tex: str) -> bytes:
    """Compile a standalone .tex source to PDF bytes via pdflatex.

    Runs in a throwaway directory with shell escape off; two passes so
    ``hyperref`` targets and ``\\tableofcontents`` settle.  Raises
    ``PdfCompileError`` when no TeX toolchain is installed or the run
    fails — the message holds the log tail for display.
    """
    pdflatex = shutil.which("pdflatex")
    if pdflatex is None:
        raise PdfCompileError(
            "pdflatex not found — install a TeX Live toolchain "
            "(or use ?format=tex for the source)")
    with tempfile.TemporaryDirectory(prefix="promo_doc_") as tmp:
        work = Path(tmp)
        (work / "document.tex").write_text(tex)
        for _ in range(2):
            try:
                proc = subprocess.run(
                    [pdflatex, "-interaction=nonstopmode", "-halt-on-error",
                     "-no-shell-escape", "document.tex"],
                    # bytes, not text=True: the log can carry raw
                    # font bytes that crash utf-8 decoding
                    cwd=work, capture_output=True, timeout=90,
                )
            except subprocess.TimeoutExpired:
                raise PdfCompileError("pdflatex timed out after 90 s")
            if proc.returncode != 0:
                raise PdfCompileError(_log_tail(
                    work, proc.stdout.decode("utf-8", "replace")))
        pdf = work / "document.pdf"
        if not pdf.exists():
            raise PdfCompileError("pdflatex produced no PDF")
        return pdf.read_bytes()


def _eq_class_label(eq: Any) -> str:
    """Equation-class IRI → readable label — ``eqclass_generic`` →
    ``generic``, ``constitutive_law`` → ``constitutive law``."""
    iri = _get(eq, "equation_class") or ""
    frag = iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return frag.replace("eqclass_", "").replace("_", " ") or "-"


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
            "sig": space.pretty_index_list(
                list(var.index_structures or [])),
            "units": var.units.latex(),
            "eq_ids": [e for e in eq_ids if e],
        })

        for eq in eqs.values():
            net = _get(eq, "network", None) or var.network
            eq_groups.setdefault(net, []).append({
                "num": _num(_get(eq, "internal_id", ""), "E_"),
                "var_num": _num(var.internal_id, "V_"),
                "lhs": _var_symbol(var, space),
                "rhs": _breakable_math(_rhs_latex(eq, var, ctx)),
                "doc": (_get(eq, "doc", "") or "").replace("_", " "),
                "eqclass": _eq_class_label(eq),
                "network": net.replace(">>>", "-->"),
            })

    template = _env.get_template("document.latex")
    return _inline_resources(
        template.render(var_groups=var_groups, eq_groups=eq_groups)
    )
