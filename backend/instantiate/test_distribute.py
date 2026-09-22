"""Tests for the species-distribution engine (§20)."""

from backend.instantiate.distribute import (
    Reaction,
    SpeciesArc,
    SpeciesArtefact,
    SpeciesNode,
    distribute,
)


def _artefact(**kw) -> SpeciesArtefact:
    base = dict(species=["A", "B", "C", "D"],
                allocations={}, reactions={})
    base.update(kw)
    return SpeciesArtefact(**base)


def test_reservoir_injects_allocation():
    """A reservoir seeds its allocated species; an isolated node gets
    nothing."""
    nodes = [SpeciesNode("res", allocation="feed"),
             SpeciesNode("reactor")]
    art = _artefact(allocations={"feed": ["A", "B"]})
    out = distribute(nodes, [], art)
    assert out.nodes["res"] == {"A", "B"}
    assert out.nodes["reactor"] == set()


def test_species_propagate_across_permeable_arc():
    """Species cross a fully-permeable arc to the connected node."""
    nodes = [SpeciesNode("res", allocation="feed"),
             SpeciesNode("reactor")]
    arcs = [SpeciesArc("a1", source="res", target="reactor")]
    art = _artefact(allocations={"feed": ["A", "B"]})
    out = distribute(nodes, [], art)  # no arcs → no spread
    assert out.nodes["reactor"] == set()
    out = distribute(nodes, arcs, art)
    assert out.nodes["reactor"] == {"A", "B"}
    assert out.arcs["a1"] == {"A", "B"}


def test_semipermeable_wall_blocks_species():
    """A transport passing only {A} blocks B from crossing."""
    nodes = [SpeciesNode("res", allocation="feed"),
             SpeciesNode("cell")]
    arcs = [SpeciesArc("mem", source="res", target="cell",
                       permeable={"A"})]
    art = _artefact(allocations={"feed": ["A", "B"]})
    out = distribute(nodes, arcs, art)
    assert out.nodes["cell"] == {"A"}        # B blocked
    assert out.arcs["mem"] == {"A"}


def test_non_species_arc_carries_nothing():
    """An energy/signal arc (carries_species=False) transports no
    species."""
    nodes = [SpeciesNode("res", allocation="feed"),
             SpeciesNode("heater")]
    arcs = [SpeciesArc("heat", source="res", target="heater",
                       carries_species=False)]
    art = _artefact(allocations={"feed": ["A", "B"]})
    out = distribute(nodes, arcs, art)
    assert out.nodes["heater"] == set()
    assert out.arcs["heat"] == set()


def test_reaction_fires_when_reactants_present():
    """reactants ⊆ present → products appear at the node."""
    nodes = [SpeciesNode("res", allocation="feed"),
             SpeciesNode("reactor", reactions=["r1"])]
    arcs = [SpeciesArc("a1", source="res", target="reactor")]
    art = _artefact(
        allocations={"feed": ["A", "B"]},
        reactions={"r1": Reaction("r1", {"A", "B"}, {"C"})})
    out = distribute(nodes, arcs, art)
    assert out.nodes["reactor"] == {"A", "B", "C"}


def test_reaction_blocked_without_reactants():
    """A reaction whose reactants never arrive produces nothing."""
    nodes = [SpeciesNode("res", allocation="feed"),
             SpeciesNode("reactor", reactions=["r1"])]
    arcs = [SpeciesArc("mem", source="res", target="reactor",
                       permeable={"A"})]      # B blocked
    art = _artefact(
        allocations={"feed": ["A", "B"]},
        reactions={"r1": Reaction("r1", {"A", "B"}, {"C"})})
    out = distribute(nodes, arcs, art)
    assert out.nodes["reactor"] == {"A"}     # no B → no C


def test_reaction_cascade_propagates_product():
    """A product made in one node crosses an arc and fires a second
    reaction downstream — the fixpoint cascades."""
    nodes = [SpeciesNode("res", allocation="feed"),
             SpeciesNode("r1", reactions=["make_c"]),
             SpeciesNode("r2", reactions=["make_d"])]
    arcs = [SpeciesArc("a1", source="res", target="r1"),
            SpeciesArc("a2", source="r1", target="r2")]
    art = _artefact(
        allocations={"feed": ["A"]},
        reactions={
            "make_c": Reaction("make_c", {"A"}, {"C"}),
            "make_d": Reaction("make_d", {"A", "C"}, {"D"}),
        })
    out = distribute(nodes, arcs, art)
    # A reaches r1 → C made → A,C cross to r2 → D made.  Bidirectional
    # spread then carries D back, so the whole permeable region
    # converges to one pool {A,C,D}.
    assert out.nodes["res"] == {"A", "C", "D"}
    assert out.nodes["r1"] == {"A", "C", "D"}
    assert out.nodes["r2"] == {"A", "C", "D"}


def test_bidirectional_spread():
    """Species cross a permeable arc both ways — a species at the
    target reaches the source."""
    nodes = [SpeciesNode("res", allocation="feed"),
             SpeciesNode("other", allocation="makeup")]
    arcs = [SpeciesArc("a1", source="res", target="other")]
    art = _artefact(allocations={"feed": ["A"], "makeup": ["B"]})
    out = distribute(nodes, arcs, art)
    assert out.nodes["res"] == {"A", "B"}    # B spread back
    assert out.nodes["other"] == {"A", "B"}
