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

import os
import re
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


def load_corpus(path: str):
    """Parse the corpus TTL into variables, indices and expression lists."""
    text = open(path).read()

    label_map: Dict[str, str] = {}      # promolg:/promo: token IRI -> surface
    variables: Dict[str, Variable] = {}
    indices: Dict[str, Index] = {}
    i_pos: Dict[str, str] = {}          # "I_4" -> index IRI
    expr_lists: Dict[str, List[str]] = {}   # E_N -> token IRIs
    var_exprs: Dict[str, str] = {}      # variable IRI -> E_N
    exprlist_v: Dict[str, str] = {}     # expression_list_V_N -> E_N

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
            em = re.search(r'promo:expression_list_(E_\d+)', head)
            if em:
                exprlist_v[m.group(1)] = em.group(1)
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
                network=_field(head, "network") or "root",
                type=_field(head, "type") or "state",
                units=Units(),          # units absent from this export
                index_structures=[],    # emitted empty (ADR-005 known bug)
            )
            if ev:
                var_exprs[iri] = exprlist_v.get(ev.group(1), "")
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
                network="root",
                index_class=typ,
                aliases={"internal_code": internal},
            )
            if pos:
                i_pos["I_%s" % pos.group(1)] = iri
            continue

    return label_map, variables, indices, i_pos, expr_lists, var_exprs


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
    label_map, variables, indices, i_pos, expr_lists, _ = corpus
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


def test_corpus_check_report():
    """Run the checker over the corpus and report results.

    Index structures are empty in the export, so index-dependent operators
    legitimately fail; this test reports rather than asserts.
    """
    corpus = _load()
    if corpus is None:
        print("SKIP: corpus not found at", CORPUS_TTL)
        return
    label_map, variables, indices, i_pos, expr_lists, var_exprs = corpus

    ok, failed = [], []
    for eid, toks in sorted(expr_lists.items(), key=lambda kv: int(kv[0][2:])):
        src = decode(toks, label_map, variables, i_pos, indices)
        lhs_iri = next(
            (v for v, e in var_exprs.items() if e == eid), None
        )
        lhs_net = variables[lhs_iri].network if lhs_iri else "root"
        ctx = DictContext(variables, indices, tree=CORPUS_TREE)
        space = CompileSpace(
            ctx.variables(), ctx.indices(),
            variable_definition_network=lhs_net,
            expression_definition_network=lhs_net,
            accessible_networks=ctx.accessible_networks(lhs_net),
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
