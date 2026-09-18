#!/usr/bin/env python3
"""Extend the seed ontology with what the HAP example needs.

Adds (idempotent — safe to re-run):

- root domain ``domain_root`` above both branches — the global scope
  for tokens and scale dimensions (``time`` rebinds to it, ``signal``
  moves to it); ``physical`` / ``information`` are reparented under it.
- domains: ``macroscopic`` and ``reactions`` under ``physical``;
  ``control`` under ``information``.  Tokens are inherited additively
  from the parent, so no explicit token bindings are needed.
- role terms on the physical role axis: graph positions only
  (``derived``, ``port``, ``flow``, ``secondary-state`` under
  ``derived``, ``differential-state`` under ``state``).  Removes the
  old domain-echo terms (``property``, ``conversion``, ``observation``,
  ``network-structure``, ``transport``) — see
  docs/ontology-design-discussion-2026-09-16.md.
- token kinds (``conserved`` | ``reference``) and signal subtokens
  ``observation`` / ``manipulation``.
- dimension kinds (``structural`` | ``content``) and the ``phase``
  content dimension (``solid``, ``fluid{liquid, gas}``, ``pseudo``).
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
from rdflib.namespace import RDF, RDFS  # noqa: E402


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
    # Namespace discipline (contract D1): promo# is vocabulary only;
    # instances mint under the owning graph's namespace.
    base = str(store.ONTOLOGY_GRAPH_IRI)

    # --- Instance IRI migration: promo# -> promo/ontology# -------------
    # Vocabulary = predicates and rdf:type objects; every other promo#
    # IRI is an instance and is rehomed, references included.  Runs
    # first so all patches below see the new IRIs, and covers every
    # named graph (var/expr graphs may reference ontology instances).
    # Idempotent: after one run no promo# instance IRIs remain.
    # NB: Dataset.predicates()/objects() only see the (empty) default
    # graph — iterate the named graphs explicitly.
    vocab = set()
    for gr in store.dataset.graphs():
        vocab |= {p for p in gr.predicates()
                  if str(p).startswith(str(PROMO))}
        vocab |= {o for o in gr.objects(None, RDF.type)
                  if isinstance(o, URIRef) and str(o).startswith(str(PROMO))}

    def _migrated(node):
        if (isinstance(node, URIRef)
                and str(node).startswith(str(PROMO))
                and node not in vocab):
            return URIRef(f"{base}#{str(node).split('#')[-1]}")
        return node

    total = 0
    for gr in store.dataset.graphs():
        moved = [(s, p, o) for s, p, o in gr
                 if _migrated(s) is not s or _migrated(o) is not o]
        for s, p, o in moved:
            gr.remove((s, p, o))
            gr.add((_migrated(s), p, _migrated(o)))
        total += len(moved)
    if total:
        print(f"iri     {total} triples rehomed promo# -> ontology#")

    # --- Legacy graph removal ------------------------------------------
    # Pre-namespace-migration snapshot(s) under example.org — fully
    # superseded by the promo/ontology graph; keeping them only adds a
    # stray untyped line to the catalogue.
    for gr in list(store.dataset.graphs()):
        if str(gr.identifier).startswith("http://example.org"):
            store.dataset.remove_context(gr)
            print(f"graph   {gr.identifier} removed (legacy snapshot)")

    # --- Label-predicate consolidation ---------------------------------
    # Canonical: rdfs:label = display label, promo:name = key-ish name.
    # Retired: promo:label, promo:scaleValueLabel (-> rdfs:label),
    #          promo:axisName, promo:scaleName (-> promo:name).
    for old, new in [(PROMO["label"], RDFS.label),
                     (PROMO["scaleValueLabel"], RDFS.label),
                     (PROMO["axisName"], PROMO["name"]),
                     (PROMO["scaleName"], PROMO["name"])]:
        n = 0
        for gr in store.dataset.graphs():
            for s, o in list(gr.subject_objects(old)):
                gr.remove((s, old, o))
                gr.add((s, new, o))
                n += 1
        if n:
            print(f"label   {str(old).split('#')[-1]:<16} -> "
                  f"{str(new).split('#')[-1]} ({n} triples)")

    root = URIRef(f"{base}#domain_root")
    phys = URIRef(f"{base}#domain_physical")
    info = URIRef(f"{base}#domain_information")
    role_phys = URIRef(f"{base}#axis_role_physical")
    state_term = URIRef(f"{base}#term_role_state")

    # --- Root domain (global scope) ------------------------------------
    # Tokens and scale dimensions bound to root are inherited by every
    # branch.  physical / information are reparented under it.
    if (root, None, None) not in g:
        store.add_domain(g, "root", iri=root)
        print("domain  root                 (created)")
    for branch_root in (phys, info):
        g.set((branch_root, PROMO["parent"], root))
    print("domain  physical/information   reparented under root")

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
    # Role = var/expr graph position only (2026-09-16 discussion).
    # Drop the old domain-echo terms — a variable's domain is carried by
    # its defining equation's domain, not by its role.
    for frag in ("property", "conversion", "observation",
                 "network_structure", "transport"):
        term = URIRef(f"{base}#term_role_{frag}")
        if (term, None, None) in g:
            g.remove((term, None, None))
            print(f"term    {frag:<20} (domain echo, removed)")

    derived_term = URIRef(f"{base}#term_role_derived")
    for frag, label, parent in [
        ("derived", "derived", None),
        ("port", "port", None),
        ("flow", "flow", None),
        ("secondary_state", "secondary-state", derived_term),
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

    # --- Token kinds (conserved | reference) ---------------------------
    for frag in ("energy", "mass", "momentum", "charge", "entropy",
                 "component_mass"):
        g.set((URIRef(f"{base}#token_{frag}"), PROMO["tokenKind"],
               Literal("conserved")))
    signal_tok = URIRef(f"{base}#token_signal")
    g.set((signal_tok, PROMO["tokenKind"], Literal("reference")))
    print("token   *                    tokenKind patched")

    # Signal subtokens: observation / manipulation.  Control-internal
    # refinement (controller-state, state-estimate, control-error, …)
    # deliberately deferred — see docs/ontology-design-discussion-2026-09-16.md
    obs_tok = URIRef(f"{base}#token_observation")
    man_tok = URIRef(f"{base}#token_manipulation")
    for tok_iri, label in [(obs_tok, "Observation"),
                           (man_tok, "Manipulation")]:
        store.add_token(g, tok_iri, label, parent=signal_tok,
                        kind="reference")
        print(f"token   {label:<20} < token_signal")

    # --- Dimension kinds + phase (content dimension) -------------------
    for frag in ("scale_time", "scale_length"):
        g.set((URIRef(f"{base}#{frag}"), PROMO["dimensionKind"],
               Literal("structural")))
    # Time is global (dynamic systems): rebind to the root domain so
    # both branches inherit it.  Length stays bound to physical.
    g.set((URIRef(f"{base}#scale_time"), PROMO["hasDomain"], root))
    print("dim     time                 hasDomain → domain_root (global)")
    phase_dim = URIRef(f"{base}#scale_phase")
    if (phase_dim, None, None) in g:
        print("dim     phase                (already present, skipped)")
    else:
        store.add_scale_dimension(g, phase_dim, "phase", phys,
                                  kind="content")
        phase_vals = {}
        for frag, label, parent_key in [
            ("solid", "solid", None),
            ("fluid", "fluid", None),
            ("fluid_liquid", "liquid", "fluid"),
            ("fluid_gas", "gas", "fluid"),
            ("pseudo", "pseudo", None),
        ]:
            val_iri = store.mint_iri(base, f"sval_phase_{frag}")
            store.add_scale_value(g, val_iri, phase_dim, label,
                                  parent=phase_vals.get(parent_key))
            phase_vals[frag] = val_iri
        print("dim     phase                kind=content + solid/fluid{liquid,gas}/pseudo")

    # --- Entity types: drop physical scale values from info types ----
    # The scale dimensions (time, length) are bound to the physical
    # domain; information entity types classify via temporal_type only.
    for frag in ("info_constant", "info_dynamic", "info_event"):
        et = URIRef(f"{base}#etype_{frag}")
        n = len(list(g.triples((et, PROMO["hasScaleValue"], None))))
        if n:
            g.remove((et, PROMO["hasScaleValue"], None))
            print(f"etype   {frag:<20} physical scale values removed ({n})")

    # --- Entity types: complete CWA 17960 scale-value compositions -----
    # point (4.1.4 event-dynamic / infinitesimal) was missing its time
    # value; transport_system (4.1.5 event-dynamic / distributed) had
    # no scale values at all.
    for frag, svals in [
        ("etype_point", ["sval_time_macro_event_dynamic"]),
        ("etype_transport_system", ["sval_time_macro_event_dynamic",
                                    "sval_length_macroscopic_distributed"]),
    ]:
        et = URIRef(f"{base}#{frag}")
        for sv in svals:
            sv_iri = URIRef(f"{base}#{sv}")
            if (et, PROMO["hasScaleValue"], sv_iri) not in g:
                g.add((et, PROMO["hasScaleValue"], sv_iri))
                print(f"etype   {frag:<20} + {sv}")

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
    # reference (accessibility) arcs share the signal token — sensor
    # and actuation carry the specialised subtokens so token matching
    # can discriminate observation from manipulation.
    physical_token_iris = [
        URIRef(f"{base}#token_{t}") for t in (
            "energy", "mass", "momentum", "charge", "entropy",
            "component_mass")
    ]
    for frag, tokens in [
        ("rule_physical-same", physical_token_iris),
        ("rule_access", [signal_tok]),
        ("rule_sensor", [obs_tok]),
        ("rule_actuation", [man_tok]),
        ("rule_signal", [signal_tok]),
    ]:
        rule_iri = URIRef(f"{base}#{frag}")
        g.remove((rule_iri, PROMO["sharedTokens"], None))
        for tok in tokens:
            g.add((rule_iri, PROMO["sharedTokens"], tok))
    print("rule    *                    sharedTokens normalised")

    # The signal token lives on the ROOT domain: any physical node can
    # expose variables (sensor/actuation/access arcs) and the
    # information branch processes them.  Remove the old branch-level
    # and transport-only bindings — signal is now inherited everywhere.
    transport = URIRef(f"{base}#domain_transport")
    g.add((root, PROMO["hasToken"], signal_tok))
    g.remove((phys, PROMO["hasToken"], signal_tok))
    g.remove((info, PROMO["hasToken"], signal_tok))
    g.remove((transport, PROMO["hasToken"], signal_tok))
    print("token   signal               branch roots → domain_root")

    # --- Extensity axis (physical) -------------------------------------
    ext_axis = URIRef(f"{base}#axis_extensity")
    if (ext_axis, None, None) not in g:
        store.add_classification_axis(g, ext_axis, phys, "Extensity")
        for frag in ("extensive", "intensive"):
            store.add_axis_term(
                g, URIRef(f"{base}#term_extensity_{frag}"), ext_axis, frag)
        print("axis    Extensity          + extensive/intensive")

    # --- Dedupe axes -----------------------------------------------------
    # A UI-created duplicate ("axis_Extensity") coexisted with the
    # seeded axis_extensity.  For any (axisName, hasDomain) pair with
    # more than one axis, keep the seed-convention IRI (all-lowercase
    # fragment) and remove the rest together with their terms.
    by_key = {}
    for a in g.subjects(RDF.type, PROMO["ClassificationAxis"]):
        key = (str(g.value(a, PROMO["name"])),
               g.value(a, PROMO["hasDomain"]))
        by_key.setdefault(key, []).append(a)
    for (name, _dom), axes in by_key.items():
        if len(axes) < 2:
            continue
        axes.sort(key=lambda a: (
            str(a).split("#")[-1] != str(a).split("#")[-1].lower(),
            str(a)))
        for dup in axes[1:]:
            for term in list(g.subjects(PROMO["hasAxis"], dup)):
                g.remove((term, None, None))
                g.remove((None, None, term))
            g.remove((dup, None, None))
            g.remove((None, None, dup))
            print(f"axis    {name:<20} duplicate removed: "
                  f"{dup}")

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

    # --- Vocabulary declarations (rdfs:Class / rdf:Property, no OWL) ---
    n = store.declare_vocabulary(g)
    if n:
        print(f"vocab   {n} terms declared (rdfs:Class / rdf:Property)")

    out = store.save()
    print(f"\nSaved {len(g)} triples to {out}")
    print("Restart the backend (./dev.sh restart) to pick up the file.")


if __name__ == "__main__":
    main()
