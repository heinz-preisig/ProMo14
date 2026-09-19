"""Tests for ``backend/equation/checker.py``."""

from .checker import check
from .compile_space import CompileSpace, Index, Variable
from .errors import IndexStructureError, UnitError, VarError
from .parser import parse
from .units import Units


def _space():
    """Tiny compile context used by the parser's test suite plus density/rate."""
    t_idx = Index(
        iri="http://promo.example/index/T",
        label="time",
        network="root",
        index_class="index",
        aliases={"internal_code": "t"},
    )
    n_idx = Index(
        iri="http://promo.example/index/N",
        label="species",
        network="thermo",
        index_class="index",
        aliases={"internal_code": "N"},
    )
    dx_idx = Index(
        iri="http://promo.example/index/dx",
        label="differential_space",
        network="thermo",
        index_class="index",
        aliases={"internal_code": "dx"},
    )

    rho = Variable(
        iri="http://promo.example/var/rho",
        internal_id="V_1",
        label="rho",
        network="thermo",
        type="state",
        units=Units(mass=1, length=-3),
        index_structures=[n_idx.iri],
    )
    v = Variable(
        iri="http://promo.example/var/v",
        internal_id="V_2",
        label="v",
        network="thermo",
        type="state",
        units=Units(length=1, time=-1),
        index_structures=[n_idx.iri],
    )
    M = Variable(
        iri="http://promo.example/var/M",
        internal_id="V_3",
        label="M",
        network="thermo",
        type="state",
        units=Units(mass=1),
        index_structures=[],
    )
    N = Variable(
        iri="http://promo.example/var/N",
        internal_id="V_4",
        label="N",
        network="thermo",
        type="state",
        units=Units(),
        index_structures=[n_idx.iri],
    )
    x = Variable(
        iri="http://promo.example/var/x",
        internal_id="V_5",
        label="x",
        network="thermo",
        type="state",
        units=Units(length=1),
        index_structures=[t_idx.iri],
    )
    A = Variable(
        iri="http://promo.example/var/A",
        internal_id="V_6",
        label="A",
        network="thermo",
        type="state",
        units=Units(mass=1, length=2, time=-2),
        index_structures=[n_idx.iri],
    )
    rhoT = Variable(
        iri="http://promo.example/var/rhoT",
        internal_id="V_7",
        label="rhoT",
        network="thermo",
        type="state",
        units=Units(mass=1, length=-3),
        index_structures=[t_idx.iri],
    )
    one = Variable(
        iri="http://promo.example/var/one",
        internal_id="V_8",
        label="one",
        network="thermo",
        type="constant",
        units=Units(),
        index_structures=[],
    )

    variables = {v.iri: v for v in [rho, v, M, N, x, A, rhoT, one]}
    indices = {i.iri: i for i in [t_idx, n_idx, dx_idx]}
    return CompileSpace(
        variables,
        indices,
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )


def test_simple_var():
    space = _space()
    node = parse("rho")
    c = check(node, space)
    assert c.units == Units(mass=1, length=-3)
    assert c.indices == ["http://promo.example/index/N"]


def test_add_compatible():
    space = _space()
    node = parse("rho + rho")
    c = check(node, space)
    assert c.units == Units(mass=1, length=-3)
    assert c.indices == ["http://promo.example/index/N"]


def test_add_incompatible_units():
    space = _space()
    # same index [N], different units -> UnitError
    node = parse("rho + v")
    try:
        check(node, space)
    except UnitError:
        return
    raise AssertionError("expected UnitError")


def test_add_incompatible_indices():
    space = _space()
    # same units, different indices -> IndexStructureError
    node = parse("rho + rhoT")
    try:
        check(node, space)
    except IndexStructureError:
        return
    raise AssertionError("expected IndexStructureError")


def test_reduce():
    space = _space()
    # rho and v both carry species index; reduce removes N
    node = parse("rho * v")
    c = check(node, space)
    assert c.units == Units(mass=1, length=-2, time=-1)
    assert c.indices == []


def test_reduce_with_index():
    space = _space()
    # explicit reduce over N: (rho[N], v[N]) removes the species index
    node = parse("rho * N v")
    c = check(node, space)
    assert c.units == Units(mass=1, length=-2, time=-1)
    assert c.indices == []


