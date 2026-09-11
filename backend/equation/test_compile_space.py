"""Tests for ``backend/equation/compile_space.py``."""

from .compile_space import CompileSpace, Index, Variable
from .errors import AmbiguousVariableError, VarError
from .units import Units


def _fixture():
    """Build a tiny two-network ontology context."""
    t_idx = Index(
        iri="http://promo.example/index/T",
        label="time",
        network="root",
        aliases={"internal_code": "t", "latex": "t"},
    )
    n_idx = Index(
        iri="http://promo.example/index/N",
        label="species",
        network="thermo",
        aliases={"internal_code": "N", "latex": "N"},
    )

    x = Variable(
        iri="http://promo.example/var/X",
        internal_id="V_1",
        label="X",
        network="thermo",
        type="state",
        units=Units(mass=1, length=-3),  # density-ish
        index_structures=[n_idx.iri],
    )
    y_thermo = Variable(
        iri="http://promo.example/var/Yt",
        internal_id="V_2",
        label="Y",
        network="thermo",
        type="state",
        units=Units(),
        index_structures=[],
    )
    y_fluid = Variable(
        iri="http://promo.example/var/Yf",
        internal_id="V_3",
        label="Y",
        network="fluid",
        type="transport",
        units=Units(length=1),  # length
        index_structures=[],
    )
    z_root = Variable(
        iri="http://promo.example/var/Zr",
        internal_id="V_4",
        label="Z",
        network="root",
        type="state",
        units=Units(),
        index_structures=[],
    )
    z_fluid = Variable(
        iri="http://promo.example/var/Zf",
        internal_id="V_5",
        label="Z",
        network="fluid",
        type="state",
        units=Units(mass=1),
        index_structures=[],
    )

    variables = {v.iri: v for v in [x, y_thermo, y_fluid, z_root, z_fluid]}
    indices = {i.iri: i for i in [t_idx, n_idx]}
    return variables, indices


def test_resolve_local_unqualified():
    variables, indices = _fixture()
    space = CompileSpace(
        variables,
        indices,
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )
    res = space.resolve("Y")
    assert res.variable.network == "thermo"
    assert res.imported is False


def test_resolve_qualified_imported():
    variables, indices = _fixture()
    space = CompileSpace(
        variables,
        indices,
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )
    res = space.resolve("fluid!Y")
    assert res.variable.network == "fluid"
    assert res.imported is True


def test_resolve_qualified_missing_raises():
    variables, indices = _fixture()
    space = CompileSpace(
        variables,
        indices,
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )
    try:
        space.resolve("fluid!X")
    except VarError:
        return
    raise AssertionError("expected VarError")


def test_resolve_globally_unique_auto_resolve():
    """The only X in the world is in thermo; asking from fluid resolves it."""
    variables, indices = _fixture()
    space = CompileSpace(
        variables,
        indices,
        variable_definition_network="thermo",
        expression_definition_network="fluid",
    )
    res = space.resolve("X")
    assert res.variable.network == "thermo"
    assert res.imported is True


def test_resolve_ambiguous_raises_with_candidates():
    variables, indices = _fixture()
    space = CompileSpace(
        variables,
        indices,
        variable_definition_network="thermo",
        expression_definition_network="root",
    )
    try:
        space.resolve("Y")
    except AmbiguousVariableError as e:
        assert e.symbol == "Y"
        assert len(e.candidates) == 2
        return
    raise AssertionError("expected AmbiguousVariableError")


def test_resolve_via_accessible_network():
    """A variable in an ancestor network resolves; a descendant's does not.

    Tree: root -> thermo -> fluid.  From ``thermo`` the accessible networks
    are ``{thermo, root}``.  ``Z`` exists in ``root`` (ancestor) and
    ``fluid`` (descendant, not visible) — so it resolves to root's ``Z``.
    """
    variables, indices = _fixture()
    space = CompileSpace(
        variables,
        indices,
        variable_definition_network="thermo",
        expression_definition_network="thermo",
        accessible_networks={"thermo", "root"},
    )
    res = space.resolve("Z")
    assert res.variable.network == "root"
    assert res.imported is True


def test_resolve_ambiguous_across_accessible_networks():
    """Two candidates in different ancestor networks -> ambiguous.

    From ``subfluid`` (child of fluid) the accessible set is
    ``{subfluid, fluid, thermo, root}``; ``Y`` lives in both ``thermo`` and
    ``fluid``, neither local — so it is ambiguous.
    """
    variables, indices = _fixture()
    space = CompileSpace(
        variables,
        indices,
        variable_definition_network="subfluid",
        expression_definition_network="subfluid",
        accessible_networks={"subfluid", "fluid", "thermo", "root"},
    )
    try:
        space.resolve("Y")
    except AmbiguousVariableError as e:
        assert e.symbol == "Y"
        assert len(e.candidates) == 2
        return
    raise AssertionError("expected AmbiguousVariableError")


def test_resolve_by_internal_id():
    variables, indices = _fixture()
    space = CompileSpace(
        variables,
        indices,
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )
    res = space.resolve("V_1")
    assert res.variable.label == "X"


def test_get_index_by_internal_code():
    variables, indices = _fixture()
    space = CompileSpace(
        variables,
        indices,
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )
    iri = space.get_index("N")
    assert iri == "http://promo.example/index/N"
    assert space.get_index("missing") is None


def test_inverse_indices_also_maps_labels():
    variables, indices = _fixture()
    space = CompileSpace(
        variables,
        indices,
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )
    assert space.get_index("species") == "http://promo.example/index/N"


def test_pretty_index_list():
    variables, indices = _fixture()
    space = CompileSpace(
        variables,
        indices,
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )
    assert space.pretty_index_list(
        ["http://promo.example/index/N", "http://promo.example/index/T"]
    ) == "[N, t]"


def test_new_temp():
    variables, indices = _fixture()
    space = CompileSpace(
        variables,
        indices,
        variable_definition_network="thermo",
        expression_definition_network="thermo",
    )
    assert space.new_temp() == "temp_0"
    assert space.new_temp() == "temp_1"


if __name__ == "__main__":
    import sys

    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:
                print(f"FAIL {name}: {e}")
                sys.exit(1)
    print("All tests passed")
