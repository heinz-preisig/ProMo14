"""Arc sub-index membership resolution (design doc §16).

Pure-Python mechanics, no rdflib/FastAPI deps — the service layer
adapts store graphs into the plain structures this module consumes.

An arc belongs to a sub-index iff it is a token-flow arc that touches
a node whose entity type *is-a* the sub-index's ``selector`` (the
``promo:parent`` chain gives transitive subtype resolution, so an arc
touching a ``diffusion_transport`` node lands in ``A_diff``, ``A_mass``
and the base ``A``).

Membership is deliberately physics-free: the selector is any entity
type, the parent chain any taxonomy.  Only token-flow arcs participate
— reference arcs (signal/access/sensor/actuation) touch no conserved
token and are reported with empty membership for transparency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class NodeInfo:
    """The slice of a model node the resolver needs."""

    iri: str
    entity_type: Optional[str] = None


@dataclass
class ArcInfo:
    """The slice of a model arc the resolver needs."""

    iri: str
    source: Optional[str] = None        # ModelNode IRI (layout order)
    target: Optional[str] = None        # ModelNode IRI
    carrier: Optional[str] = None       # "token-flow" | "reference" | …


@dataclass
class SubIndexInfo:
    """An Index carrying §16 partitioning metadata."""

    iri: str
    sub_index_of: str                   # base index IRI
    selector: str                       # entity-type IRI defining membership
    short_name: str = ""


@dataclass
class ArcMembership:
    """Resolution result for one arc."""

    arc: str
    carrier: Optional[str]
    sub_indices: List[str] = field(default_factory=list)   # sub-index IRIs
    touches: List[str] = field(default_factory=list)       # entity types hit


def ancestors(entity_type: Optional[str],
              parents: Dict[str, str]) -> Set[str]:
    """The entity type plus its transitive ``promo:parent`` closure."""
    out: Set[str] = set()
    cur = entity_type
    while cur and cur not in out:
        out.add(cur)
        cur = parents.get(cur)
    return out


def arc_carrier(arc_type_iri: Optional[str]) -> Optional[str]:
    """Carrier category from an arc-type IRI (``promo:ArcType/<carrier>``).

    The modeller synthesises arc types from connection-rule carriers;
    the fragment after ``ArcType/`` is the carrier.  Anything else is
    returned as the raw fragment so unknown schemes stay visible.
    """
    if not arc_type_iri:
        return None
    if "ArcType/" in arc_type_iri:
        return arc_type_iri.rsplit("ArcType/", 1)[1]
    return arc_type_iri.split("#")[-1].split("/")[-1]


def resolve(nodes: Dict[str, NodeInfo],
            arcs: Dict[str, ArcInfo],
            sub_indices: Dict[str, SubIndexInfo],
            parents: Dict[str, str],
            ) -> List[ArcMembership]:
    """Resolve every arc's sub-index membership.

    ``parents`` maps entity-type IRI → parent entity-type IRI
    (``promo:parent``).  Only arcs with carrier ``token-flow`` (or no
    declared carrier — untyped arcs resolve permissively) take part in
    membership; reference arcs are reported with empty ``sub_indices``.
    """
    # Precompute each node's ancestor closure (entity type + parents).
    node_ancestors: Dict[str, Set[str]] = {
        iri: ancestors(n.entity_type, parents)
        for iri, n in nodes.items()
    }

    out: List[ArcMembership] = []
    for arc in arcs.values():
        carrier = arc.carrier
        touched: Set[str] = set()
        for end in (arc.source, arc.target):
            if end is not None:
                touched |= node_ancestors.get(end, set())
        member = [
            si.iri for si in sub_indices.values()
            if si.selector in touched
        ] if carrier in (None, "token-flow") else []
        out.append(ArcMembership(
            arc=arc.iri,
            carrier=carrier,
            sub_indices=sorted(member),
            touches=sorted(touched),
        ))
    return out


def by_sub_index(memberships: List[ArcMembership]) -> Dict[str, List[str]]:
    """Invert the per-arc view: sub-index IRI → member arc IRIs."""
    out: Dict[str, List[str]] = {}
    for m in memberships:
        for si in m.sub_indices:
            out.setdefault(si, []).append(m.arc)
    return out
