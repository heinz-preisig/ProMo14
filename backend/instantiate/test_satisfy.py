"""Tests for the §13/§14 connect-time port-satisfaction adjudicator.

Pure engine tests over plain dicts — the endpoint test lives in
``backend/modeller/test_service.py``.
"""

from backend.instantiate.builder import AssignmentInfo, EqInfo, VarInfo
from backend.instantiate.satisfy import port_satisfaction

MASS = "promo#tok_mass"
ENERGY = "promo#tok_energy"
SIGNAL = "promo#tok_signal"
MOMENTUM = "promo#tok_momentum"

# mass ⊃ component_mass, signal ⊃ observation|manipulation
TOKEN_PARENTS = {
    "promo#tok_component_mass": MASS,
    "promo#tok_observation": SIGNAL,
    "promo#tok_manipulation": SIGNAL,
}


def _v(iri, tokens=(), port_variable=False, effort=False):
    return VarInfo(iri=iri, label=iri.rsplit("/", 1)[-1],
                   tokens=list(tokens), port_variable=port_variable,
                   effort=effort)


def _eq(iri, lhs):
    return EqInfo(iri=iri, lhs=lhs)


def _asg(et, **kw):
    return AssignmentInfo(entity_type=et, **kw)


def _run(src_asg, tgt_asg, variables, equations=None,
         matched_tokens=None):
    assignments = {a.entity_type: a for a in (src_asg, tgt_asg) if a}
    src = src_asg.entity_type if src_asg else "src"
    tgt = tgt_asg.entity_type if tgt_asg else "tgt"
    return port_satisfaction(
        src, tgt, assignments, variables, equations or {},
        TOKEN_PARENTS, matched_tokens=matched_tokens)


def test_satisfied_single_comparable_candidate():
    """A mass port reads the peer's defined mass variable."""
    variables = {
        "v_p": _v("v_p", [MASS]),
        "v_rho": _v("v_rho", [MASS]),
    }
    src = _asg("et_a", ports=["v_p"])
    tgt = _asg("et_b", sequence=["e1"])
    src_side, tgt_side = _run(
        src, tgt, variables, {"e1": _eq("e1", "v_rho")},
        matched_tokens={MASS})
    assert src_side.ports[0].status == "satisfied"
    assert src_side.ports[0].candidates == ["v_rho"]
    assert tgt_side.ports == []


def test_unbound_when_peer_defines_nothing_comparable():
    variables = {
        "v_p": _v("v_p", [MASS]),
        "v_T": _v("v_T", [ENERGY]),
    }
    src = _asg("et_a", ports=["v_p"])
    tgt = _asg("et_b", sequence=["e1"])
    src_side, _ = _run(
        src, tgt, variables, {"e1": _eq("e1", "v_T")},
        matched_tokens={MASS, ENERGY})
    p = src_side.ports[0]
    assert p.status == "unbound" and p.candidates == []


def test_unflagged_state_is_hidden_with_hint():
    """Comparable but unflagged state is not a candidate — the
    state_hidden hint tells the user to set port_variable."""
    variables = {
        "v_p": _v("v_p", [MASS]),
        "v_n": _v("v_n", [MASS]),          # peer state, unflagged
    }
    src = _asg("et_a", ports=["v_p"])
    tgt = _asg("et_b", state_variable="v_n")
    src_side, _ = _run(src, tgt, variables, matched_tokens={MASS})
    p = src_side.ports[0]
    assert p.status == "unbound" and p.state_hidden


def test_flagged_state_exports_and_preferred():
    """port_variable state exports; flagged candidates win over raw."""
    variables = {
        "v_p": _v("v_p", [MASS]),
        "v_n": _v("v_n", [MASS], port_variable=True),
        "v_m": _v("v_m", [MASS]),
    }
    src = _asg("et_a", ports=["v_p"])
    tgt = _asg("et_b", state_variable="v_n", sequence=["e1"])
    src_side, _ = _run(
        src, tgt, variables, {"e1": _eq("e1", "v_m")},
        matched_tokens={MASS})
    p = src_side.ports[0]
    # flagged (v_n) preferred over unflagged defined (v_m)
    assert p.status == "satisfied" and p.candidates == ["v_n"]


