#!/usr/bin/env python3
"""Extend the seed ontology with what the HAP example needs.

Adds (idempotent — safe to re-run):

- domains: ``macroscopic`` and ``reactions`` under ``physical``;
  ``control`` under ``information``.  Tokens are inherited additively
  from the parent, so no explicit token bindings are needed.
- role terms on the physical role axis: ``property``, ``conversion``,
  ``observation``, ``network-structure`` (top level);
  ``secondary-state`` and ``differential-state`` as children of
  ``state``.
- index ``q``: reaction index with ``conversion`` source kind,
  belonging to the ``reactions`` domain.

Saves the ontology graph to ``PROMO_DATA_DIR/ontology.trig`` (or
``./data``).  Restart the backend afterwards so the running store picks
up the file.

Usage::

    uv run python scripts/extend_ontology_hap.py
    uv run python scripts/extend_ontology_hap.py --data-dir /path/to/data
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.graph_store import PROMO, RdfStore  # noqa: E402
from rdflib import Literal, URIRef  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=None,
        help="ProMo data directory (default: PROMO_DATA_DIR or ./data)",
    )
    args = parser.parse_args()

    store = RdfStore(args.data_dir)
    store.load()
    g = store.ontology_graph
    base = str(PROMO).rstrip("#")

    phys = URIRef(f"{base}#domain_physical")
    info = URIRef(f"{base}#domain_information")
    role_phys = URIRef(f"{base}#axis_role_physical")
    state_term = URIRef(f"{base}#term_role_state")

    # --- Domains -------------------------------------------------------
    # physical: macroscopic (capacity), transport (transport nodes),
    #           reactions / properties / geometry (service domains)
    # information: control (pControl)
    for name, parent, branch in [
        ("macroscopic", phys, "physical"),
        ("transport", phys, "physical"),
        ("reactions", phys, "physical"),
        ("properties", phys, "physical"),
        ("geometry", phys, "physical"),
        ("control", info, "information"),
    ]:
        iri = store.mint_iri(base, f"domain_{name}")
        store.add_domain(g, name, iri=iri, parent=parent, branch=branch)
        print(f"domain  {name:<12} parent={parent.split('#')[-1]}")

    # --- Role terms (physical axis) ------------------------------------
    for frag, label, parent in [
        ("property", "property", None),
        ("conversion", "conversion", None),
        ("observation", "observation", None),
        ("network_structure", "network-structure", None),
        ("secondary_state", "secondary-state", state_term),
        ("differential_state", "differential-state", state_term),
    ]:
        iri = store.mint_iri(base, f"term_role_{frag}")
        store.add_axis_term(g, iri, role_phys, label, parent=parent)
        p = f" < {parent.split('#')[-1]}" if parent else ""
        print(f"term    {label:<20}{p}")

    # --- Token hierarchy: component_mass < mass ------------------------
    g.set((URIRef(f"{base}#token_component_mass"), PROMO["parent"],
           URIRef(f"{base}#token_mass")))
    print("token   component_mass       < token_mass")

    # --- Connection-rule attributes (carrier / scope) ------------------
    # Arc semantics live in rule attributes, not in the type name.
    # Patch the seeded rules in existing data files (new seeds already
    # carry these values).
    for frag, carrier, scope in [
        ("rule_physical-same", "token-flow", "same"),
        ("rule_signal", "reference", "same"),
    ]:
        rule_iri = URIRef(f"{base}#{frag}")
        g.set((rule_iri, PROMO["carrier"], Literal(carrier)))
        g.set((rule_iri, PROMO["scope"], Literal(scope)))
        print(f"rule    {frag:<20} carrier={carrier} scope={scope}")

    # physical-cross retired (2026-09-15): a token-flow arc with
    # scope=cross can never apply — cross-branch pairs share no tokens.
    # physical-same covers all intra-physical continuity (incl. the
    # liquid-gas interface case it was named for).  Remove it from
    # existing data files.
    retired = URIRef(f"{base}#rule_physical-cross")
    if (retired, None, None) in g:
        g.remove((retired, None, None))
        print("rule    rule_physical-cross  (retired, removed)")

    # access: physical→physical reference arcs (service couplings).
    # Domain-constrained so the resolver prefers it over signal.
    # scope must be "same": two physical domains always share the
    # physical ancestor, so scope=cross can never fire.
    access_iri = URIRef(f"{base}#rule_access")
    if (access_iri, None, None) in g:
        g.set((access_iri, PROMO["scope"], Literal("same")))
        print("rule    rule_access          scope=same (corrected)")
    else:
        store.add_connection_rule(
            g, access_iri, "access",
            direction="unidirectional", carrier="reference", scope="same",
            source_domain=phys, target_domain=phys,
            description="Physical→physical accessibility arc (service coupling)")
        print("rule    rule_access          carrier=reference scope=same physical→physical")

    # signal is information-internal; sensor/actuation close the loop
    # across the branch boundary.  Existing user-defined rules are kept
    # (e.g. an actuation rule constrained to the transport domain).
    signal_rule = URIRef(f"{base}#rule_signal")
    g.set((signal_rule, PROMO["sourceDomain"], info))
    g.set((signal_rule, PROMO["targetDomain"], info))
    print("rule    rule_signal          constrained information→information")
    for name, src, tgt, desc in [
        ("sensor", phys, info,
         "Physical→information accessibility arc (measurement)"),
        ("actuation", info, phys,
         "Information→physical accessibility arc (control loop closure)"),
    ]:
        rule_iri = URIRef(f"{base}#rule_{name}")
        if (rule_iri, None, None) in g:
            print(f"rule    rule_{name:<15} (already present, skipped)")
        else:
            store.add_connection_rule(
                g, rule_iri, name, direction="unidirectional",
                carrier="reference", scope="cross",
                source_domain=src, target_domain=tgt, description=desc)
            print(f"rule    rule_{name:<15} carrier=reference scope=cross")

    # Shared tokens: physical arcs share the physical token set;
    # reference (accessibility) arcs share the signal token.
    signal_tok = URIRef(f"{base}#token_signal")
    physical_token_iris = [
        URIRef(f"{base}#token_{t}") for t in (
            "energy", "mass", "momentum", "charge", "entropy",
            "component_mass")
    ]
    for frag, tokens in [
        ("rule_physical-same", physical_token_iris),
        ("rule_access", [signal_tok]),
        ("rule_sensor", [signal_tok]),
        ("rule_actuation", [signal_tok]),
        ("rule_signal", [signal_tok]),
    ]:
        rule_iri = URIRef(f"{base}#{frag}")
        g.remove((rule_iri, PROMO["sharedTokens"], None))
        for tok in tokens:
            g.add((rule_iri, PROMO["sharedTokens"], tok))
    print("rule    *                    sharedTokens normalised")

    # The signal token is information-internal plus transport: the
    # transport system is the physical node that is measured/actuated.
    # Remove the old branch-wide binding on domain_physical.
    transport = URIRef(f"{base}#domain_transport")
    g.remove((phys, PROMO["hasToken"], signal_tok))
    g.add((transport, PROMO["hasToken"], signal_tok))
    print("token   signal               domain_physical → domain_transport")

    # --- Extensity axis (physical) -------------------------------------
    ext_axis = URIRef(f"{base}#axis_extensity")
    if (ext_axis, None, None) not in g:
        store.add_classification_axis(g, ext_axis, phys, "Extensity")
        for frag in ("extensive", "intensive"):
            store.add_axis_term(
                g, URIRef(f"{base}#term_extensity_{frag}"), ext_axis, frag)
        print("axis    Extensity          + extensive/intensive")

    # --- Index q (reaction index, conversion source) -------------------
    q_iri = store.mint_iri(base, "idx_reaction_q")
    if (q_iri, None, None) in g:
        print("index   q                    (already present, skipped)")
    else:
        internal_id = store.next_internal_id("I")
        store.add_index_dict(g, {
            "iri": str(q_iri),
            "label": "reaction",
            "short_name": "q",
            "network": "reactions",
            "index_class": "conversion",
            "internal_id": internal_id,
            "aliases": {"global_ID": internal_id, "internal_code": "q"},
            "doc": "Reaction index (conversion source), reactions domain",
        })
        print(f"index   q                    {internal_id}")

    out = store.save()
    print(f"\nSaved {len(g)} triples to {out}")
    print("Restart the backend (./dev.sh restart) to pick up the file.")


if __name__ == "__main__":
    main()
