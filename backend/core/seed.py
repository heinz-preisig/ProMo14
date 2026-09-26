"""Ontology seeding — the ``SeedMixin`` half of ``RdfStore``.

Split out of ``core/graph_store.py`` for size: everything here writes
the default ProMo ontology (domain tree, tokens, axes, entity types,
connection rules) plus the migratable seed-floor steps that top up
existing graphs.  Methods use ``self`` like ordinary ``RdfStore``
members — ``RdfStore(SeedMixin, PersistenceMixin)`` composes them
back together.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

from .vocab import PROMO, SEED_CONSTANTS, SEED_FLOOR


class SeedMixin:
    """Ontology seeding: the initial two-branch ontology plus the
    migratable seed-floor steps (constants, transport mechanisms, arc
    sub-indices, capabilities, scale regimes)."""
    def seed_default_ontology(self) -> None:
        """Seed the default ProMo14 ontology (two-branch domain tree,
        tokens, classification axes, entity types, connection rules).

        Called when no ``ontology.trig`` exists.
        """
        g = self.ontology_graph
        # Namespace discipline (contract D1): promo# is vocabulary only;
        # instances mint under the owning graph's namespace.
        base = str(self.ONTOLOGY_GRAPH_IRI)

        # --- Domain tree: universe + two branches ---
        # The universe domain is the global scope: tokens and scale
        # dimensions bound to it are inherited by every branch.
        root_iri = self.mint_iri(base, "domain_universe")
        self.add_domain(g, "universe", iri=root_iri)

        phys_iri = self.mint_iri(base, "domain_physical")
        self.add_domain(g, "physical", iri=phys_iri, parent=root_iri,
                        branch="physical")

        info_iri = self.mint_iri(base, "domain_information")
        self.add_domain(g, "information", iri=info_iri, parent=root_iri,
                        branch="information")

        # --- Tokens ---
        # Token kinds (promo:tokenKind):
        #   conserved — accumulate in capacities, transferred by
        #               token-flow arcs, appear in balances (F·fx)
        #   reference — variable access; carried by reference arcs,
        #               reading never depletes, no balance
        physical_tokens = {
            "energy": "Energy",
            "mass": "Mass",
            "momentum": "Momentum",
            "charge": "Charge",
            "entropy": "Entropy",
            "component_mass": "Component Mass",
        }
        for frag, label in physical_tokens.items():
            tok_iri = self.mint_iri(base, f"token_{frag}")
            self.add_token(g, tok_iri, label, kind="conserved")

        # component_mass is a subtoken of mass (mass decomposed by species).
        g.set((self.mint_iri(base, "token_component_mass"), PROMO["parent"],
               self.mint_iri(base, "token_mass")))

        # signal = the reference-kind token: the currency of all
        # reference-carrier arcs (sensor, actuation, access, signal).
        # observation / manipulation are the seeded subtokens — the
        # control-internal taxonomy (controller-state, state-estimate,
        # control-error, …) is deliberately deferred.
        signal_iri = self.mint_iri(base, "token_signal")
        self.add_token(g, signal_iri, "Signal", kind="reference")
        signal_subtokens = {}
        for frag, label in [("observation", "Observation"),
                            ("manipulation", "Manipulation")]:
            sub_iri = self.mint_iri(base, f"token_{frag}")
            self.add_token(g, sub_iri, label, parent=signal_iri,
                           kind="reference")
            signal_subtokens[frag] = sub_iri

        # Bind tokens to domains.  Conserved tokens live on the physical
        # branch; signal lives on the ROOT — any physical node can
        # expose variables (sensor/actuation/access arcs) and the
        # information branch processes them.
        for frag in physical_tokens:
            tok_iri = self.mint_iri(base, f"token_{frag}")
            g.add((phys_iri, PROMO["hasToken"], tok_iri))
        g.add((root_iri, PROMO["hasToken"], signal_iri))

        # --- Classification axes ---
        # Physical branch: two axes, one question each
        # (design discussion 2026-09-24):
        #   determination — is the value fixed or does it vary?
        #     constant|variable (solved-ness itself is structural —
        #     derived = has a defining equation, port = port_variable
        #     flag on the bipartite graph, so neither is an axis term)
        #   function      — what does the variable physically do?
        #     parameter lives here: a parameter is a characteristic
        #     value in a function — part of the function definition,
        #     often embodying a specific assumption — not a
        #     determination mode.  determination=variable +
        #     function=parameter is a rebindable parameter,
        #     constant + parameter a fixed one.
        # Information branch keeps a single "role" axis; differential-state
        # lives there for the control canonical form dx/dt = A.x + B.u —
        # A needs two distinct index objects over the state set (a
        # variable's index structure may not repeat an index).
        def seed_axis(axis_frag, term_prefix, name, domain_iri, terms):
            axis_iri = self.mint_iri(base, f"axis_{axis_frag}")
            self.add_classification_axis(g, axis_iri, domain_iri, name)
            term_iris: Dict[str, URIRef] = {}
            for term, parent_label in terms:
                frag = term.replace("-", "_")
                term_iri = self.mint_iri(base, f"term_{term_prefix}_{frag}")
                parent_iri = (term_iris.get(parent_label)
                              if parent_label else None)
                self.add_axis_term(g, term_iri, axis_iri, term,
                                   parent=parent_iri)
                term_iris[term] = term_iri

        seed_axis("determination_physical", "determination",
                  "determination", phys_iri, [
                      ("constant", None),
                      ("variable", None),
                  ])
        seed_axis("function_physical", "function", "function", phys_iri, [
            ("state", None),
            ("fundamental-state", "state"),
            ("secondary-state", "state"),
            ("effort", None),
            ("flow", None),
            ("frame", None),
            ("reaction", None),
            ("parameter", None),
        ])
        seed_axis("role_information", "info_role", "role", info_iri, [
            ("state", None),
            ("differential-state", "state"),
            ("input", None),
            ("output", None),
            ("constant", None),
            ("parameter", None),
        ])

        # --- Scale dimensions + values (seed) ---
        # Time scale: 4 levels, each with triple-domain children
        # (constant / dynamic / event-dynamic).
        # Multi-scale stacking: lower level's constant = higher level's
        # event-dynamic.  Entity types reference the fine-grained children.
        # These are seeds — user can rename, restructure, add levels.
        # Time is global (dynamic systems): bound to the root domain so
        # both branches inherit it.  Length stays physical-only.
        time_scale_iri = self.mint_iri(base, "scale_time")
        self.add_scale_dimension(g, time_scale_iri, "time", root_iri,
                                 kind="structural")
        time_val_iris = {}
        time_levels = ["molecular", "nano", "milli", "macro"]
        time_triple = ["constant", "dynamic", "event-dynamic"]
        for level in time_levels:
            level_iri = self.mint_iri(base, f"sval_time_{level}")
            self.add_scale_value(g, level_iri, time_scale_iri, level)
            time_val_iris[f"time_{level}"] = level_iri
            for triple in time_triple:
                tkey = triple.replace("-", "_")
                child_key = f"time_{level}_{tkey}"
                child_iri = self.mint_iri(base, f"sval_{child_key}")
                self.add_scale_value(g, child_iri, time_scale_iri, triple,
                                     parent=level_iri)
                time_val_iris[child_key] = child_iri

        # Length scale: 4 levels, each with spatial sub-values.
        # infinitesimal: point (zero-size), finite (small)
        # microscopic, macroscopic: uniform, distributed
        # infinite: uniform only
        length_scale_iri = self.mint_iri(base, "scale_length")
        self.add_scale_dimension(g, length_scale_iri, "length", phys_iri,
                                 kind="structural")
        length_val_iris = {}
        length_levels = [
            ("infinitesimal", ["point", "finite"]),
            ("microscopic", ["uniform", "distributed"]),
            ("macroscopic", ["uniform", "distributed"]),
            ("infinite", ["uniform"]),
        ]
        for level, sub_labels in length_levels:
            level_iri = self.mint_iri(base, f"sval_length_{level}")
            self.add_scale_value(g, level_iri, length_scale_iri, level)
            length_val_iris[f"length_{level}"] = level_iri
            for sub in sub_labels:
                child_key = f"length_{level}_{sub}"
                child_iri = self.mint_iri(base, f"sval_{child_key}")
                self.add_scale_value(g, child_iri, length_scale_iri, sub,
                                     parent=level_iri)
                length_val_iris[child_key] = child_iri

        # --- Content dimensions ---
        # Phase is a CONTENT dimension (kind="content"): it never
        # composes entity types — it is bound per model-node instance
        # and consumed by the properties domain for constitutive
        # routing.  Pseudo-phases (averaged-mixture models) are just
        # terms whose meaning is defined by the property network
        # implementing them.
        phase_iri = self.mint_iri(base, "scale_phase")
        self.add_scale_dimension(g, phase_iri, "phase", phys_iri,
                                 kind="content")
        phase_vals: Dict[str, URIRef] = {}
        for frag, label, parent_key in [
            ("solid", "solid", None),
            ("fluid", "fluid", None),
            ("fluid_liquid", "liquid", "fluid"),
            ("fluid_gas", "gas", "fluid"),
            ("pseudo", "pseudo", None),
        ]:
            val_iri = self.mint_iri(base, f"sval_phase_{frag}")
            self.add_scale_value(g, val_iri, phase_iri, label,
                                 parent=phase_vals.get(parent_key))
            phase_vals[frag] = val_iri

        # --- Entity types (CWA 17960 seed) ---
        # Entity types are compositions of fine-grained scale values.
        # temporal_type / spatial_type / spatial_size are legacy fields
        # kept for backward compat; the canonical definition is the
        # scale value composition.  Behaviour Linker assigns a specific
        # scale level to a base entity.
        entity_types = [
            ("environment", "constant", "uniform", "infinite", "physical",
             "Constant/uniform/infinite — environment",
             ["time_macro_constant", "length_infinite_uniform"]),
            ("lumped", "dynamic", "uniform", "finite", "physical",
             "Dynamic/uniform/finite — lumped ODE",
             ["time_macro_dynamic", "length_macroscopic_uniform"]),
            ("distributed", "dynamic", "distributed", "finite", "physical",
             "Dynamic/distributed/finite — distributed PDE",
             ["time_macro_dynamic", "length_macroscopic_distributed"]),
            ("point", "event-dynamic", "uniform", "infinitesimal", "physical",
             "Event-dynamic/point/infinitesimal — point (reactions)",
             ["time_molecular_event_dynamic", "length_infinitesimal_point"]),
            ("transport_system", "event-dynamic", "distributed", "finite", "physical",
             "Event-dynamic/distributed/finite — transport system (node, not arc)",
             ["time_molecular_event_dynamic", "length_microscopic_distributed"]),
            # Information entity types carry no scale values: the scale
            # dimensions are bound to the physical domain.  Their
            # classification is the temporal_type triple only.
            ("info_constant", "constant", None, None, "information",
             "Constant information capacity",
             []),
            ("info_dynamic", "dynamic", None, None, "information",
             "Dynamic information capacity",
             []),
            ("info_event", "event-dynamic", None, None, "information",
             "Event-dynamic information capacity (instantaneous I/O)",
             []),
        ]
        all_scale_vals = {**time_val_iris, **length_val_iris}
        for frag, temporal, spatial, size, branch, desc, scale_frags in entity_types:
            et_iri = self.mint_iri(base, f"etype_{frag}")
            self.add_entity_type(g, et_iri, frag.replace("_", " ").title(),
                                 temporal, branch, spatial_type=spatial,
                                 spatial_size=size, description=desc)
            for sf in scale_frags:
                if sf in all_scale_vals:
                    g.add((et_iri, PROMO["hasScaleValue"], all_scale_vals[sf]))

        # --- Connection rules ---
        # Arc semantics live in rule attributes, not in the type name:
        #   direction : unidirectional | bidirectional
        #   carrier   : token-flow | reference
        #   scope     : same | cross | any   (branch constraint:
        #               same = shared ancestor, cross = none)
        # physical-cross was retired (2026-09-15): a token-flow arc with
        # scope=cross can never apply (cross-branch pairs share no
        # tokens); physical-same covers all intra-physical continuity.
        physical_token_iris = [
            self.mint_iri(base, f"token_{f}") for f in physical_tokens
        ]
        rules = [
            ("physical-same", "bidirectional", "token-flow", "same",
             phys_iri, phys_iri, physical_token_iris,
             "Same branch, shared tokens — physical arc (continuity)"),
            ("signal", "unidirectional", "reference", "same",
             info_iri, info_iri, [signal_iri],
             "Signal connection — information arc (unidirectional)"),
        ]
        for rule_type, direction, carrier, scope, src, tgt, shared, desc in rules:
            rule_iri = self.mint_iri(base, f"rule_{rule_type}")
            self.add_connection_rule(g, rule_iri, rule_type,
                                     direction=direction, carrier=carrier,
                                     scope=scope, source_domain=src,
                                     target_domain=tgt, shared_tokens=shared,
                                     description=desc)

        # access: physical→physical reference arcs (service couplings —
        # reactions, properties, geometry reading host state). Domain-
        # constrained to the physical branch, so resolve_connection
        # prefers it over the unconstrained signal rule for those pairs.
        access_iri = self.mint_iri(base, "rule_access")
        self.add_connection_rule(g, access_iri, "access",
                                 direction="unidirectional",
                                 carrier="reference", scope="same",
                                 source_domain=phys_iri,
                                 target_domain=phys_iri,
                                 shared_tokens=[signal_iri],
                                 description="Physical→physical accessibility arc (service coupling)")

        # signal is information-internal; sensor/actuation close the loop
        # across the branch boundary (scope=cross — no shared ancestor).
        # They carry the specialised signal subtokens so token matching
        # can discriminate observation from manipulation.
        for name, src, tgt, shared, desc in [
            ("sensor", phys_iri, info_iri, [signal_subtokens["observation"]],
             "Physical→information accessibility arc (measurement)"),
            ("actuation", info_iri, phys_iri, [signal_subtokens["manipulation"]],
             "Information→physical accessibility arc (control loop closure)"),
        ]:
            self.add_connection_rule(
                g, self.mint_iri(base, f"rule_{name}"), name,
                direction="unidirectional", carrier="reference",
                scope="cross", source_domain=src, target_domain=tgt,
                shared_tokens=shared, description=desc)

        # --- Indices ---
        # species: enumerates chemical components, bound to component mass token.
        # node / arc: index the network graph topology.
        seed_indices = [
            ("idx_species", "species", "S", "physical", "index",
             "token_component_mass"),
            ("idx_node", "node", "N", "physical", "node", None),
            ("idx_arc", "arc", "A", "physical", "arc", None),
        ]
        for frag, label, short, network, iclass, token_frag in seed_indices:
            internal_id = self.next_internal_id("I")
            self.add_index_dict(g, {
                "iri": str(self.mint_iri(base, frag)),
                "label": label,
                "short_name": short,
                "network": network,
                "index_class": iclass,
                "internal_id": internal_id,
                "aliases": {"global_ID": internal_id, "internal_code": short},
                "token": str(self.mint_iri(base, token_frag)) if token_frag else None,
            })

        # --- Seed floor (migratable subset) ---
        # Universal constants (ADR-008), scale regimes, transport
        # mechanisms + arc sub-indices (§16), §20 capabilities — the
        # same ordered sequence load() and apply-seed-floor run, so a
        # fresh seed and a migrated store carry the same floor.
        self.apply_seed_floor(g, base)

        # --- Equation classes (top-level hierarchy) ---
        eq_classes = ["generic", "instantiate", "balance", "empirical", "user_function"]
        for ec in eq_classes:
            ec_iri = self.mint_iri(base, f"eqclass_{ec}")
            self.add_equation_class(g, ec_iri, ec)

        # --- Artefact-type marker (self-description) ------------------
        g.add((g.identifier, RDF.type, PROMO["Ontology"]))

        # --- Vocabulary declarations (rdfs:Class / rdf:Property) -------
        self.declare_vocabulary(g)

    def apply_seed_floor(self, g: Graph, base: str) -> None:
        """Run the migratable seed sequence against ``g`` and stamp the
        floor revision (``promo:seedFloor``).

        Shared by ``load()`` (core graph, automatic) and
        ``POST /api/ontology/apply-seed-floor`` (draft ontology forks,
        opt-in) so the two can't diverge.  Order matters: scale regimes
        before transport mechanisms (regimes create scale values the
        transport migration binds), capabilities last (they grant onto
        the ``mass_transport`` grouping).  Every step is idempotent by
        deterministic IRI, so re-applying the floor is a no-op plus a
        stamp refresh.
        """
        self._seed_constants(g, base)
        self._seed_scale_regimes(g, base)
        self._seed_transport_mechanisms(g, base)
        self._seed_arc_sub_indices(g, base)
        self._seed_capabilities(g, base)
        g.set((g.identifier, PROMO["seedFloor"], Literal(SEED_FLOOR)))

    def _seed_constants(self, g: Graph, base: str) -> None:
        """Add the universal constants (``zero``, ``one``, ``half``).

        Idempotent by deterministic IRI — also called from ``load()`` as
        a migration for stores that predate ADR-008.  Constants carry a
        pre-bound ``promo:value`` (permanent: fixed by mathematics) and a
        latex alias so documents render numerals, not labels.
        """
        for frag, label, value, latex in SEED_CONSTANTS:
            iri = self.mint_iri(base, frag)
            if (iri, RDF.type, PROMO["Variable"]) in g:
                continue
            internal_id = self.next_internal_id("V")
            self.add_variable_dict(g, {
                "iri": str(iri),
                "label": label,
                "network": "root",
                "type": "constant",
                "internal_id": internal_id,
                "aliases": {"global_ID": internal_id, "latex": latex},
                "value": value,
                "doc": "Universal constant",
            })

    def _seed_transport_mechanisms(self, g: Graph, base: str) -> None:
        """Add transport mechanism entity subtypes, grouped by token.

        Idempotent by deterministic IRI — also called from ``load()`` as
        a migration for stores that predate §16.  Mechanisms are
        per-token: mass transports by diffusion and convection, energy
        by heat (conduction), radiation and work (mechanical/volume).
        The token-level grouping types give the balance equations their
        incidence partition; the leaves give the constitutive-law
        partition.  Arcs derive membership from the transport node they
        touch.
        """
        root = self.mint_iri(base, "etype_transport_system")
        if (root, RDF.type, PROMO["EntityType"]) not in g:
            return
        # Continuum regime bindings — transport is continuum-domain;
        # the molecular time level would misclassify it as particulate.
        scales = [
            self.mint_iri(base, "sval_time_macro_event_dynamic"),
            self.mint_iri(base, "sval_length_microscopic_distributed"),
        ]
        # (frag, label, parent_frag, bind_scales) — parents first.
        tree = [
            ("mass_transport", "Mass Transport", "transport_system", False),
            ("energy_transport", "Energy Transport", "transport_system", False),
            ("diffusion_transport", "Diffusion Transport", "mass_transport", True),
            ("convection_transport", "Convection Transport", "mass_transport", True),
            ("heat_transport", "Heat Transport", "energy_transport", True),
            ("radiation_transport", "Radiation Transport", "energy_transport", True),
            ("work_transport", "Work Transport", "energy_transport", True),
        ]
        for frag, label, parent_frag, bind_scales in tree:
            iri = self.mint_iri(base, f"etype_{frag}")
            parent_iri = self.mint_iri(base, f"etype_{parent_frag}")
            if (iri, RDF.type, PROMO["EntityType"]) in g:
                # Migration: reparent seeds that predate the token
                # grouping (they sit directly under transport_system).
                # A parent set to anything else is a deliberate user
                # edit — leave it alone.
                cur = g.value(iri, PROMO["parent"])
                if cur is None or cur == root:
                    g.set((iri, PROMO["parent"], parent_iri))
                if bind_scales:
                    # Regime migration: drop the molecular time binding
                    # (predates the regime layer) and ensure the
                    # continuum bindings landed — older stores may
                    # lack the length value at original seed time.
                    g.remove((iri, PROMO["hasScaleValue"], self.mint_iri(
                        base, "sval_time_molecular_event_dynamic")))
                    for sv in scales:
                        if (sv, None, None) in g:
                            g.add((iri, PROMO["hasScaleValue"], sv))
                continue
            self.add_entity_type(
                g, iri, label,
                "event-dynamic", "physical",
                spatial_type="distributed", spatial_size="finite",
                description=f"Transport system — {label.lower()} mechanism",
                scale_values=[sv for sv in scales
                              if bind_scales and (sv, None, None) in g],
                parent=parent_iri,
            )

    def _seed_arc_sub_indices(self, g: Graph, base: str) -> None:
        """Add arc sub-indices partitioned by token and mechanism.

        Idempotent by deterministic IRI — migration for stores that
        predate §16.  ``A_mass``/``A_energy`` select the token-level
        grouping entity types (membership over leaf subtypes — needs
        transitive resolution at instantiation); the rest select a
        single mechanism leaf.  Instantiation resolves membership, the
        checker sees plain distinct indices.  Short names use
        underscore — ``^`` is the power operator.
        """
        arc_iri = self.mint_iri(base, "idx_arc")
        if (arc_iri, RDF.type, PROMO["Index"]) not in g:
            return
        for frag, label, short, sel_frag in [
            ("idx_arc_mass", "mass arc", "A_mass",
             "etype_mass_transport"),
            ("idx_arc_energy", "energy arc", "A_energy",
             "etype_energy_transport"),
            ("idx_arc_diffusion", "diffusion arc", "A_diff",
             "etype_diffusion_transport"),
            ("idx_arc_convection", "convection arc", "A_conv",
             "etype_convection_transport"),
            ("idx_arc_heat", "heat arc", "A_heat",
             "etype_heat_transport"),
            ("idx_arc_radiation", "radiation arc", "A_rad",
             "etype_radiation_transport"),
            ("idx_arc_work", "work arc", "A_work",
             "etype_work_transport"),
        ]:
            iri = self.mint_iri(base, frag)
            if (iri, RDF.type, PROMO["Index"]) in g:
                continue
            internal_id = self.next_internal_id("I")
            self.add_index_dict(g, {
                "iri": str(iri),
                "label": label,
                "short_name": short,
                "network": "physical",
                "index_class": "arc",
                "internal_id": internal_id,
                "aliases": {"global_ID": internal_id, "internal_code": short},
                "sub_index_of": str(arc_iri),
                "selector": str(self.mint_iri(base, sel_frag)),
            })

    def _seed_capabilities(self, g: Graph, base: str) -> None:
        """Seed entity-type capabilities (§20): which types may inject
        species, host reactions, or carry species.

        Idempotent — guarded by the ``cap_species_source`` resource, and
        called from ``load()`` as a migration for stores that predate
        §20.  A capability is a ``promo:Capability`` resource the entity
        type references via ``promo:capability``; subtypes inherit it
        through ``promo:parent`` ancestry (the modeller checks the
        ancestor chain).  ``species_transport`` sits on the
        ``mass_transport`` grouping so diffusion/convection inherit it
        while energy transport does not.
        """
        anchor = self.mint_iri(base, "cap_species_source")
        if (anchor, RDF.type, PROMO["Capability"]) in g:
            return
        caps = {
            "species_source":
                "Species Source — may inject a species allocation",
            "reaction_host":
                "Reaction Host — may host reactions",
            "species_transport":
                "Species Transport — carries species (permeability)",
        }
        cap_iris = {}
        for frag, desc in caps.items():
            iri = self.mint_iri(base, f"cap_{frag}")
            cap_iris[frag] = iri
            g.add((iri, RDF.type, PROMO["Capability"]))
            g.add((iri, RDFS.label, Literal(frag.replace("_", " "))))
            g.add((iri, PROMO["doc"], Literal(desc)))
        # entity-type frag → capability frags it grants
        grants = {
            "environment": ["species_source"],
            "lumped": ["reaction_host"],
            "distributed": ["reaction_host"],
            "point": ["reaction_host"],
            "mass_transport": ["species_transport"],
        }
        for et_frag, cap_frags in grants.items():
            et = self.mint_iri(base, f"etype_{et_frag}")
            if (et, RDF.type, PROMO["EntityType"]) not in g:
                continue
            for cf in cap_frags:
                g.add((et, PROMO["capability"], cap_iris[cf]))

    def _seed_scale_regimes(self, g: Graph, base: str) -> None:
        """Group scale levels under regime values (particulate|continuum).

        Idempotent — also called from ``load()`` as a migration for
        stores that predate the regime layer.  Regime is a scale
        distinction: particulate = discrete matter (molecular level),
        continuum = continuum assumption (all other levels).  Entity
        types keep binding leaf values; regime is derived by walking
        ``promo:parent`` ancestry — no separate classification that
        could contradict the scale binding.
        """
        length_iri = self.mint_iri(base, "scale_length")
        if (length_iri, RDF.type, PROMO["ScaleDimension"]) not in g:
            return
        time_iri = self.mint_iri(base, "scale_time")

        # Regime grouping values — new top level of each structural tree.
        regimes = {}
        for dim_iri, frag, label in [
            (length_iri, "length_particulate", "particulate"),
            (length_iri, "length_continuum", "continuum"),
            (time_iri, "time_particulate", "particulate"),
            (time_iri, "time_continuum", "continuum"),
        ]:
            if (dim_iri, RDF.type, PROMO["ScaleDimension"]) not in g:
                continue
            iri = self.mint_iri(base, f"sval_{frag}")
            if (iri, RDF.type, PROMO["ScaleValue"]) not in g:
                self.add_scale_value(g, iri, dim_iri, label)
            regimes[frag] = iri

        # Level specs: (level frag, regime frag, [children]).  The
        # particulate length level (molecular) is new — a particle is
        # point/finite, mirroring infinitesimal's spatial children.
        specs = [
            (length_iri, [
                ("length_molecular", "length_particulate",
                 ["point", "finite"]),
                ("length_infinitesimal", "length_continuum",
                 ["point", "finite"]),
                ("length_microscopic", "length_continuum",
                 ["uniform", "distributed"]),
                ("length_macroscopic", "length_continuum",
                 ["uniform", "distributed"]),
                ("length_infinite", "length_continuum", ["uniform"]),
            ]),
            (time_iri, [
                ("time_molecular", "time_particulate",
                 ["constant", "dynamic", "event-dynamic"]),
                ("time_nano", "time_continuum",
                 ["constant", "dynamic", "event-dynamic"]),
                ("time_milli", "time_continuum",
                 ["constant", "dynamic", "event-dynamic"]),
                ("time_macro", "time_continuum",
                 ["constant", "dynamic", "event-dynamic"]),
            ]),
        ]
        for dim_iri, levels in specs:
            if (dim_iri, RDF.type, PROMO["ScaleDimension"]) not in g:
                continue
            for level_frag, regime_frag, children in levels:
                regime_iri = regimes.get(regime_frag)
                if regime_iri is None:
                    continue
                level_iri = self.mint_iri(base, f"sval_{level_frag}")
                if (level_iri, RDF.type, PROMO["ScaleValue"]) not in g:
                    # Missing level (older store) — create under regime.
                    self.add_scale_value(
                        g, level_iri, dim_iri,
                        level_frag.split("_", 1)[1], parent=regime_iri)
                elif g.value(level_iri, PROMO["parent"]) is None:
                    # Existing top level — group it under its regime.
                    # A user-set parent is a deliberate edit: untouched.
                    g.set((level_iri, PROMO["parent"], regime_iri))
                # Ensure children exist — older stores may lack them.
                for sub in children:
                    child_iri = self.mint_iri(
                        base,
                        f"sval_{level_frag}_{sub.replace('-', '_')}")
                    if (child_iri, RDF.type, PROMO["ScaleValue"]) not in g:
                        self.add_scale_value(g, child_iri, dim_iri, sub,
                                             parent=level_iri)

        # Regime migration: nothing seeded is particulate — drop the
        # molecular time binding from continuum entity types (it
        # predates the regime layer and would misclassify them).
        # Mechanism leaves are handled in _seed_transport_mechanisms.
        molecular_time = self.mint_iri(
            base, "sval_time_molecular_event_dynamic")
        for frag in ("etype_point", "etype_transport_system"):
            g.remove((self.mint_iri(base, frag),
                      PROMO["hasScaleValue"], molecular_time))
