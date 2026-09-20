"""Code generation — render a checked expression tree to target languages.

The renderer walks the ``Checked`` tree produced by ``checker.check`` rather
than the raw AST: every node carries its inferred index-IRI list, which is
what the tensor operators need (e.g. the position of a reduced index inside
each operand determines the ``tensordot`` axes).

Targets:

- ``python`` — NumPy/SciPy-flavoured code; variables render as their
  ``internal_id`` (ADR-005: internal IDs are the code-generation name).
- ``matlab`` — MATLAB code targeting the ``MultiDimVar`` library
  (``@MultiDimVar``, Einstein-notation operators): ``einsum`` for
  Hadamard/expand/contraction, ``reducesum``/``reducemult`` for index
  reductions — all keyed by index *labels* (the ``internal_code``
  aliases), not axis positions.
- ``latex`` — publication rendering; variables render as their human label
  with index subscripts from the index ``internal_code`` aliases.

Named-helper emissions (``total_diff``, ``par_diff``, ``solve``) mark spots
where the target runtime must supply a numerical implementation — the
expression language carries the semantics, the runtime supplies the solver.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .checker import Checked
from .compile_space import CompileSpace
from .errors import VarError
from .syntax import (
    Add, Call, Expand, Group, Hadamard, Instantiate, Integral, MaxMin,
    ParDiff, Power, Product, Reduce, ReduceSum, Root, TotalDiff, UFunc, Var,
)

TARGETS = ("python", "matlab", "latex")

# Unitary function name → target surface form.  Names not listed fall back
# to the raw function name (user functions render as plain calls).
_UFUNC_PY: Dict[str, str] = {
    "sin": "np.sin", "cos": "np.cos", "tan": "np.tan",
    "exp": "np.exp", "ln": "np.log", "log": "np.log10",
    "sqrt": "np.sqrt", "abs": "np.abs",
    "inv": "np.linalg.inv", "trans": "np.transpose",
    "diffSpace": "np.gradient",
}
_UFUNC_ML: Dict[str, str] = {
    "ln": "log", "log": "log10",
    "inv": "inv", "trans": "transpose",
    "diffSpace": "gradient",
}
_UFUNC_TEX: Dict[str, str] = {
    "sin": r"\sin", "cos": r"\cos", "tan": r"\tan",
    "exp": r"\exp", "ln": r"\ln", "log": r"\log",
}


def _san(name: str) -> str:
    """Sanitise a surface name into a code-legal identifier."""
    return re.sub(r"\W", "_", name)


def tex_escape(name: str) -> str:
    """Escape a surface name for math-mode LaTeX — ``A_heat`` → ``A\\_heat``.

    Index ``internal_code`` aliases and variable labels are atomic names,
    not math: a raw ``_`` inside ``_{...}`` is a double-subscript error.
    """
    return name.replace("_", r"\_")


class Renderer:
    """Render one ``Checked`` tree for one target."""

    def __init__(self, space: CompileSpace, target: str, lhs: Optional[str] = None):
        if target not in TARGETS:
            raise VarError("unknown codegen target %r (expected one of %s)"
                           % (target, TARGETS))
        self.space = space
        self.target = target
        self.lhs = lhs

    # -- variable naming ----------------------------------------------------

    def _var_name(self, node: Var) -> str:
        resolved = self.space.resolve(node.name)
        var = resolved.variable
        if self.target == "latex":
            subs = [
                tex_escape(self.space.index_alias(iri))
                for iri in sorted(var.index_structures)
            ]
            # A latex alias is raw LaTeX (e.g. "\rho", "\dot{m}") — render
            # verbatim; otherwise fall back to the italicised label.
            alias = var.aliases.get("latex")
            if alias:
                base = alias
            else:
                label = var.label or node.name
                base = r"\mathit{%s}" % tex_escape(label)
            return "%s_{%s}" % (base, ",".join(subs)) if subs else base
        name = _san(var.internal_id or var.label or node.name)
        if resolved.imported and var.network:
            return "%s_%s" % (_san(var.network), name)
        return name

    def _index_axis(self, checked: Checked, index_iri: str) -> int:
        """Position of an index IRI inside a checked node's index list."""
        try:
            return checked.indices.index(index_iri)
        except ValueError:
            raise VarError(
                "codegen: index %s not in node indices %s"
                % (index_iri, checked.indices)
            )

    def _index_name(self, iri: str) -> str:
        return self.space.index_alias(iri)

    def _tex_index(self, iri: str) -> str:
        """Index alias escaped for math-mode LaTeX."""
        return tex_escape(self._index_name(iri))

    def _ml_labels(self, iris: List[str]) -> str:
        """Matlab cell array of index labels, e.g. ``{'N','t'}``."""
        return "{%s}" % ",".join(
            "'%s'" % self._index_name(iri) for iri in iris)

    # -- dispatch -------------------------------------------------------------

    def render(self, c: Checked) -> str:
        node = c.node
        ch = c.children

        if isinstance(node, Var):
            var = self.space.resolve(node.name).variable
            # A variable with a pre-bound ``promo:value`` (universal
            # constants) renders as the literal in code targets — never
            # as its own LHS symbol though (ADR-008).
            if (self.target in ("python", "matlab")
                    and getattr(var, "value", None)
                    and node.name != self.lhs):
                return var.value
            return self._var_name(node)

        if isinstance(node, Group):
            inner = self.render(ch[0])
            if self.target == "latex":
                return r"\left( %s \right)" % inner
            return "( %s )" % inner

        if isinstance(node, Add):
            return "%s %s %s" % (self.render(ch[0]), node.op, self.render(ch[1]))

        if isinstance(node, Expand):
            left, right = self.render(ch[0]), self.render(ch[1])
            if self.target == "python":
                return "np.multiply.outer(%s, %s)" % (left, right)
            if self.target == "matlab":
                # einsum with no reduce labels: disjoint index sets give a
                # pure outer product.
                return "einsum(%s, %s)" % (left, right)
            return r"%s \otimes %s" % (left, right)

        if isinstance(node, Hadamard):
            left, right = self.render(ch[0]), self.render(ch[1])
            if self.target == "python":
                return "%s * %s" % (left, right)
            if self.target == "matlab":
                # einsum with no reduce labels: shared indices become
                # element-wise "pages", disjoint ones outer-product.
                return "einsum(%s, %s)" % (left, right)
            return r"%s \circ %s" % (left, right)

        if isinstance(node, Reduce):
            return self._render_reduce(node, ch)

        if isinstance(node, Power):
            base, exp = self.render(ch[0]), self.render(ch[1])
            if self.target == "python":
                return "%s ** %s" % (base, exp)
            if self.target == "matlab":
                return "power(%s, %s)" % (base, exp)
            return "{%s}^{%s}" % (base, exp)

        if isinstance(node, Instantiate):
            # ``lhs := inst(proto)`` — declares lhs as an instance of
            # proto: a bound-value slot filled at instantiation, not a
            # computed assignment (ADR-008).
            proto = self.render(ch[0])
            lhs_name = self._var_name(Var(self.lhs)) if self.lhs else "x"
            if self.target == "latex":
                return (r"%s := \mathrm{inst}\left( %s \right)"
                        % (lhs_name, proto))
            if self.target == "matlab":
                return ("%s = []; %% parameter: instance of %s"
                        % (lhs_name, proto))
            return ("%s = None  # parameter: instance of %s"
                    % (lhs_name, proto))

        if isinstance(node, Integral):
            body, var, lo, hi = (self.render(x) for x in ch)
            if self.target == "python":
                return ("scipy.integrate.quad(lambda %s: %s, %s, %s)"
                        % (var, body, lo, hi))
            if self.target == "matlab":
                return "integral(@(%s) %s, %s, %s)" % (var, body, lo, hi)
            return r"\int_{%s}^{%s} %s \, d%s" % (lo, hi, body, var)

        if isinstance(node, Product):
            index_iri = self.space.get_index(node.index.name)
            body = self.render(ch[0])
            axis = self._index_axis(ch[0], index_iri)
            if self.target == "python":
                return "np.prod(%s, axis=%d)" % (body, axis)
            if self.target == "matlab":
                return "reducemult(%s, %s)" % (
                    body, self._ml_labels([index_iri]))
            return r"\prod_{%s} %s" % (self._tex_index(index_iri), body)

        if isinstance(node, Root):
            body = self.render(ch[0])
            lhs = self._var_name(Var(self.lhs)) if self.lhs else "x"
            if self.target == "python":
                return "scipy.optimize.fsolve(lambda %s: %s, x0)" % (lhs, body)
            if self.target == "matlab":
                return "fzero(@(%s) %s, x0)" % (lhs, body)
            return r"%s = 0" % body

        if isinstance(node, MaxMin):
            a, b = self.render(ch[0]), self.render(ch[1])
            if self.target == "python":
                fn = "np.maximum" if node.which == "max" else "np.minimum"
                return "%s(%s, %s)" % (fn, a, b)
            if self.target == "matlab":
                return "%s(%s, %s)" % (node.which, a, b)
            return r"\%s\left( %s, %s \right)" % (node.which, a, b)

        if isinstance(node, TotalDiff):
            x, y = self.render(ch[0]), self.render(ch[1])
            if self.target == "python":
                return "total_diff(%s, %s)" % (x, y)
            if self.target == "matlab":
                return "totalDiff(%s, %s)" % (x, y)
            return r"\frac{\mathrm{d} %s}{\mathrm{d} %s}" % (x, y)

        if isinstance(node, ParDiff):
            x, y = self.render(ch[0]), self.render(ch[1])
            if self.target == "python":
                return "par_diff(%s, %s)" % (x, y)
            if self.target == "matlab":
                return "parDiff(%s, %s)" % (x, y)
            return r"\frac{\partial %s}{\partial %s}" % (x, y)

        if isinstance(node, ReduceSum):
            index_iri = self.space.get_index(node.index.name)
            body = self.render(ch[0])
            axis = self._index_axis(ch[0], index_iri)
            if self.target == "python":
                return "np.sum(%s, axis=%d)" % (body, axis)
            if self.target == "matlab":
                return "reducesum(%s, %s)" % (
                    body, self._ml_labels([index_iri]))
            return r"\sum_{%s} %s" % (self._tex_index(index_iri), body)

        if isinstance(node, UFunc):
            arg = self.render(ch[0])
            if self.target == "python":
                return "%s(%s)" % (_UFUNC_PY.get(node.name, "np." + node.name), arg)
            if self.target == "matlab":
                return "%s(%s)" % (_UFUNC_ML.get(node.name, node.name), arg)
            tex = _UFUNC_TEX.get(node.name)
            if tex:
                return r"%s\left( %s \right)" % (tex, arg)
            if node.name == "inv":
                return r"{%s}^{-1}" % arg
            if node.name == "sqrt":
                return r"\sqrt{%s}" % arg
            return r"\mathrm{%s}\left( %s \right)" % (node.name, arg)

        if isinstance(node, Call):
            args = ", ".join(self.render(x) for x in ch)
            name = node.name.name
            if self.target == "latex":
                return r"\mathrm{%s}\left( %s \right)" % (name, args)
            return "%s(%s)" % (_san(name), args)

        raise VarError("codegen: unknown node type %s" % type(node).__name__)

    # -- reduce (contraction) -------------------------------------------------

    def _render_reduce(self, node: Reduce, ch: List[Checked]) -> str:
        left, right = ch[0], ch[1]
        l_src, r_src = self.render(left), self.render(right)

        common = left.index_set() & right.index_set()
        if node.index:
            reduced_iri = self.space.get_index(node.index.name)
        else:
            reduced_iri = next(iter(common)) if len(common) == 1 else None

        if self.target == "latex":
            if reduced_iri:
                return r"\sum_{%s} %s \, %s" % (
                    self._tex_index(reduced_iri), l_src, r_src)
            return r"%s \, %s" % (l_src, r_src)

        # Contraction over the shared index: axis = its position inside each
        # operand's (sorted) index list.
        if reduced_iri is None:
            raise VarError("codegen: reduce has no resolvable index")
        if self.target == "matlab":
            # Label-based contraction: einsum(op1, op2, {'N'}).
            return "einsum(%s, %s, %s)" % (
                l_src, r_src, self._ml_labels([reduced_iri]))
        li = self._index_axis(left, reduced_iri)
        ri = self._index_axis(right, reduced_iri)
        return ("np.tensordot(%s, %s, axes=([%d], [%d]))"
                % (l_src, r_src, li, ri))


def render(
    checked: Checked,
    space: CompileSpace,
    target: str,
    lhs: Optional[str] = None,
) -> str:
    """Render a checked expression tree to ``target`` source code."""
    return Renderer(space, target, lhs=lhs).render(checked)