def test_ambiguous_multiple_candidates():
    variables = {
        "v_p": _v("v_p", [MASS]),
        "v_rho": _v("v_rho", [MASS]),
        "v_m": _v("v_m", [MASS]),
    }
    src = _asg("et_a", ports=["v_p"])
    tgt = _asg("et_b", sequence=["e1", "e2"])
    src_side, _ = _run(
        src, tgt, variables,
        {"e1": _eq("e1", "v_rho"), "e2": _eq("e2", "v_m")},
        matched_tokens={MASS})
    p = src_side.ports[0]
    assert p.status == "ambiguous"
    assert set(p.candidates) == {"v_rho", "v_m"}


def test_unlicensed_when_arc_carries_no_comparable_token():
    """A signal arc cannot feed a mass port."""
    variables = {
        "v_p": _v("v_p", [MASS]),
        "v_rho": _v("v_rho", [MASS]),
    }
    src = _asg("et_a", ports=["v_p"])
    tgt = _asg("et_b", sequence=["e1"])
    src_side, _ = _run(
        src, tgt, variables, {"e1": _eq("e1", "v_rho")},
        matched_tokens={SIGNAL})
    assert src_side.ports[0].status == "unlicensed"


def test_subtoken_comparability_both_directions():
    """component_mass demand matches a mass-carrying arc and a mass
    supply (ancestor either way, §14)."""
    variables = {
        "v_c": _v("v_c", ["promo#tok_component_mass"]),
        "v_m": _v("v_m", [MASS]),
    }
    src = _asg("et_a", ports=["v_c"])
    tgt = _asg("et_b", sequence=["e1"])
    src_side, _ = _run(
        src, tgt, variables, {"e1": _eq("e1", "v_m")},
        matched_tokens={MASS})
    assert src_side.ports[0].status == "satisfied"


def test_instantiated_peer_exports_value():
    """A boundary entity's instantiated variable is a valid supply."""
    variables = {
        "v_p": _v("v_p", [MASS]),
        "v_p_env": _v("v_p_env", [MASS]),
    }
    src = _asg("et_a", ports=["v_p"])
    tgt = _asg("et_b", instantiated=["v_p_env"])
    src_side, _ = _run(src, tgt, variables, matched_tokens={MASS})
    p = src_side.ports[0]
    assert p.status == "satisfied" and p.candidates == ["v_p_env"]


def test_identity_candidate():
    """The same variable instantiated on the peer counts (boundary
    entity re-exposes the port variable itself)."""
    variables = {"v_p": _v("v_p", [MASS], port_variable=True)}
    src = _asg("et_a", ports=["v_p"])
    tgt = _asg("et_b", instantiated=["v_p"])
    src_side, _ = _run(src, tgt, variables, matched_tokens={MASS})
    assert src_side.ports[0].status == "satisfied"


def test_missing_assignment_reports_flag():
    variables = {"v_p": _v("v_p", [MASS])}
    src = _asg("et_a", ports=["v_p"])
    assignments = {src.entity_type: src}
    src_side, tgt_side = port_satisfaction(
        "et_a", "et_missing", assignments, variables, {},
        TOKEN_PARENTS, matched_tokens={MASS})
    assert not tgt_side.has_assignment
    assert src_side.ports[0].status == "unbound"


def test_no_license_check_without_matched_tokens():
    """matched_tokens=None → licensing unknown, judged on supply only."""
    variables = {
        "v_p": _v("v_p", [MASS]),
        "v_rho": _v("v_rho", [MASS]),
    }
    src = _asg("et_a", ports=["v_p"])
    tgt = _asg("et_b", sequence=["e1"])
    src_side, _ = _run(
        src, tgt, variables, {"e1": _eq("e1", "v_rho")},
        matched_tokens=None)
    assert src_side.ports[0].status == "satisfied"


