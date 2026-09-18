"""Tests for ``backend/equation/codegen.py``."""

import pytest

from .checker import check
from .codegen import render
from .compile_space import CompileSpace, Index, Variable
from .parser import parse
from .syntax import Call, Var
from .units import Units

T = "http://promo.example/index/T"
N = "http://promo.example/index/N"


def _space():
    """Same tiny context as the checker suite: rho[N], v[N], M[], N[N],
    x[t], A[N], rhoT[t], one[]."""
    t_idx = Index(iri=T, label="time", network="root",
                  aliases={"internal_code": "t"})
    n_idx = Index(iri=N, label="species", network="thermo",
                  aliases={"internal_code": "N"})

    def var(iri, iid, label, units, idx):
        return Variable(iri=iri, internal_id=iid, label=label,
                        network="thermo", type="state", units=units,
                        index_structures=idx)

    variables = {v.iri: v for v in [
        var("http://promo.example/var/rho", "V_1", "rho",
            Units(mass=1, length=-3), [N]),
        var("http://promo.example/var/v", "V_2", "v",
            Units(length=1, time=-1), [N]),
        var("http://promo.example/var/M", "V_3", "M", Units(mass=1), []),
        var("http://promo.example/var/N", "V_4", "N", Units(), [N]),
        var("http://promo.example/var/x", "V_5", "x",
            Units(length=1), [T]),
        var("http://promo.example/var/rhoT", "V_7", "rhoT",
            Units(mass=1, length=-3), [T]),
        var("http://promo.example/var/one", "V_8", "one", Units(), []),
    ]}
    indices = {i.iri: i for i in [t_idx, n_idx]}
    return CompileSpace(
        variables, indices,
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )


def gen(text, target, space=None, lhs=None):
    space = space or _space()
    checked = check(parse(text), space, Var(lhs) if lhs else None)
    return render(checked, space, target, lhs=lhs)


# -- python -----------------------------------------------------------------

def test_python_var_uses_internal_id():
    assert gen("rho", "python") == "V_1"


def test_python_add():
    assert gen("rho + rho", "python") == "V_1 + V_1"


def test_python_group():
    assert gen("( rho + rho )", "python") == "( V_1 + V_1 )"


def test_python_hadamard():
    assert gen("rho . v", "python") == "V_1 * V_2"


def test_python_expand():
    assert gen("rho : rhoT", "python") == "np.multiply.outer(V_1, V_7)"


def test_python_reduce_tensordot_axes():
    # rho[N] * v[N]: the shared index N sits at position 0 in both operands.
    assert gen("rho * v", "python") == \
        "np.tensordot(V_1, V_2, axes=([0], [0]))"


def test_python_power():
    assert gen("one ^ one", "python") == "V_8 ** V_8"


def test_python_reduce_sum():
    assert gen("reduceSum(rho, N)", "python") == "np.sum(V_1, axis=0)"


def test_python_product():
    assert gen("Product(N, N)", "python") == "np.prod(V_4, axis=0)"


def test_python_ufunc():
    assert gen("sin(one)", "python") == "np.sin(V_8)"


def test_python_instantiate():
    # Instantiate(expr, shape): LHS is the declared variable, arg1 is the
    # RHS, arg2 only supplies units/indices.
    assert gen("Instantiate(M, one)", "python", lhs="rho") == "V_1 = V_3"


def test_python_integral():
    out = gen("Integral(M :: M in [one, one])", "python")
    assert out == "scipy.integrate.quad(lambda V_3: V_3, V_8, V_8)"


def test_python_root():
    out = gen("Root(M + M)", "python", lhs="M")
    assert out == "scipy.optimize.fsolve(lambda V_3: V_3 + V_3, x0)"


def test_python_maxmin():
    assert gen("max(M, M)", "python") == "np.maximum(V_3, V_3)"
    assert gen("min(M, M)", "python") == "np.minimum(V_3, V_3)"


def test_python_diffs_emit_named_helpers():
    assert gen("TotalDiff(x, x)", "python") == "total_diff(V_5, V_5)"
    assert gen("ParDiff(x, x)", "python") == "par_diff(V_5, V_5)"


