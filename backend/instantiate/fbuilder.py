"""Signed node–arc incidence matrices ``F[N,A]`` (design doc §15).

Pure-Python, no rdflib/FastAPI deps — the service layer adapts store
graphs into resolver output, which this module consumes.

Sign convention: ``F[n,a] = +1`` when ``n`` is the arc's
``reference_to`` end (positive flow enters the node) and ``-1`` at
``reference_from``.  Node balances then read ``F·f`` = net inflow.
The reference direction is the *effective* one reported by the
resolver (stored §15 orientation, else draw order).

One matrix per declared arc sub-index (columns = member arcs) plus the
base matrix over all token-flow arcs.  Every matrix shares the same
row space — the full node list — so they can be summed and compared
directly.  Entries are sparse COO ``(row, col, sign)`` triples.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .resolver import ArcInfo, ArcMembership, NodeInfo, SubIndexInfo

# Carriers that participate in conservation incidence (mirrors the
# resolver's membership rule).
_TOKEN_FLOW = (None, "token-flow")


@dataclass
class Incidence:
    """``F[N,A]`` for one (sub-)index — sparse COO ±1 entries."""

    index: str                       # index IRI ("" if undetermined)
    short_name: str = ""             # "A", "A_diff", …
    nodes: List[str] = field(default_factory=list)   # row labels
    arcs: List[str] = field(default_factory=list)    # column labels
    entries: List[Tuple[int, int, int]] = field(default_factory=list)


@dataclass
class IncidenceReport:
    base: Incidence                            # all token-flow arcs
    sub_indices: List[Incidence] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)  # unplaceable arcs


def build(nodes: Dict[str, NodeInfo],
          arcs: Dict[str, ArcInfo],
          memberships: List[ArcMembership],
          sub_indices: Dict[str, SubIndexInfo],
          ) -> IncidenceReport:
    """Build the base F plus one F_k per declared arc sub-index."""
    node_list = sorted(nodes)
    row = {n: i for i, n in enumerate(node_list)}
    by_arc = {m.arc: m for m in memberships}

    skipped: List[str] = []

    def matrix(index_iri: str, short_name: str,
               arc_iris: List[str]) -> Incidence:
        cols = sorted(arc_iris)
        entries: List[Tuple[int, int, int]] = []
        for j, a in enumerate(cols):
            m = by_arc[a]
            rf, rt = m.reference_from, m.reference_to
            if rf is None or rt is None:
                skipped.append(a)
                continue
            if rf in row:
                entries.append((row[rf], j, -1))
            if rt in row:
                entries.append((row[rt], j, +1))
        return Incidence(index_iri, short_name, node_list, cols, entries)

    # Base matrix: every token-flow (or untyped) arc.
    base_arcs = [m.arc for m in memberships if m.carrier in _TOKEN_FLOW]
    bases = {si.sub_index_of for si in sub_indices.values()}
    base_iri = next(iter(bases)) if len(bases) == 1 else ""
    base = matrix(base_iri, "", base_arcs)

    subs = [
        matrix(si.iri, si.short_name,
               [m.arc for m in memberships if si.iri in m.sub_indices])
        for si in sorted(sub_indices.values(), key=lambda s: s.iri)
    ]
    return IncidenceReport(base=base, sub_indices=subs,
                           skipped=sorted(set(skipped)))