def test_bidirectional_both_sides_judged():
    """Physical arcs feed ports both ways."""
    variables = {
        "v_p": _v("v_p", [MASS]),
        "v_T": _v("v_T", [ENERGY]),
        "v_rho": _v("v_rho", [MASS]),
        "v_U": _v("v_U", [ENERGY]),
    }
    src = _asg("et_a", ports=["v_p"], sequence=["eU"])
    tgt = _asg("et_b", ports=["v_T"], sequence=["eRho"])
    src_side, tgt_side = _run(
        src, tgt, variables,
        {"eU": _eq("eU", "v_U"), "eRho": _eq("eRho", "v_rho")},
        matched_tokens={MASS, ENERGY})
    assert src_side.ports[0].status == "satisfied"
    assert tgt_side.ports[0].status == "satisfied"


def test_unsatisfied_list_excludes_satisfied():
    variables = {
        "v_p": _v("v_p", [MASS]),
        "v_T": _v("v_T", [ENERGY]),
        "v_rho": _v("v_rho", [MASS]),
    }
    src = _asg("et_a", ports=["v_p", "v_T"])
    tgt = _asg("et_b", sequence=["e1"])
    src_side, _ = _run(
        src, tgt, variables, {"e1": _eq("e1", "v_rho")},
        matched_tokens={MASS, ENERGY})
    assert src_side.unsatisfied == ["v_T"]


def test_unidirectional_source_ports_unreachable():
    """§14: on a unidirectional (signal/reference) arc the source's own
    port demands can never be fed — the flow runs source→target."""
    variables = {
        "v_obs": _v("v_obs", ["promo#tok_observation"]),
        "v_sig": _v("v_sig", [SIGNAL]),
    }
    src = _asg("et_sensor", ports=["v_obs"], instantiated=["v_obs"])
    tgt = _asg("et_plant", sequence=["e1"], ports=["v_sig"])
    src_side, tgt_side = port_satisfaction(
        "et_sensor", "et_plant",
        {"et_sensor": src, "et_plant": tgt},
        variables, {"e1": _eq("e1", "v_sig")},
        TOKEN_PARENTS, matched_tokens={"promo#tok_observation"},
        unidirectional=True)
    assert src_side.ports[0].status == "unreachable"
    assert src_side.ports[0].var == "v_obs"
    assert tgt_side.ports[0].status == "satisfied"
    assert tgt_side.ports[0].candidates == ["v_obs"]
    assert src_side.ports[0].candidates == []
    assert src_side.unsatisfied == ["v_obs"]
    assert tgt_side.unsatisfied == []


def test_unidirectional_missing_assignment_flagged():
    """Source without an assignment reports has_assignment=False, no ports."""
    variables = {"v": _v("v", [SIGNAL])}
    tgt = _asg("et_plant", ports=["v"])
    src_side, tgt_side = port_satisfaction(
        "et_sensor", "et_plant", {"et_plant": tgt},
        variables, {}, TOKEN_PARENTS, unidirectional=True)
    assert src_side.has_assignment is False
    assert src_side.ports == []


def test_bidirectional_default_keeps_both_sides():
    """Default (physical) arcs still judge both directions."""
    variables = {
        "v_a": _v("v_a", [MASS]),
        "v_b": _v("v_b", [MASS]),
    }
    src = _asg("et_a", ports=["v_a"], sequence=["e1"])
    tgt = _asg("et_b", ports=["v_b"], sequence=["e2"])
    src_side, tgt_side = port_satisfaction(
        "et_a", "et_b", {"et_a": src, "et_b": tgt},
        variables, {"e1": _eq("e1", "v_a"), "e2": _eq("e2", "v_b")},
        TOKEN_PARENTS, matched_tokens={MASS})
    assert src_side.ports[0].status == "satisfied"
    assert tgt_side.ports[0].status == "satisfied"


def test_unidirectional_source_unlicensed_token():
    variables = {"v_mass": _v("v_mass", [MASS])}
    src = _asg("et_source", ports=["v_mass"])
    src_side, _ = port_satisfaction(
        "et_source", "et_target", {"et_source": src},
        variables, {}, TOKEN_PARENTS,
        matched_tokens={SIGNAL}, unidirectional=True)
    assert src_side.ports[0].status == "unlicensed"
    assert src_side.ports[0].candidates == []
    assert src_side.unsatisfied == ["v_mass"]


# -- §38 effort coupling --------------------------------------------------