def test_hadamard():
    space = _space()
    # rho . N -> density per species (keeps N)
    node = parse("rho . N")
    c = check(node, space)
    assert c.units == Units(mass=1, length=-3)
    assert c.indices == ["http://promo.example/index/N"]


def test_expand_requires_disjoint_indices():
    space = _space()
    # rho : one -> one is a scalar (no index), so result is rho's index N
    node = parse("rho : one")
    c = check(node, space)
    assert c.indices == ["http://promo.example/index/N"]
    # both rho and v carry N -> common -> error
    node2 = parse("rho : v")
    try:
        check(node2, space)
    except IndexStructureError:
        return
    raise AssertionError("expected IndexStructureError")


def test_power_dimensionless():
    space = _space()
    # N ^ N with dimensionless N
    node = parse("N ^ N")
    c = check(node, space)
    assert c.units.is_dimensionless()
    assert c.indices == ["http://promo.example/index/N"]


def test_power_rejects_dimensioned_exponent():
    space = _space()
    node = parse("N ^ rho")
    try:
        check(node, space)
    except UnitError:
        return
    raise AssertionError("expected UnitError")


def test_ufunc_retain():
    space = _space()
    node = parse("abs(rho)")
    c = check(node, space)
    assert c.units == Units(mass=1, length=-3)


def test_ufunc_none_requires_dimensionless():
    space = _space()
    node = parse("sin(rho)")
    try:
        check(node, space)
    except UnitError:
        return
    raise AssertionError("expected UnitError")


def test_ufunc_inverse():
    space = _space()
    # inv(rho) has inverse density units
    node = parse("inv(rho)")
    c = check(node, space)
    assert c.units == Units(mass=-1, length=3)


def test_ufunc_loose():
    space = _space()
    node = parse("sign(rho)")
    c = check(node, space)
    assert c.units.is_dimensionless()


def test_instantiate():
    space = _space()
    # ADR-008: Instantiate(proto) — the instance inherits the prototype's
    # units and index structure; incidence is empty (the prototype is a
    # type-level reference, not a value dependency).  'one' is class
    # constant — an allowed LHS.
    c = check(parse("Instantiate(rho)"), space, parse("one"))
    assert c.units == Units(mass=1, length=-3)
    assert c.indices == ["http://promo.example/index/N"]
    assert c.incidence == frozenset()


def test_instantiate_lhs_class_enforced():
    space = _space()
    # 'rho' is class state — an instance must be constant|parameter.
    try:
        check(parse("Instantiate(M)"), space, parse("rho"))
    except VarError:
        return
    raise AssertionError("expected VarError for state-class LHS")


def test_instantiate_unknown_proto():
    space = _space()
    try:
        check(parse("Instantiate(nosuch)"), space, parse("one"))
    except VarError:
        return
    raise AssertionError("expected VarError for unknown prototype")


def test_total_diff():
    space = _space()
    # TotalDiff(A, x) -> energy / length units
    node = parse("TotalDiff(A, x)")
    c = check(node, space)
    assert c.units == Units(mass=1, length=1, time=-2)


def test_product():
    space = _space()
    # Product(N, N) removes species index; N is dimensionless -> OK
    node = parse("Product(N, N)")
    c = check(node, space)
    assert c.units.is_dimensionless()
    assert c.indices == []


def test_reduce_sum():
    space = _space()
    # reduceSum(rho, N) removes N from density
    node = parse("reduceSum(rho, N)")
    c = check(node, space)
    assert c.units == Units(mass=1, length=-3)
    assert c.indices == []


def test_root_finds_lhs():
    space = _space()
    # Root(expr) — the LHS variable must appear in the body
    node = parse("Root(rho + rho)")
    lhs = parse("rho")
    c = check(node, space, lhs)
    assert c.units == Units(mass=1, length=-3)
    assert c.indices == ["http://promo.example/index/N"]


def test_root_missing_dependency():
    space = _space()
    node = parse("Root(M)")
    lhs = parse("rho")
    try:
        check(node, space, lhs)
    except VarError:
        return
    raise AssertionError("expected VarError")


def test_root_requires_lhs():
    space = _space()
    node = parse("Root(rho)")
    try:
        check(node, space)
    except VarError:
        return
    raise AssertionError("expected VarError")


if __name__ == "__main__":
    import sys

    for name, fn in globals().items():
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:
                print(f"FAIL {name}: {e}")
                import traceback

                traceback.print_exc()
                sys.exit(1)
    print("All tests passed")
