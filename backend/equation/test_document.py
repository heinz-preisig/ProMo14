"""Tests for ``backend/equation/document.py``."""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core import graph_store
from backend.main import app

from .compile_space import Index, Variable
from .document import (
    PdfCompileError,
    build_document,
    compile_pdf,
    pdf_available,
)
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
    rz = Variable(
        iri="http://promo.example/var/rz", internal_id="V_30", label="rz",
        network="thermo", type="state", units=Units(),
        index_structures=[N], aliases={"latex": "r_z"},
    )
    return _Ctx(
        {v.iri: v for v in [rho, M, J, rz]},
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
    assert r"{\mathit{rho}}_{N}" in tex
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
    assert r"{\mathit{rho}}_{N} + {\mathit{rho}}_{N}" in tex
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
    assert r"{\mathit{J}}_{A\_heat}" in tex
    assert r"\subsection{ mass\_balance }" in tex


def test_latex_alias_with_own_subscript_braced():
    tex = build_document(_ctx())
    # Verbatim alias ``r_z`` + index subscript: the base is braced and
    # its own subscript normalised — ``{r_{z}}_{N}`` compiles, while
    # ``r_z_{N}`` is a LaTeX double-subscript error.
    assert r"{r_{z}}_{N}" in tex


def test_variable_row_lists_equation_links():
    tex = build_document(_ctx())
    assert r'\hyperlink{"e:1"}' in tex
    assert r'\hyperlink{"e:2"}' in tex


@pytest.mark.skipif(shutil.which("pdflatex") is None,
                    reason="no TeX toolchain installed")
def test_generated_document_compiles_to_pdf():
    """End-to-end: the rendered .tex must survive a real pdflatex run."""
    pdf = compile_pdf(build_document(_ctx()))
    assert pdf.startswith(b"%PDF")


def test_compile_pdf_reports_log_tail():
    if shutil.which("pdflatex") is None:
        pytest.skip("no TeX toolchain installed")
    with pytest.raises(PdfCompileError) as exc:
        compile_pdf("\\documentclass{article}\\begin{document}\\undefinedcmd\n"
                    "\\end{document}")
    assert "undefinedcmd" in str(exc.value)


def test_context_reports_pdf_capability(tmp_path: Path, monkeypatch):
    """``GET /context`` advertises host capabilities; ``pdf`` mirrors
    ``pdf_available()`` so the UI can hide the link on TeX-less hosts
    (default Docker image)."""
    monkeypatch.setenv("PROMO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(graph_store, "_STORE", None)
    with TestClient(app) as client:
        r = client.get("/api/equation/context")
    monkeypatch.setattr(graph_store, "_STORE", None)
    assert r.status_code == 200
    assert r.json()["capabilities"]["pdf"] == pdf_available()