def test_effort_port_binds_effort_peer_carrying_drive_token():
    """Convection (drives momentum) reads the peer's effort var —
    pressure — which is function:effort and carries the drive token."""
    variables = {
        "v_p": _v("v_p", [MOMENTUM], effort=True),
        "v_e": _v("v_e", [MOMENTUM], effort=True),
    }
    src = _asg("et_conv", ports=["v_p"])
    tgt = _asg("et_cap", sequence=["e1"])
    src_side, _ = port_satisfaction(
        "et_conv", "et_cap", {"et_conv": src, "et_cap": tgt},
        variables, {"e1": _eq("e1", "v_e")}, TOKEN_PARENTS,
        matched_tokens={MOMENTUM},
        drives={"et_conv": {MOMENTUM}})
    assert src_side.ports[0].status == "satisfied"
    assert src_side.ports[0].candidates == ["v_e"]


def test_effort_port_rejects_non_effort_peer():
    """A momentum-carrying peer var is NOT the effort unless it is
    function:effort-classified — token comparability alone is not the
    conjugate pairing."""
    variables = {
        "v_p": _v("v_p", [MOMENTUM], effort=True),
        "v_flux": _v("v_flux", [MOMENTUM]),
    }
    src = _asg("et_conv", ports=["v_p"])
    tgt = _asg("et_cap", sequence=["e1"])
    src_side, _ = port_satisfaction(
        "et_conv", "et_cap", {"et_conv": src, "et_cap": tgt},
        variables, {"e1": _eq("e1", "v_flux")}, TOKEN_PARENTS,
        matched_tokens={MOMENTUM},
        drives={"et_conv": {MOMENTUM}})
    assert src_side.ports[0].status == "effort-unavailable"
    assert src_side.ports[0].candidates == []


def test_effort_port_rejects_effort_peer_wrong_drive():
    """An effort var carrying energy cannot drive a momentum-driven
    mechanism — the drive token must be comparable."""
    variables = {
        "v_p": _v("v_p", [MOMENTUM], effort=True),
        "v_T": _v("v_T", [ENERGY], effort=True),
    }
    src = _asg("et_conv", ports=["v_p"])
    tgt = _asg("et_cap", sequence=["e1"])
    src_side, _ = port_satisfaction(
        "et_conv", "et_cap", {"et_conv": src, "et_cap": tgt},
        variables, {"e1": _eq("e1", "v_T")}, TOKEN_PARENTS,
        matched_tokens={MOMENTUM},
        drives={"et_conv": {MOMENTUM}})
    assert src_side.ports[0].status == "effort-unavailable"


def test_effort_port_no_drives_falls_back_to_role():
    """Mechanism with no promo:drives declared: the effort-role match
    still applies (peer must be function:effort), the drive-token
    check is skipped."""
    variables = {
        "v_p": _v("v_p", [MOMENTUM], effort=True),
        "v_e": _v("v_e", [MOMENTUM], effort=True),
        "v_x": _v("v_x", [MOMENTUM]),
    }
    src = _asg("et_mech", ports=["v_p"])
    tgt = _asg("et_cap", sequence=["e1", "e2"])
    src_side, _ = port_satisfaction(
        "et_mech", "et_cap", {"et_mech": src, "et_cap": tgt},
        variables, {"e1": _eq("e1", "v_e"), "e2": _eq("e2", "v_x")},
        TOKEN_PARENTS, matched_tokens={MOMENTUM})
    assert src_side.ports[0].status == "satisfied"
    assert src_side.ports[0].candidates == ["v_e"]


def test_non_effort_port_ignores_drives():
    """Flow/other ports bind by plain comparability even when the
    demand side's mechanism declares drives."""
    variables = {
        "v_f": _v("v_f", [MASS]),
        "v_w": _v("v_w", [MASS]),
    }
    src = _asg("et_conv", ports=["v_f"])
    tgt = _asg("et_cap", sequence=["e1"])
    src_side, _ = port_satisfaction(
        "et_conv", "et_cap", {"et_conv": src, "et_cap": tgt},
        variables, {"e1": _eq("e1", "v_w")}, TOKEN_PARENTS,
        matched_tokens={MASS},
        drives={"et_conv": {MOMENTUM}})
    assert src_side.ports[0].status == "satisfied"
    assert src_side.ports[0].candidates == ["v_w"]
