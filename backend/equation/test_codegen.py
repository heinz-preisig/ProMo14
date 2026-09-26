"""Tests for ``backend/equation/codegen.py``."""

import pytest

from .checker import check
from .codegen import render, tex_suggest_alias
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

    def var(iri, iid, label, units, idx, type="state", value=None):
        return Variable(iri=iri, internal_id=iid, label=label,
                        network="thermo", type=type, units=units,
                        index_structures=idx, value=value)

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
        var("http://promo.example/var/one", "V_8", "one", Units(), [],
            type="constant"),
        var("http://promo.example/var/half", "V_10", "half", Units(), [],
            type="constant", value="0.5"),
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
    # ADR-008: Instantiate(proto) declares lhs as an instance — a
    # bound-value slot rendered as a parameter placeholder, never a copy
    # of the prototype's value.
    assert gen("Instantiate(M)", "python", lhs="one") == \
        "V_8 = None  # parameter: instance of V_3"


def test_python_constant_value_inlined():
    # A variable with a pre-bound promo:value renders as the literal.
    assert gen("half . M", "python") == "0.5 * V_3"


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
        r"\mathrm{userFunc}\left( M, one \right)"


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
    assert gen("rho", "latex") == r"{\rho}_{N}"
    assert gen("M", "latex") == r"M"


def _underscore_space():
    """A space whose index internal_code carries an underscore (A_heat)."""
    ah = Index(iri="http://promo.example/index/A_heat", label="heat arcs",
               network="root", aliases={"internal_code": "A_heat"})
    j = Variable(iri="http://promo.example/var/J", internal_id="V_20",
                 label="J", network="thermo", type="state",
                 units=Units(), index_structures=[ah.iri])
    return CompileSpace(
        {j.iri: j}, {ah.iri: ah},
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )


def test_latex_underscore_index_alias_escaped():
    # A raw ``_`` inside ``_{...}`` is a LaTeX double-subscript error.
    space = _underscore_space()
    assert gen("J", "latex", space) == r"{J}_{A\_heat}"
    assert gen("reduceSum(J, A_heat)", "latex", space) == \
        r"\sum_{A\_heat} {J}_{A\_heat}"


def test_matlab_underscore_index_alias_stays_raw():
    # Escaping is latex-only — matlab labels keep the real surface token.
    space = _underscore_space()
    assert gen("reduceSum(J, A_heat)", "matlab", space) == \
        "reducesum(V_20, {'A_heat'})"


def test_latex_group():
    assert gen("( rho + rho )", "latex") == \
        r"\left( {\rho}_{N} + {\rho}_{N} \right)"


def test_latex_hadamard():
    assert gen("rho . v", "latex") == r"{\rho}_{N} \circ {v}_{N}"


def test_latex_expand():
    assert gen("rho : rhoT", "latex") == \
        r"{\rho}_{N} \otimes {rhoT}_{t}"


def test_latex_reduce_sums_shared_index():
    assert gen("rho * v", "latex") == \
        r"\sum_{N} {\rho}_{N} \, {v}_{N}"


def test_latex_power():
    assert gen("one ^ one", "latex") == r"{one}^{one}"


def test_latex_ufunc():
    assert gen("sin(one)", "latex") == r"\sin\left( one \right)"
    assert gen("inv(M)", "latex") == r"{M}^{-1}"
    assert gen("sqrt(one)", "latex") == r"\sqrt{one}"


def test_latex_integral():
    assert gen("Integral(M :: M in [one, one])", "latex") == \
        r"\int_{one}^{one} M \, dM"


def test_latex_root():
    assert gen("Root(M + M)", "latex", lhs="M") == \
        r"M + M = 0"


def test_latex_pardiff():
    assert gen("ParDiff(x, x)", "latex") == \
        r"\frac{\partial {x}_{t}}{\partial {x}_{t}}"


def test_latex_alias_with_own_subscript_braced():
    # A verbatim latex alias may itself carry a subscript (``r_z``);
    # ``{r_z}_{N}`` compiles, ``r_z_{N}`` is a double-subscript error.
    n_idx = Index(iri=N, label="species", network="thermo",
                  aliases={"internal_code": "N"})
    rz = Variable(iri="http://promo.example/var/rz", internal_id="V_30",
                  label="rz", network="thermo", type="state",
                  units=Units(), index_structures=[N],
                  aliases={"latex": "r_z"})
    space = CompileSpace(
        {rz.iri: rz}, {n_idx.iri: n_idx},
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )
    # Unbraced subscript runs are braced — a bare ``_`` consumes one
    # token, so ``r_z`` alone renders ``r_z`` anyway but ``F_conv``
    # would render ``F_c`` + stray ``onv``.
    assert gen("rz", "latex", space) == r"r_{z,N}"


def test_latex_alias_multi_char_subscript_braced():
    # Real data: ``F_conv``'s alias is the label verbatim — a bare ``_``
    # would subscript only ``c``; bracing gives ``F_{conv}``.
    n_idx = Index(iri=N, label="species", network="thermo",
                  aliases={"internal_code": "N"})
    f = Variable(iri="http://promo.example/var/f", internal_id="V_31",
                 label="F_conv", network="thermo", type="state",
                 units=Units(), index_structures=[N],
                 aliases={"latex": "F_conv"})
    space = CompileSpace(
        {f.iri: f}, {n_idx.iri: n_idx},
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )
    assert gen("F_conv", "latex", space) == r"F_{conv,N}"


def test_latex_accented_alias_with_own_subscript_and_indices():
    n_idx = Index(iri=N, label="species", network="thermo",
                  aliases={"internal_code": "N"})
    flow = Variable(iri="http://promo.example/var/flow", internal_id="V_32",
                    label="flow", network="thermo", type="state",
                    units=Units(), index_structures=[N],
                    aliases={"latex": r"\hat{n}_conv"})
    space = CompileSpace(
        {flow.iri: flow}, {n_idx.iri: n_idx},
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )
    assert gen("flow", "latex", space) == r"\hat{n}_{conv,N}"


def test_latex_alias_with_outer_groups_and_own_subscript():
    n_idx = Index(iri=N, label="species", network="thermo",
                  aliases={"internal_code": "N"})
    flow = Variable(iri="http://promo.example/var/flow", internal_id="V_33",
                    label="flow", network="thermo", type="state",
                    units=Units(), index_structures=[N],
                    aliases={"latex": r"{{\tilde{n}_{conv}}}"})
    space = CompileSpace(
        {flow.iri: flow}, {n_idx.iri: n_idx},
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )
    assert gen("flow", "latex", space) == r"\tilde{n}_{conv,N}"


def test_latex_instantiate():
    assert gen("Instantiate(M)", "latex", lhs="one") == \
        r"one := \mathrm{inst}\left( M \right)"


def test_latex_alias_suggestion():
    assert tex_suggest_alias("rho") == r"\rho"
    assert tex_suggest_alias("rho_gas") == r"\rho_{gas}"
    assert tex_suggest_alias("T_wall") == r"T_{wall}"
    assert tex_suggest_alias("mass_flow") == r"mass_{flow}"


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
    assert gen("upstream!ext", "latex", space) == r"ext"


def test_unknown_target_rejected():
    space = _space()
    checked = check(parse("rho"), space)
    with pytest.raises(Exception):
        render(checked, space, "fortran")
