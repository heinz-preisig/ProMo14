"""Species distribution (§20) — which species occupy each node and
arc.

Species presence is a *computed* property, not a topological one: a
reservoir (constant environment system) injects an allocated set,
transport arcs pass a permeable subset, and reactions produce species
where their reactants are present.  The result is the element set for
the species index ``S`` on every node and arc — the input the §19
builder needs to bind ``S`` — plus the element set for the reaction
index ``Q``: the hosted reactions whose reactants are present (the
ones that fired) on each node.

The engine is a pure function over a minimal input contract so it can
be shared by the modeller (live "species present" feedback) and the
instantiation builder (binding) — and tested without the artefact
machinery.  The species artefact schema is still open (§20); these
dataclasses are the slice the algorithm consumes.

Propagation is **bidirectional** across a permeable arc: for sizing we
over-approximate — a species that *could* be present is counted as
present.  A connected permeable region therefore shares one species
pool.  Directional (downstream-only) spread is a possible refinement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass
class SpeciesNode:
    """The slice of a model node the distribution needs."""

    iri: str
    allocation: Optional[str] = None      # reservoir → allocation name
    reactions: List[str] = field(default_factory=list)  # hosted rxn ids


@dataclass
class SpeciesArc:
    """The slice of a model arc the distribution needs."""

    iri: str
    source: Optional[str] = None          # node IRI
    target: Optional[str] = None          # node IRI
    carries_species: bool = True          # mass/species transport only
    permeable: Optional[Set[str]] = None  # None = passes all species


@dataclass
class Reaction:
    """A stoichiometric rule: reactants present → products appear."""

    iri: str
    reactants: Set[str] = field(default_factory=set)
    products: Set[str] = field(default_factory=set)


@dataclass
class SpeciesArtefact:
    """The slice of the species artefact the distribution needs."""

    species: List[str] = field(default_factory=list)        # global S
    allocations: Dict[str, List[str]] = field(default_factory=dict)
    reactions: Dict[str, Reaction] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


@dataclass
class SpeciesDistribution:
    """The computed species set per node and per arc, and the active
    reaction set per node (the ``Q`` index's element set — only nodes
    hosting at least one reaction appear)."""

    nodes: Dict[str, Set[str]] = field(default_factory=dict)
    arcs: Dict[str, Set[str]] = field(default_factory=dict)
    reactions: Dict[str, Set[str]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def distribute(nodes: List[SpeciesNode],
               arcs: List[SpeciesArc],
               artefact: SpeciesArtefact) -> SpeciesDistribution:
    """Propagate species to a fixpoint.

    ``species(n) = injected(n) ∪ transported_in(n) ∪ produced(n)`` and
    ``species(a) = (species(source) ∪ species(target)) ∩ permeable(a)``.
    Species only accumulate, so the iteration terminates.
    """
    all_species = set(artefact.species)
    node_sp: Dict[str, Set[str]] = {n.iri: set() for n in nodes}
    arc_sp: Dict[str, Set[str]] = {a.iri: set() for a in arcs}
    node_rxns = {n.iri: n.reactions for n in nodes}

    # Seed the reservoirs.
    for n in nodes:
        if n.allocation is not None:
            node_sp[n.iri] |= set(artefact.allocations.get(n.allocation,
                                                         []))

    changed = True
    while changed:
        changed = False

        # Transport: species cross a permeable arc both ways.
        for a in arcs:
            if not a.carries_species or a.source is None \
                    or a.target is None:
                continue
            pool = node_sp[a.source] | node_sp[a.target]
            crossing = pool if a.permeable is None \
                else pool & (a.permeable & all_species)
            if crossing != arc_sp[a.iri]:
                arc_sp[a.iri] = set(crossing)
            for n in (a.source, a.target):
                if not crossing <= node_sp[n]:
                    node_sp[n] |= crossing
                    changed = True

        # Reactions: reactants present → products appear.
        for n_iri, rxn_ids in node_rxns.items():
            for r_id in rxn_ids:
                r = artefact.reactions.get(r_id)
                if r is None or not r.reactants <= node_sp[n_iri]:
                    continue
                if not r.products <= node_sp[n_iri]:
                    node_sp[n_iri] |= r.products
                    changed = True

    # Q: a hosted reaction is active iff its reactants are present at
    # the fixpoint — exactly the ones that fired above (species only
    # accumulate, so firing is monotone).
    node_rxn_active: Dict[str, Set[str]] = {}
    for n in nodes:
        if not n.reactions:
            continue
        node_rxn_active[n.iri] = {
            r_id for r_id in n.reactions
            if (r := artefact.reactions.get(r_id)) is not None
            and r.reactants <= node_sp[n.iri]}

    return SpeciesDistribution(nodes=node_sp, arcs=arc_sp,
                               reactions=node_rxn_active)
