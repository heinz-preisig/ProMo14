"""Connect-time port satisfaction (§13/§14 — modeller-side check).

Advisory adjudication for the connect gesture: given the behaviour
assignments of two entity types and the tokens a candidate arc is
licensed to carry (``matched_tokens`` from resolve-connection), report
which of each side's BL port demands the arc would feed.

Semantics mirror ``builder.build_model`` port resolution, with the
topology abstracted away:

- **Demand** — each side's ``hasPortVariable`` marks with the
  variable's ``carriesToken``.
- **Supply** — the peer's exportable variables
  (:func:`builder.readable_vars`), minus the unflagged state (the
  accumulation stays internal); ``port_variable``-flagged candidates
  are preferred (§14 R3: flag = override, not gate).
- **Status** — ``satisfied`` (exactly one comparable candidate),
  ``ambiguous`` (several), ``unbound`` (none — includes the
  ``state_hidden`` hint when the peer's unflagged state was the only
  comparable), or ``unlicensed`` (no ``matched_tokens`` entry is
  comparable to the port's tokens — the arc's rule licenses the
  connection kind but not this exchange).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .builder import AssignmentInfo, EqInfo, VarInfo, _comparable, readable_vars


@dataclass
class PortDemand:
    """Adjudication of one BL port variable against a candidate arc."""

    var: str
    label: str = ""
    tokens: List[str] = field(default_factory=list)
    #: satisfied|ambiguous|unbound|unlicensed
    status: str = "unbound"
    #: comparable exportable candidates on the peer (variable IRIs)
    candidates: List[str] = field(default_factory=list)
    #: peer's unflagged state was comparable but hidden (§14 hint)
    state_hidden: bool = False


@dataclass
class SideReport:
    """One endpoint's port demands against the proposed connection."""

    entity_type: str
    has_assignment: bool = True
    ports: List[PortDemand] = field(default_factory=list)

    @property
    def unsatisfied(self) -> List[str]:
        return [p.var for p in self.ports if p.status != "satisfied"]


def _adjudicate(asg: AssignmentInfo, peer_asg: Optional[AssignmentInfo],
                variables: Dict[str, VarInfo],
                equations: Dict[str, EqInfo],
                token_parents: Dict[str, str],
                matched_tokens: Optional[Set[str]]) -> SideReport:
    """Judge one direction: ``asg``'s ports read from ``peer_asg``'s
    exportable variables through an arc carrying ``matched_tokens``
    (``None`` = licensing unknown, skip the license check)."""
    side = SideReport(entity_type=asg.entity_type)
    if peer_asg is None:
        side.has_assignment = False
    supply = readable_vars(peer_asg, equations) if peer_asg else set()
    peer_state = peer_asg.state_variable if peer_asg else None

    for v_iri in asg.ports:
        var = variables.get(v_iri)
        if var is None:
            continue
        demand = PortDemand(var=v_iri, label=var.label,
                            tokens=list(var.tokens))

        # License check: some arc-carried token must be comparable to
        # one of the port's tokens.  A port with no token can never be
        # licensed — carriesToken is definitional (§14).
        if matched_tokens is not None:
            licensed = any(
                _comparable(t, m, token_parents)
                for t in var.tokens for m in matched_tokens)
            if not licensed:
                demand.status = "unlicensed"
                side.ports.append(demand)
                continue

        raw: List[str] = []
        hidden = False
        for w_iri in sorted(supply):
            w = variables.get(w_iri)
            if w is None:
                continue
            # Identity is comparable (a boundary entity that
            # instantiates the same variable exports its value).
            if w_iri != v_iri and not any(
                    _comparable(t, wt, token_parents)
                    for t in var.tokens for wt in w.tokens):
                continue
            if w_iri == peer_state and not w.port_variable:
                hidden = True    # accumulation stays internal
                continue
            raw.append(w_iri)
        flagged = [c for c in raw if variables[c].port_variable]
        demand.candidates = flagged or raw
        demand.state_hidden = hidden
        if len(demand.candidates) == 1:
            demand.status = "satisfied"
        elif len(demand.candidates) > 1:
            demand.status = "ambiguous"
        else:
            demand.status = "unbound"
        side.ports.append(demand)
    return side


def port_satisfaction(
    source: str,
    target: str,
    assignments: Dict[str, AssignmentInfo],
    variables: Dict[str, VarInfo],
    equations: Dict[str, EqInfo],
    token_parents: Dict[str, str],
    matched_tokens: Optional[Set[str]] = None,
) -> Tuple[SideReport, SideReport]:
    """Adjudicate a proposed source↔target connection.  Both directions
    are judged — a physical arc is bidirectional, so each side's ports
    read from the other's exportable variables.  Entity types without
    an assignment report ``has_assignment=False`` and no demands."""
    src_asg = assignments.get(source)
    tgt_asg = assignments.get(target)
    source_side = (_adjudicate(src_asg, tgt_asg, variables, equations,
                               token_parents, matched_tokens)
                   if src_asg else SideReport(entity_type=source,
                                              has_assignment=False))
    target_side = (_adjudicate(tgt_asg, src_asg, variables, equations,
                               token_parents, matched_tokens)
                   if tgt_asg else SideReport(entity_type=target,
                                              has_assignment=False))
    return source_side, target_side
