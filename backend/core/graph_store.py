"""Shared RDF graph store for the ProMo suite.

``RdfStore`` wraps an ``rdflib.Dataset`` and provides the low-level storage
that the ontology editor, equation editor, and modeller share.  It is
intentionally thin: it loads/saves named graphs from ``PROMO_DATA_DIR`` and
offers a few helpers for minting IRIs and importing the legacy v8 data.

The store uses a small ProMo vocabulary (``http://example.org#``).  The
initial content can be seeded from ``variables_v8.json``,
``fix_variables_v8.json``, ``ontology.json`` and ``variableExpression.trig``
using the existing legacy loader.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import rdflib
from rdflib import Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

from . import loader
from .config import get_data_dir

PROMO = Namespace("http://example.org#")
PROMOLG = Namespace("http://example.org/language#")
QUDT = Namespace("http://qudt.org/schema/qudt/")

# Legacy prefixes used in old TriG files.
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

# ProMo14 ontology vocabulary extensions (see docs/ontology-editor-v1-ticket.md)
#
# Domain tree
#   promo:Domain            — a domain in the tree (replaces promo:Network)
#   promo:branch            — "physical" or "information" (top-level only)
#   promo:hasToken          — links a domain to tokens that live in it
#
# Classification axes
#   promo:ClassificationAxis — an axis definition
#   promo:axisName          — axis label (e.g. "role", "extensivity")
#   promo:AxisTerm          — a term in an axis hierarchy
#   promo:axisValue         — links a variable to an axis term
#   promo:hasAxis           — links a domain to an axis it defines
#
# Scale dimensions and values (first-class concept)
#   promo:ScaleDimension   — a scale dimension (time scale, length scale, user-defined)
#   promo:scaleName        — dimension name (e.g. "time", "length")
#   promo:hasDomain        — links a scale dimension to the domain where it is defined
#   promo:ScaleValue       — a value in a scale dimension's hierarchical tree
#   promo:hasScale         — links a scale value to its dimension
#   promo:scaleValueLabel  — label for a scale value (e.g. "microscopic", "macroscopic")
#
# Entity type taxonomy (CWA 17960 — seed/default, not hardcoded schema)
#   promo:EntityType        — an entity type
#   promo:temporalType     — "constant" | "dynamic" | "event-dynamic"
#   promo:spatialType      — "uniform" | "distributed" (physical only)
#   promo:spatialSize      — "infinite" | "finite" | "infinitesimal" (physical only)
#   promo:hasScaleValue    — links an entity type to its scale value(s)
#
# Connection rules
#   promo:ConnectionRule    — a connection rule definition
#   promo:ruleType          — "physical-same" | "physical-cross" | "signal"
#   promo:sharedTokens      — tokens that must be shared for physical rules
#
# Equation classes (hierarchical)
#   promo:EquationClass     — an equation class node
#   promo:equationClass     — links an equation to its class (IRI, not string)
#
# Equations (nested in variable's named graph)
#   promo:Equation         — one equation (LHS variable + RHS expression)
#   promo:hasEquation      — links a variable to its equation(s)
#   promo:lhs              — the variable IRI being defined
#   promo:rhs              — the expression token stream (string)
#   promo:rhsLatex         — generated LaTeX of the RHS (cached)
#   promo:incidenceList     — list of variable IRIs in the RHS (JSON array)

# Module-level singleton so that all backend modules see the same store
# within one process.  The store is loaded on first access.
_STORE: Optional["RdfStore"] = None


def get_store() -> "RdfStore":
    """Return the shared ``RdfStore`` for this process."""
    global _STORE
    if _STORE is None:
        _STORE = RdfStore()
        _STORE.load()
    return _STORE

UNIT_FIELDS = [
    "time",
    "length",
    "mass",
    "current",
    "temperature",
    "amount",
    "light",
    "nil",
]


def _as_literal(value: Any) -> Literal:
    if isinstance(value, bool):
        return Literal(value, datatype=XSD.boolean)
    if isinstance(value, int):
        return Literal(value, datatype=XSD.integer)
    if isinstance(value, float):
        return Literal(value, datatype=XSD.double)
    if isinstance(value, (list, dict)):
        return Literal(json.dumps(value))
    return Literal(str(value))


class RdfStore:
    """In-memory RDF store backed by an ``rdflib.Dataset``.

    The store is the single source of truth for ontology data in ProMo14.
    It is loaded from ``PROMO_DATA_DIR`` on construction and can be saved back
    as a TriG file.  Named graphs are used to separate the ontology vocabulary
    from var/expr graphs and version snapshots.
    """

    # Default named graph for the editable ontology vocabulary.
    ONTOLOGY_GRAPH_IRI = URIRef("http://example.org/ontology")

    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        if data_dir is None:
            self.data_dir = get_data_dir()
        else:
            self.data_dir = Path(data_dir)
        self.dataset = Dataset()
        self._id_counters: Dict[str, int] = {}

        # Bind common prefixes so serialised TriG is readable.
        self.dataset.bind("promo", PROMO)
        self.dataset.bind("promolg", PROMOLG)
        self.dataset.bind("qudt", QUDT)
        self.dataset.bind("rdf", RDF)
        self.dataset.bind("rdfs", RDFS)
        self.dataset.bind("xsd", XSD)

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load the ontology from ``PROMO_DATA_DIR``.

        If ``ontology.trig`` exists it is loaded first.  If the editable
        ontology graph is still empty, the legacy JSON/TriG files are imported
        as the initial seed.
        """
        ontology_path = self.data_dir / "ontology.trig"
        if ontology_path.exists():
            try:
                self.dataset.parse(str(ontology_path), format="trig")
            except Exception:
                pass

        if not len(self.ontology_graph):
            self.seed_from_legacy()

        if not len(self.ontology_graph):
            self.seed_default_ontology()

        # Load any additional var/expr named graphs that are already in the
        # data directory, but do not replace the editable ontology graph.
        for path in sorted(self.data_dir.glob("*.trig")):
            if path.name == "ontology.trig":
                continue
            try:
                self.dataset.parse(str(path), format="trig")
            except Exception:
                continue

    def save(self, filename: str = "ontology.trig") -> Path:
        """Serialise the dataset to ``PROMO_DATA_DIR/filename``.

        Returns the written file path.
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / filename
        self.dataset.serialize(str(path), format="trig")
        return path

    def seed_from_legacy(self) -> None:
        """Import legacy v8 JSON/TriG files into the store."""
        try:
            ctx = loader.load_context(self.data_dir)
        except FileNotFoundError:
            return

        ontology = self.ontology_graph
        for var in ctx["variables"].values():
            self.add_variable_dict(ontology, var)
        for idx in ctx["indices"].values():
            self.add_index_dict(ontology, idx)
        for parent, children in ctx.get("network_tree", {}).items():
            self.add_network(ontology, parent, children=children)

    def seed_default_ontology(self) -> None:
        """Seed the default ProMo14 ontology (two-branch domain tree,
        tokens, classification axes, entity types, connection rules).

        Called when no legacy data is found and no ``ontology.trig`` exists.
        """
        g = self.ontology_graph
        base = str(PROMO).rstrip("#")

        # --- Domain tree: two branches ---
        phys_iri = self.mint_iri(base, "domain_physical")
        self.add_domain(g, "physical", iri=phys_iri, branch="physical")

        info_iri = self.mint_iri(base, "domain_information")
        self.add_domain(g, "information", iri=info_iri, branch="information")

        # --- Tokens ---
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
            self.add_token(g, tok_iri, label)

        signal_iri = self.mint_iri(base, "token_signal")
        self.add_token(g, signal_iri, "Signal")

        # Bind tokens to domains.
        for frag in physical_tokens:
            tok_iri = self.mint_iri(base, f"token_{frag}")
            g.add((phys_iri, PROMO["hasToken"], tok_iri))
        g.add((info_iri, PROMO["hasToken"], signal_iri))

        # --- Classification axes: "role" axis on both branches ---
        role_phys_iri = self.mint_iri(base, "axis_role_physical")
        self.add_classification_axis(g, role_phys_iri, phys_iri, "role")
        role_info_iri = self.mint_iri(base, "axis_role_information")
        self.add_classification_axis(g, role_info_iri, info_iri, "role")

        physical_role_terms = ["state", "effort", "transport", "frame", "constant", "parameter"]
        for term in physical_role_terms:
            term_iri = self.mint_iri(base, f"term_role_{term}")
            self.add_axis_term(g, term_iri, role_phys_iri, term)

        information_role_terms = ["state", "input", "output", "constant", "parameter"]
        for term in information_role_terms:
            term_iri = self.mint_iri(base, f"term_info_role_{term}")
            self.add_axis_term(g, term_iri, role_info_iri, term)

        # --- Scale dimensions + values (seed) ---
        # Time scale: 4 levels, each with triple-domain children
        # (constant / dynamic / event-dynamic).
        # Multi-scale stacking: lower level's constant = higher level's
        # event-dynamic.  Entity types reference the fine-grained children.
        # These are seeds — user can rename, restructure, add levels.
        time_scale_iri = self.mint_iri(base, "scale_time")
        self.add_scale_dimension(g, time_scale_iri, "time", phys_iri)
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
        self.add_scale_dimension(g, length_scale_iri, "length", phys_iri)
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
            ("info_constant", "constant", None, None, "information",
             "Constant information capacity",
             ["time_macro_constant"]),
            ("info_dynamic", "dynamic", None, None, "information",
             "Dynamic information capacity",
             ["time_macro_dynamic"]),
            ("info_event", "event-dynamic", None, None, "information",
             "Event-dynamic information capacity (instantaneous I/O)",
             ["time_molecular_event_dynamic"]),
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

        # --- Connection rules (3 types) ---
        rules = [
            ("physical-same", "bidirectional",
             "Same domain, shared tokens — physical arc (continuity)"),
            ("physical-cross", "bidirectional",
             "Different physical domains, shared tokens — physical arc (continuity)"),
            ("signal", "unidirectional",
             "Signal connection — information arc (unidirectional)"),
        ]
        for rule_type, direction, desc in rules:
            rule_iri = self.mint_iri(base, f"rule_{rule_type}")
            self.add_connection_rule(g, rule_iri, rule_type,
                                     direction=direction, description=desc)

        # --- Indices ---
        # species: enumerates chemical components, bound to component mass token.
        # node / arc: index the network graph topology.
        seed_indices = [
            ("idx_species", "species", "s", "physical", "index",
             "token_component_mass"),
            ("idx_node", "node", "n", "physical", "node", None),
            ("idx_arc", "arc", "a", "physical", "arc", None),
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

        # --- Equation classes (top-level hierarchy) ---
        eq_classes = ["generic", "instantiate", "balance", "empirical", "user_function"]
        for ec in eq_classes:
            ec_iri = self.mint_iri(base, f"eqclass_{ec}")
            self.add_equation_class(g, ec_iri, ec)

    # ------------------------------------------------------------------
    # Named graph helpers
    # ------------------------------------------------------------------

    @property
    def ontology_graph(self) -> Graph:
        """Return the default editable ontology named graph."""
        return self.dataset.graph(self.ONTOLOGY_GRAPH_IRI)

    def graph(self, iri: Union[str, URIRef]) -> Graph:
        """Return or create a named graph."""
        if isinstance(iri, str):
            iri = URIRef(iri)
        return self.dataset.graph(iri)

    # ------------------------------------------------------------------
    # IRI minting
    # ------------------------------------------------------------------

    def mint_iri(self, base: Union[str, URIRef], fragment: str) -> URIRef:
        """Create a new IRI under ``base`` with the given fragment."""
        if isinstance(base, URIRef):
            base = str(base)
        base = base.rstrip("#")
        return URIRef(f"{base}#{fragment}")

    def next_internal_id(self, prefix: str) -> str:
        """Return the next internal ID for a prefix, e.g. ``V_1``.

        Counters start at the highest existing ID + 1 for the prefix.
        """
        if prefix not in self._id_counters:
            self._id_counters[prefix] = 0

        # Look for existing IDs in the ontology graph.
        for s, o in self.ontology_graph.subject_objects(PROMO["internalID"]):
            if isinstance(o, Literal):
                value = str(o)
                if value.startswith(prefix):
                    try:
                        num = int(value[len(prefix) :].lstrip("_"))
                        self._id_counters[prefix] = max(
                            self._id_counters[prefix], num
                        )
                    except ValueError:
                        pass

        self._id_counters[prefix] += 1
        # Old IDs were like "V_1", "I_3".  Keep that shape.
        return f"{prefix}_{self._id_counters[prefix]}"

    # ------------------------------------------------------------------
    # Add / update resources (dictionary-friendly)
    # ------------------------------------------------------------------

    def _set_literal(self, graph: Graph, subject: URIRef, predicate, value) -> None:
        if value is None:
            return
        graph.set((subject, predicate, _as_literal(value)))

    def _add_aliases(self, graph: Graph, subject: URIRef, aliases: dict) -> None:
        for key, value in aliases.items():
            if not value:
                continue
            pred = PROMO[key] if key in ("internal_code", "latex", "matlab") else PROMO["alias"]
            if pred == PROMO["alias"]:
                # Store arbitrary aliases as a single JSON literal for now.
                graph.set((subject, PROMO["aliases"], _as_literal(aliases)))
                break
            graph.set((subject, pred, _as_literal(value)))

    def add_network(
        self,
        graph: Graph,
        name: str,
        iri: Optional[URIRef] = None,
        parent: Optional[Union[str, URIRef]] = None,
        children: Optional[List[str]] = None,
    ) -> URIRef:
        """Add a network/domain to the ontology graph."""
        if iri is None:
            iri = self.mint_iri(PROMO, f"network_{name}")
        graph.add((iri, RDF.type, PROMO["Network"]))
        graph.set((iri, PROMO["name"], _as_literal(name)))
        if parent is not None:
            if isinstance(parent, str):
                parent = self.mint_iri(PROMO, f"network_{parent}")
            graph.set((iri, PROMO["parent"], parent))
        if children:
            for child in children:
                child_iri = self.mint_iri(PROMO, f"network_{child}")
                graph.add((iri, PROMO["child"], child_iri))
                # Also make sure the child resource exists.
                self.add_network(graph, child, iri=child_iri)
        return iri

    def add_domain(
        self,
        graph: Graph,
        name: str,
        iri: Optional[URIRef] = None,
        parent: Optional[Union[str, URIRef]] = None,
        branch: Optional[str] = None,
        tokens: Optional[List[Union[str, URIRef]]] = None,
    ) -> URIRef:
        """Add a domain to the ontology graph with branch and token bindings."""
        if iri is None:
            iri = self.mint_iri(PROMO, f"domain_{name}")
        graph.add((iri, RDF.type, PROMO["Domain"]))
        graph.set((iri, PROMO["name"], _as_literal(name)))
        if parent is not None:
            if isinstance(parent, str):
                parent = URIRef(parent)
            graph.set((iri, PROMO["parent"], parent))
        if branch is not None:
            graph.set((iri, PROMO["branch"], _as_literal(branch)))
        if tokens is not None:
            graph.remove((iri, PROMO["hasToken"], None))
            for token in tokens:
                if isinstance(token, str):
                    token = URIRef(token)
                graph.add((iri, PROMO["hasToken"], token))
        return iri

    def add_variable_dict(self, graph: Graph, var: dict) -> URIRef:
        """Add a variable record to the graph using the ProMo14 schema.

        Supports both the legacy ``variable_class`` (string) and the new
        ``classifications`` (map of axis IRI → axis term IRI) fields.
        If ``classifications`` is present, each entry is stored as a
        ``promo:axisValue`` triple.  If ``variable_class`` / ``type`` is
        present (legacy), it is stored as ``promo:variableClass`` for
        backward compatibility.
        """
        iri = URIRef(var["iri"])
        graph.add((iri, RDF.type, PROMO["Variable"]))
        self._set_literal(graph, iri, PROMO["label"], var.get("label"))
        self._set_literal(graph, iri, PROMO["internalID"], var.get("internal_id"))
        self._set_literal(graph, iri, PROMO["network"], var.get("network"))
        self._set_literal(graph, iri, PROMO["doc"], var.get("doc"))
        self._set_literal(
            graph, iri, PROMO["portVariable"], var.get("port_variable", False)
        )
        self._set_literal(
            graph, iri, PROMO["imported"], var.get("imported", False)
        )

        # Legacy variable_class (string) — kept for backward compat.
        vc = var.get("variable_class") or var.get("type")
        if vc:
            self._set_literal(graph, iri, PROMO["variableClass"], vc)

        # New multi-axis classifications (map of axis IRI → axis term IRI).
        classifications = var.get("classifications")
        if classifications:
            for axis_iri, term_iri in classifications.items():
                graph.add((iri, PROMO["axisValue"], URIRef(term_iri)))

        # Units as an 8-element vector literal.
        units = var.get("units")
        if units:
            graph.set((iri, PROMO["unitVector"], _as_literal(units)))

        for idx_iri in var.get("index_structures", []):
            graph.add((iri, PROMO["indexStructure"], URIRef(idx_iri)))

        for token in var.get("tokens", []):
            graph.add((iri, PROMO["carriesToken"], URIRef(token)))

        if var.get("aliases"):
            self._add_aliases(graph, iri, var["aliases"])

        # Nested equations (dict of E_N -> equation record)
        equations = var.get("equations")
        if equations:
            for eq_id, eq in equations.items():
                eq_iri = eq.get("iri") or str(self.mint_iri(str(PROMO).rstrip("#"), eq_id))
                self.add_equation(graph, URIRef(eq_iri), iri, eq)

        return iri

    def add_index_dict(self, graph: Graph, idx: dict) -> URIRef:
        """Add an index record to the graph using the ProMo14 schema."""
        iri = URIRef(idx["iri"])
        graph.add((iri, RDF.type, PROMO["Index"]))
        self._set_literal(graph, iri, PROMO["label"], idx.get("label"))
        self._set_literal(graph, iri, PROMO["internalID"], idx.get("internal_id"))
        self._set_literal(graph, iri, PROMO["shortName"], idx.get("short_name"))
        self._set_literal(graph, iri, PROMO["network"], idx.get("network"))
        self._set_literal(graph, iri, PROMO["indexClass"], idx.get("index_class"))
        self._set_literal(graph, iri, PROMO["doc"], idx.get("doc"))

        if idx.get("token"):
            graph.set((iri, PROMO["token"], URIRef(idx["token"])))

        if idx.get("aliases"):
            self._add_aliases(graph, iri, idx["aliases"])

        return iri

    def add_token(self, graph: Graph, iri: URIRef, label: str, parent: Optional[URIRef] = None) -> URIRef:
        """Add a token type to the graph."""
        graph.add((iri, RDF.type, PROMO["Token"]))
        self._set_literal(graph, iri, RDFS.label, label)
        if parent is not None:
            graph.set((iri, PROMO["parent"], parent))
        return iri

    # ------------------------------------------------------------------
    # Classification axes, entity types, connection rules, equation classes
    # ------------------------------------------------------------------

    def add_classification_axis(
        self,
        graph: Graph,
        iri: URIRef,
        domain: Union[str, URIRef],
        name: str,
        parent: Optional[Union[str, URIRef]] = None,
    ) -> URIRef:
        """Add a classification axis definition to the graph."""
        graph.add((iri, RDF.type, PROMO["ClassificationAxis"]))
        self._set_literal(graph, iri, PROMO["axisName"], name)
        if isinstance(domain, str):
            domain = URIRef(domain)
        graph.set((iri, PROMO["hasDomain"], domain))
        if parent is not None:
            if isinstance(parent, str):
                parent = URIRef(parent)
            graph.set((iri, PROMO["parent"], parent))
        return iri

    def add_axis_term(
        self,
        graph: Graph,
        iri: URIRef,
        axis: Union[str, URIRef],
        label: str,
        parent: Optional[Union[str, URIRef]] = None,
    ) -> URIRef:
        """Add a term to a classification axis hierarchy."""
        graph.add((iri, RDF.type, PROMO["AxisTerm"]))
        self._set_literal(graph, iri, PROMO["label"], label)
        if isinstance(axis, str):
            axis = URIRef(axis)
        graph.set((iri, PROMO["hasAxis"], axis))
        if parent is not None:
            if isinstance(parent, str):
                parent = URIRef(parent)
            graph.set((iri, PROMO["parent"], parent))
        return iri

    def add_scale_dimension(
        self,
        graph: Graph,
        iri: URIRef,
        name: str,
        domain: Union[str, URIRef],
        parent: Optional[Union[str, URIRef]] = None,
    ) -> URIRef:
        """Add a scale dimension (time scale, length scale, user-defined)."""
        graph.add((iri, RDF.type, PROMO["ScaleDimension"]))
        self._set_literal(graph, iri, PROMO["scaleName"], name)
        if isinstance(domain, str):
            domain = URIRef(domain)
        graph.set((iri, PROMO["hasDomain"], domain))
        if parent is not None:
            if isinstance(parent, str):
                parent = URIRef(parent)
            graph.set((iri, PROMO["parent"], parent))
        return iri

    def add_scale_value(
        self,
        graph: Graph,
        iri: URIRef,
        dimension: Union[str, URIRef],
        label: str,
        parent: Optional[Union[str, URIRef]] = None,
    ) -> URIRef:
        """Add a value to a scale dimension's hierarchical tree."""
        graph.add((iri, RDF.type, PROMO["ScaleValue"]))
        self._set_literal(graph, iri, PROMO["scaleValueLabel"], label)
        if isinstance(dimension, str):
            dimension = URIRef(dimension)
        graph.set((iri, PROMO["hasScale"], dimension))
        if parent is not None:
            if isinstance(parent, str):
                parent = URIRef(parent)
            graph.set((iri, PROMO["parent"], parent))
        return iri

    def add_entity_type(
        self,
        graph: Graph,
        iri: URIRef,
        label: str,
        temporal_type: str,
        branch: str,
        spatial_type: Optional[str] = None,
        spatial_size: Optional[str] = None,
        description: str = "",
    ) -> URIRef:
        """Add an entity type (CWA 17960 taxonomy) to the graph."""
        graph.add((iri, RDF.type, PROMO["EntityType"]))
        self._set_literal(graph, iri, PROMO["label"], label)
        self._set_literal(graph, iri, PROMO["temporalType"], temporal_type)
        self._set_literal(graph, iri, PROMO["branch"], branch)
        if spatial_type is not None:
            self._set_literal(graph, iri, PROMO["spatialType"], spatial_type)
        if spatial_size is not None:
            self._set_literal(graph, iri, PROMO["spatialSize"], spatial_size)
        if description:
            self._set_literal(graph, iri, PROMO["doc"], description)
        return iri

    def add_connection_rule(
        self,
        graph: Graph,
        iri: URIRef,
        rule_type: str,
        direction: Optional[str] = None,
        source_domain: Optional[Union[str, URIRef]] = None,
        target_domain: Optional[Union[str, URIRef]] = None,
        shared_tokens: Optional[List[Union[str, URIRef]]] = None,
        description: str = "",
    ) -> URIRef:
        """Add a connection rule definition to the graph."""
        graph.add((iri, RDF.type, PROMO["ConnectionRule"]))
        self._set_literal(graph, iri, PROMO["ruleType"], rule_type)
        if direction is not None:
            self._set_literal(graph, iri, PROMO["direction"], direction)
        if source_domain is not None:
            if isinstance(source_domain, str):
                source_domain = URIRef(source_domain)
            graph.set((iri, PROMO["sourceDomain"], source_domain))
        if target_domain is not None:
            if isinstance(target_domain, str):
                target_domain = URIRef(target_domain)
            graph.set((iri, PROMO["targetDomain"], target_domain))
        if shared_tokens is not None:
            graph.remove((iri, PROMO["sharedTokens"], None))
            for token in shared_tokens:
                if isinstance(token, str):
                    token = URIRef(token)
                graph.add((iri, PROMO["sharedTokens"], token))
        if description:
            self._set_literal(graph, iri, PROMO["doc"], description)
        return iri

    def add_equation_class(
        self,
        graph: Graph,
        iri: URIRef,
        label: str,
        parent: Optional[Union[str, URIRef]] = None,
    ) -> URIRef:
        """Add an equation class node to the hierarchy."""
        graph.add((iri, RDF.type, PROMO["EquationClass"]))
        self._set_literal(graph, iri, PROMO["label"], label)
        if parent is not None:
            if isinstance(parent, str):
                parent = URIRef(parent)
            graph.set((iri, PROMO["parent"], parent))
        return iri

    def add_equation(
        self,
        graph: Graph,
        eq_iri: URIRef,
        lhs_var: URIRef,
        eq: dict,
    ) -> URIRef:
        """Add an equation (LHS variable + RHS expression) to the graph.

        Links the equation to its parent variable via ``promo:hasEquation``.
        """
        graph.add((eq_iri, RDF.type, PROMO["Equation"]))
        graph.add((lhs_var, PROMO["hasEquation"], eq_iri))
        graph.set((eq_iri, PROMO["lhs"], lhs_var))
        self._set_literal(graph, eq_iri, PROMO["internalID"], eq.get("internal_id"))
        self._set_literal(graph, eq_iri, PROMO["rhs"], eq.get("rhs"))
        self._set_literal(graph, eq_iri, PROMO["rhsLatex"], eq.get("rhs_latex"))
        self._set_literal(graph, eq_iri, PROMO["equationClass"], eq.get("equation_class"))
        self._set_literal(graph, eq_iri, PROMO["network"], eq.get("network"))
        self._set_literal(graph, eq_iri, PROMO["doc"], eq.get("doc"))
        if eq.get("incidence_list"):
            graph.set((eq_iri, PROMO["incidenceList"], _as_literal(eq["incidence_list"])))
        if eq.get("created"):
            self._set_literal(graph, eq_iri, PROMO["created"], eq["created"])
        if eq.get("modified"):
            self._set_literal(graph, eq_iri, PROMO["modified"], eq["modified"])
        return eq_iri

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def as_trig(self) -> str:
        """Return the whole dataset as a TriG string."""
        return self.dataset.serialize(format="trig")