def test_python_call():
    # No functions are registered in the default symbol table, so build
    # the Call node directly (the parser only emits Call for registered
    # ``functions``).
    space = _space()
    node = Call(Var("userFunc"), (Var("M"), Var("one")))
    checked = check(node, space)
    assert render(checked, space, "python") == "userFunc(V_3, V_8)"
    assert render(checked, space, "latex") == \
        r"\mathrm{userFunc}\left( \mathit{M}, \mathit{one} \right)"


# -- matlab -----------------------------------------------------------------

def test_matlab_hadamard_einsum_no_reduce():
    # Shared indices become element-wise "pages" when nothing is reduced.
    assert gen("rho . v", "matlab") == "einsum(V_1, V_2)"


def test_matlab_expand_einsum_outer():
    # Disjoint index sets -> pure outer product, same call shape.
    assert gen("rho : rhoT", "matlab") == "einsum(V_1, V_7)"


def test_matlab_reduce_einsum_labels():
    assert gen("rho * v", "matlab") == "einsum(V_1, V_2, {'N'})"


def test_matlab_power():
    assert gen("one ^ one", "matlab") == "power(V_8, V_8)"


def test_matlab_reduce_sum_labels():
    assert gen("reduceSum(rho, N)", "matlab") == "reducesum(V_1, {'N'})"


def test_matlab_product_reducemult():
    assert gen("Product(N, N)", "matlab") == "reducemult(V_4, {'N'})"


def test_matlab_integral():
    assert gen("Integral(M :: M in [one, one])", "matlab") == \
        "integral(@(V_3) V_3, V_8, V_8)"


def test_matlab_root():
    assert gen("Root(M + M)", "matlab", lhs="M") == \
        "fzero(@(V_3) V_3 + V_3, x0)"


# -- latex ------------------------------------------------------------------

def test_latex_var_label_with_index_subscripts():
    assert gen("rho", "latex") == r"\mathit{rho}_{N}"
    assert gen("M", "latex") == r"\mathit{M}"


def test_latex_group():
    assert gen("( rho + rho )", "latex") == \
        r"\left( \mathit{rho}_{N} + \mathit{rho}_{N} \right)"


def test_latex_hadamard():
    assert gen("rho . v", "latex") == r"\mathit{rho}_{N} \circ \mathit{v}_{N}"


def test_latex_expand():
    assert gen("rho : rhoT", "latex") == \
        r"\mathit{rho}_{N} \otimes \mathit{rhoT}_{t}"


def test_latex_reduce_sums_shared_index():
    assert gen("rho * v", "latex") == \
        r"\sum_{N} \mathit{rho}_{N} \, \mathit{v}_{N}"


def test_latex_power():
    assert gen("one ^ one", "latex") == r"{\mathit{one}}^{\mathit{one}}"


def test_latex_ufunc():
    assert gen("sin(one)", "latex") == r"\sin\left( \mathit{one} \right)"
    assert gen("inv(M)", "latex") == r"{\mathit{M}}^{-1}"
    assert gen("sqrt(one)", "latex") == r"\sqrt{\mathit{one}}"


def test_latex_integral():
    assert gen("Integral(M :: M in [one, one])", "latex") == \
        r"\int_{\mathit{one}}^{\mathit{one}} \mathit{M} \, d\mathit{M}"


def test_latex_root():
    assert gen("Root(M + M)", "latex", lhs="M") == \
        r"\mathit{M} + \mathit{M} = 0"


def test_latex_pardiff():
    assert gen("ParDiff(x, x)", "latex") == \
        r"\frac{\partial \mathit{x}_{t}}{\partial \mathit{x}_{t}}"


def test_latex_instantiate():
    assert gen("Instantiate(M, one)", "latex", lhs="rho") == \
        r"\mathit{rho}_{N} := \mathit{M}"


# -- imported variables -------------------------------------------------------

def test_imported_var_gets_network_prefix_in_code():
    space = _space()
    space.variables["http://promo.example/var/ext"] = Variable(
        iri="http://promo.example/var/ext", internal_id="V_9",
        label="ext", network="upstream", type="state",
        units=Units(mass=1), index_structures=[],
    )
    assert gen("upstream!ext", "python", space) == "upstream_V_9"
    # LaTeX keeps the human label (network qualifier is a code concern).
    assert gen("upstream!ext", "latex", space) == r"\mathit{ext}"


def test_unknown_target_rejected():
    space = _space()
    checked = check(parse("rho"), space)
    with pytest.raises(Exception):
        render(checked, space, "fortran")
