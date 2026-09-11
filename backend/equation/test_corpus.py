"""Replay the ProMo13 expression corpus through the new parser/checker.

Reads ``var_equ_rdf.ttl`` — the real ProMo13 variable/equation export — and
decodes every ``promo:expression_list_E_N`` token sequence back to a source
string, then runs it through ``parser.parse`` and ``checker.check``.

Notes on the corpus:

- Expression tokens are IRIs: ``promo:minus``, ``promolg:Hadamard``,
  ``qudt:EnergyInternal``, ``promo:I_4``-style index references, etc.
- Index tokens ``I_n`` map to index resources via the ``rdf:_N
  promo:global_index_list`` position in each index block.
- ``index_structures`` are emitted empty in this export (the known ADR-005
  serialisation bug), so every variable is checked with an empty index list.
  Index-dependent operators (``*``, ``Product``) therefore raise
  ``IndexStructureError`` — those are recorded, not asserted.
- Units are absent from the export; all variables are dimensionless, so unit
  checks trivially pass. The corpus test's real value is **parse coverage**
  of the full grammar on real expressions.

The corpus path defaults to the ProMo13 checkout; override with
``PROMO13_CORPUS_TTL``. The test is skipped if the file is absent.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .checker import check
from .compile_space import CompileSpace, Index, Variable
from .context import DictContext
from .errors import VarError
from .parser import ParseError, parse
from .units import Units

CORPUS_TTL = os.environ.get(
    "PROMO13_CORPUS_TTL",
    "/home/heinz/1_Gits/CAM13/ProMo13/packages/Common/ontologies/var_equ_rdf.ttl",
)

# The domain tree is not exported in var_equ_rdf.ttl; this is the standard
# ProMo hierarchy (parent -> children) the corpus was authored against.
CORPUS_TREE = {
    "root": ["physical", "control", "info_processing"],
    "physical": ["macroscopic", "microscopic", "reactions"],
    "macroscopic": ["solid", "fluid", "energy"],
    "fluid": ["liquid", "gas"],
}


# ---------------------------------------------------------------------------
# Minimal block-based Turtle reader — enough for this file's regular shape.
# ---------------------------------------------------------------------------

def _blocks(text: str) -> List[str]:
    return [
        b for b in re.split(r"\n\s*\n", text)
        if b.strip() and not b.strip().startswith("@prefix")
    ]


def _field(block: str, name: str) -> Optional[str]:
    m = re.search(r'promo:%s\s+"([^"]*)"' % name, block)
    return m.group(1) if m else None


def _parse_network(value: Optional[str]) -> str:
    """The old TTL sometimes stores networks as Python list literals.

    If the value is a list, take the most specific (last) network; otherwise
    return the string or the default root.
    """
    if not value:
        return "root"
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value
    if isinstance(parsed, list) and parsed:
        return str(parsed[-1])
    return str(value)


def load_corpus(path: str):
    """Parse the corpus TTL into variables, indices and expression lists."""
    text = open(path).read()

    label_map: Dict[str, str] = {}      # promolg:/promo: token IRI -> surface
    variables: Dict[str, Variable] = {}
    indices: Dict[str, Index] = {}
    i_pos: Dict[str, str] = {}          # "I_4" -> index IRI
    expr_lists: Dict[str, List[str]] = {}   # E_N -> token IRIs
    var_exprs: Dict[str, str] = {}      # variable IRI -> first E_N
    expr_to_var: Dict[str, str] = {}    # E_N -> variable IRI
    exprlist_v: Dict[str, List[str]] = {}  # expression_list_V_N -> [E_N, ...]
    var_to_vn: Dict[str, str] = {}      # variable IRI -> V_N (resolved after V blocks)

    for b in _blocks(text):
        head = b.strip()

        m = re.match(r'(promolg|promo):(\w+)\s+rdfs:label\s+"([^"]*)"', head)
        if m:
            label_map["%s:%s" % (m.group(1), m.group(2))] = m.group(3)
            continue

        m = re.match(r'promo:expression_list_(E_\d+)\b', head)
        if m:
            toks = {
                int(t.group(1)): t.group(2)
                for t in re.finditer(
                    r'rdf:_(\d+)\s+((?:promo|promolg|qudt):\w+)', head
                )
            }
            expr_lists[m.group(1)] = [toks[i] for i in sorted(toks)]
            continue

        m = re.match(r'promo:expression_list_(V_\d+)\b', head)
        if m:
            ems = re.findall(r'rdf:_\d+\s+promo:expression_list_(E_\d+)', head)
            if ems:
                exprlist_v[m.group(1)] = ems
            continue

        m = re.match(r'(promo|qudt):(\w+)\s+a\s+promo:variable', head)
        if m:
            iri = "%s:%s" % (m.group(1), m.group(2))
            ev = re.search(
                r'promo:expression_list\s+promo:expression_list_(V_\d+)', head
            )
            variables[iri] = Variable(
                iri=iri,
                label=_field(head, "label") or m.group(2),
                network=_parse_network(_field(head, "network")) or "root",
                type=_field(head, "type") or "state",
                units=Units(),          # units absent from this export
                index_structures=[],    # emitted empty (ADR-005 known bug)
            )
            if ev:
                var_to_vn[iri] = ev.group(1)
            continue

        m = re.match(
            r'(promo|qudt):(\w+)\s+promo:label\s+"([^"]*)"\s*;', head, re.S,
        )
        if m and re.search(r'promo:type\s+"(index|block_index)"', head):
            iri = "%s:%s" % (m.group(1), m.group(2))
            pos = re.search(r'rdf:_(\d+)\s+promo:global_index_list', head)
            typ = re.search(r'promo:type\s+"(index|block_index)"', head).group(1)
            internal = "I_%s" % pos.group(1) if pos else m.group(3)
            indices[iri] = Index(
                iri=iri,
                label=m.group(3),
                network=_parse_network(_field(head, "network")) or "root",
                index_class=typ,
                aliases={"internal_code": internal},
            )
            if pos:
                i_pos["I_%s" % pos.group(1)] = iri
            continue

    # Variable blocks occur before the expression_list_V blocks in the TTL
    # file, so resolve the expression mapping now that all V blocks are known.
    for iri, vn in var_to_vn.items():
        eids = exprlist_v.get(vn, [""])
        if eids:
            var_exprs[iri] = eids[0]
            for eid in eids:
                expr_to_var[eid] = iri

    return label_map, variables, indices, i_pos, expr_lists, var_exprs, expr_to_var


def decode(tokens: List[str], label_map, variables, i_pos, indices) -> str:
    """Decode a token-IRI sequence to a source string.

    Expression tokens use the ``promo:`` namespace while their surface labels
    are declared on ``promolg:`` resources — check both.
    """
    out = []
    for tok in tokens:
        if tok in label_map:
            out.append(label_map[tok])
        elif tok.startswith("promo:") and "promolg:" + tok[6:] in label_map:
            out.append(label_map["promolg:" + tok[6:]])
        elif tok in variables:
            out.append(variables[tok].label)
        elif tok in i_pos:
            out.append(indices[i_pos[tok]].alias())
        else:
            out.append(tok.split(":")[-1])
    return " ".join(out)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _load():
    if not os.path.exists(CORPUS_TTL):
        return None
    return load_corpus(CORPUS_TTL)


def test_corpus_parses_all():
    corpus = _load()
    if corpus is None:
        print("SKIP: corpus not found at", CORPUS_TTL)
        return
    label_map, variables, indices, i_pos, expr_lists, _, _ = corpus
    failures = []
    for eid, toks in sorted(expr_lists.items(), key=lambda kv: int(kv[0][2:])):
        src = decode(toks, label_map, variables, i_pos, indices)
        try:
            parse(src)
        except ParseError as e:
            failures.append((eid, src, str(e)))
    for eid, src, err in failures:
        print("PARSE FAIL %s: %s  (%s)" % (eid, src, err))
    assert not failures, "%d corpus expressions failed to parse" % len(failures)


def _iri_tail(iri: str) -> str:
    """Return the fragment / last path segment of an IRI."""
    return iri.split("#")[-1].split("/")[-1]


def _rdf_context():
    """Try to load the real ontology via RdfStore/RdfContext.

    Returns ``(ctx, i_pos)`` on success, ``(None, None)`` if the graph store
    is unavailable or the data directory is missing.
    """
    try:
        from backend.core.graph_store import RdfStore
        from backend.ontology.rdf_context import RdfContext
    except ImportError:
        return None, None

    data_dir = os.environ.get(
        "PROMO13_DATA_DIR",
        str(
            Path(CORPUS_TTL).parents[4]
            / "Ontology_Repository"
            / "processes_distributed_no_interface_eqs"
        ),
    )
    if not os.path.isdir(data_dir):
        return None, None

    old = os.environ.get("PROMO_DATA_DIR")
    try:
        os.environ["PROMO_DATA_DIR"] = data_dir
        store = RdfStore()
        store.load()
        ctx = RdfContext(store)
    except Exception:
        return None, None
    finally:
        if old is None:
            os.environ.pop("PROMO_DATA_DIR", None)
        else:
            os.environ["PROMO_DATA_DIR"] = old

    i_pos = {
        _iri_tail(iri): iri
        for iri, idx in ctx.indices().items()
        if _iri_tail(iri).startswith("I_")
    }

    return ctx, i_pos


def test_corpus_check_report():
    """Run the checker over the corpus and report results.

    If the ProMo13 data directory is available, the real RdfContext is used
    for variables, indices, units and the domain tree.  The TTL export alone
    (no index structures) is used as a fallback and explains any remaining
    Reduce/Product failures.
    """
    corpus = _load()
    if corpus is None:
        print("SKIP: corpus not found at", CORPUS_TTL)
        return
    label_map, variables, indices, i_pos, expr_lists, var_exprs, expr_to_var = corpus

    rdf_ctx, rdf_i_pos = _rdf_context()
    if rdf_ctx is not None:
        # Use the real ontology, but keep any corpus-only variables as a
        # fallback (e.g. expression-level temporaries not in the v8 store).
        ctx_variables = dict(variables)
        ctx_variables.update(rdf_ctx.variables())
        # The RDF indices are the authoritative ones; the TTL indices use
        # different IRIs and would shadow the real index lookup.
        ctx_indices = dict(rdf_ctx.indices())
        ctx = DictContext(ctx_variables, ctx_indices, tree=rdf_ctx.tree())
        i_pos = rdf_i_pos or i_pos
    else:
        ctx = DictContext(variables, indices, tree=CORPUS_TREE)

    ok, failed = [], []
    for eid, toks in sorted(expr_lists.items(), key=lambda kv: int(kv[0][2:])):
        src = decode(toks, label_map, ctx.variables(), i_pos, ctx.indices())
        lhs_iri = expr_to_var.get(eid)
        lhs_net = ctx.variables()[lhs_iri].network if lhs_iri else "root"
        space = CompileSpace(
            ctx.variables(), ctx.indices(),
            variable_definition_network=lhs_net,
            expression_definition_network=lhs_net,
            accessible_networks=ctx.accessible_networks(lhs_net),
            network_tree=ctx.tree(),
        )
        try:
            node = parse(src)
            check(node, space)
            ok.append(eid)
        except (VarError, ParseError) as e:
            failed.append((eid, src, str(e).splitlines()[0]))

    print("check ok: %d / %d" % (len(ok), len(expr_lists)))
    for eid, src, err in failed:
        print("  CHECK FAIL %s: %s  (%s)" % (eid, src, err))
    # Hard assertion only on parse coverage; check failures are expected
    # where the export lost index_structures.


if __name__ == "__main__":
    import sys

    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except AssertionError as e:
                print("FAIL %s: %s" % (name, e))
                sys.exit(1)
    print("Done")
