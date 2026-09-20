"""Tests for ``backend/equation/document.py``."""

from .compile_space import Index, Variable
from .document import build_document
from .units import Units

N = "http://promo.example/index/N"


class _Ctx:
    """Minimal stand-in for ``scoped_context`` results."""

    def __init__(self, variables, indices):
        self._v = variables
        self._i = indices

    def variables(self):
        return self._v

    def indices(self):
        return self._i

    def accessible_networks(self, net):
        return [net]


def _ctx():
    n_idx = Index(iri=N, label="species", network="thermo",
                  aliases={"internal_code": "N"})
    rho = Variable(
        iri="http://promo.example/var/rho", internal_id="V_1", label="rho",
        network="thermo", type="state", units=Units(mass=1, length=-3),
        index_structures=[N], doc="mass_density",
    )
    rho.equations = {
        "e1": {
            "internal_id": "E_1",
            "rhs": "rho + rho",
            "network": "thermo",
            "doc": "doubled density",
        },
        "e2": {
            "internal_id": "E_2",
            "rhs": "not parseable ][",
            "rhs_latex": r"\mathit{fallback}",
            "network": "thermo",
            "doc": "broken",
        },
    }
    M = Variable(
        iri="http://promo.example/var/M", internal_id="V_3", label="M",
        network="thermo", type="state", units=Units(mass=1),
        index_structures=[], doc="total mass",
    )
    ah_idx = Index(iri="http://promo.example/index/A_heat",
                   label="heat arcs", network="root",
                   aliases={"internal_code": "A_heat"})
    J = Variable(
        iri="http://promo.example/var/J", internal_id="V_20", label="J",
        network="mass_balance", type="state", units=Units(),
        index_structures=[ah_idx.iri], doc="heat flow",
    )
    return _Ctx(
        {v.iri: v for v in [rho, M, J]},
        {i.iri: i for i in [n_idx, ah_idx]},
    )


def test_document_structure():
    tex = build_document(_ctx())
    assert r"\documentclass[landscape]{article}" in tex
    assert r"\section{Variables}" in tex
    assert r"\section{Equations}" in tex
    assert r"\subsection{ thermo }" in tex
    assert r"\end{document}" in tex


def test_variable_rows():
    tex = build_document(_ctx())
    # symbol with index subscript, label verbatim, doc un-underscored
    assert r"\mathit{rho}_{N}" in tex
    assert r"\verb|rho|" in tex
    assert "mass density" in tex
    # hyperlink target keyed on the stripped number
    assert r'\hypertarget{"v:1"}' in tex
    # M has no index subscript
    assert r"\mathit{M}" in tex
    assert r"\mathit{M}_" not in tex


def test_equation_rows_render_rhs():
    tex = build_document(_ctx())
    # e1: fresh parse+check+render of "rho + rho"
    assert r"\mathit{rho}_{N} + \mathit{rho}_{N}" in tex
    assert ":=" in tex
    # cross-link back to the defining variable
    assert r'\hyperlink{"v:1"}' in tex
    assert r'\hypertarget{"e:1"}' in tex


def test_equation_rhs_falls_back_to_cached_latex():
    tex = build_document(_ctx())
    # e2's rhs does not parse -> cached rhs_latex is used
    assert r"\mathit{fallback}" in tex


def test_underscores_escaped_in_math_and_titles():
    tex = build_document(_ctx())
    # A_heat index alias: raw ``_`` inside ``_{...}`` would be a LaTeX
    # double-subscript error; the mass_balance network would break the
    # text-mode \subsection title.
    assert r"\mathit{J}_{A\_heat}" in tex
    assert r"\subsection{ mass\_balance }" in tex


def test_variable_row_lists_equation_links():
    tex = build_document(_ctx())
    assert r'\hyperlink{"e:1"}' in tex
    assert r'\hyperlink{"e:2"}' in tex
