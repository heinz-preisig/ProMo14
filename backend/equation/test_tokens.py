"""Tests for the §24 token algebra: ``tokens.py`` + checker propagation."""

from .checker import check
from .compile_space import CompileSpace, Index, Variable
from .parser import parse
from .tokens import TokenVec, tadd, tmul, token_frag, tsub
from .units import Units

T_E = "https://w3id.org/promo/ontology#token_energy"
T_M = "https://w3id.org/promo/ontology#token_component_mass"
T_T = "https://w3id.org/promo/ontology#token_time"


def _var(iri, label, token_vector=None):
    return Variable(
        iri=iri, label=label, network="thermo", type="state",
        units=Units(), index_structures=[], token_vector=token_vector,
    )


def _space(*vars_):
    return CompileSpace(
        {v.iri: v for v in vars_}, {},
        variable_definition_network="thermo",
        expression_definition_network="thermo",
        accessible_networks={"thermo"},
    )


# -- TokenVec ---------------------------------------------------------------

def test_tokenvec_mul_sub_inverse():
    h = TokenVec.from_dict({T_E: 1, T_M: -1})       # molar enthalpy
    n = TokenVec.from_dict({T_M: 1, T_T: -1})       # molar flow
    e_dot = h * n
    assert e_dot == TokenVec.from_dict({T_E: 1, T_T: -1})
    assert e_dot.pretty() == "energy time^-1"
    # e_dot/h would give the flow back; e_dot - h = {component_mass:+1, time:-1}
    assert (e_dot - h).as_dict() == {T_M: 1, T_T: -1}
    assert e_dot.inverse().as_dict() == {T_E: -1, T_T: 1}


def test_tokenvec_zero_exponents_canonical():
    a = TokenVec.from_dict({T_E: 1, T_M: 0})
    assert a == TokenVec.single(T_E)
    assert a.is_empty() is False
    assert TokenVec.from_dict({}).is_empty()


def test_tokenvec_from_json_and_frag():
    v = TokenVec.from_json('{"token_energy": 1, "token_mass": -1}')
    assert v.as_dict() == {"token_energy": 1, "token_mass": -1}
    assert token_frag(T_E) == "energy"
    assert v.pretty() == "energy mass^-1"


def test_tokenvec_carries_membership():
    v = TokenVec.from_dict({T_E: 1, T_M: -1})
    assert v.carries(T_E)
    assert v.carries("token_energy")          # fragment key tolerated
    assert v.carries(T_M)                      # nonzero exponent (−1: intensive)
    assert not v.carries(T_T)                  # absent entirely


def test_optional_combinators_absorb_none():
    a = TokenVec.single(T_E)
    assert tmul(a, None) is None
    assert tsub(None, a) is None
    warnings = []
    assert tadd(a, TokenVec.single(T_M), warn=warnings.append) is None
    assert warnings and "mismatch" in warnings[0]
    assert tadd(a, TokenVec.single(T_E)) == a


# -- checker propagation -----------------------------------------------------

def test_checker_propagates_product_tokens():
    h = _var("v:h", "h", {T_E: 1, T_M: -1})
    n = _var("v:n", "n", {T_M: 1, T_T: -1})
    space = _space(h, n)
    checked = check(parse("( h . n )"), space)
    assert checked.tokens == TokenVec.from_dict({T_E: 1, T_T: -1})


def test_checker_partial_diff_subtracts():
    u = _var("v:U", "U", {T_E: 1})
    v = _var("v:V", "V", {T_M: 1})
    space = _space(u, v)
    checked = check(parse("ParDiff( U, V )"), space)
    assert checked.tokens == TokenVec.from_dict({T_E: 1, T_M: -1})


def test_checker_untracked_absorbs():
    h = _var("v:h", "h", {T_E: 1})
    flag = _var("v:d", "d")                    # no token_vector
    space = _space(h, flag)
    checked = check(parse("( h . d )"), space)
    assert checked.tokens is None
    assert space.warnings == []


def test_checker_sum_mismatch_warns():
    a = _var("v:a", "a", {T_E: 1})
    b = _var("v:b", "b", {T_M: 1})
    space = _space(a, b)
    checked = check(parse("( a + b )"), space)
    assert checked.tokens is None
    assert any("token mismatch" in w for w in space.warnings)


def test_checker_sqrt_even_exponents():
    # A var with a squared token signature, e.g. variance-like quantity.
    x2 = _var("v:x2", "x2", {T_E: 2})
    space = _space(x2)
    checked = check(parse("sqrt( x2 )"), space)
    assert checked.tokens == TokenVec.single(T_E)
