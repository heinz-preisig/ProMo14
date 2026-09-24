"""Shared RDF graph store for the ProMo suite.

``RdfStore`` wraps an ``rdflib.Dataset`` and provides the low-level storage
that the ontology editor, equation editor, and modeller share.  It is
intentionally thin: it loads/saves named graphs from ``PROMO_DATA_DIR`` and
offers a few helpers for minting IRIs.

The store uses the ProMo vocabulary (``https://w3id.org/promo#``).  When no
``ontology.trig`` exists, a default two-branch ontology is seeded.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import rdflib
from rdflib import Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

from .config import get_data_dir

PROMO = Namespace("https://w3id.org/promo#")
PROMOLG = Namespace("https://w3id.org/promo/language#")
QUDT = Namespace("http://qudt.org/schema/qudt/")

# Artefact-type markers (docs/versioning-and-session-design.md): every
# artefact graph carries ``<graphIRI> a promo:<Type>`` so the catalogue
# can classify it.  ``promo:Version`` marks frozen graphs separately.
ARTEFACT_TYPES = ("Ontology", "Library", "Assignment", "Model", "Glass",
                  "Species")

# Universal constants seeded into every ontology (ADR-008): pre-bound
# value slots, class ``constant``, network ``root`` — visible from every
# expression network via ancestor-chain resolution.  ``value`` is the
# code-surface literal; ``latex`` is the document-surface alias.
#   (fragment, label, value, latex alias)
SEED_CONSTANTS = (
    ("const_zero", "zero", "0", "0"),
    ("const_one", "one", "1", "1"),
    ("const_half", "half", "0.5", r"\frac{1}{2}"),
)

# Seed-floor revision stamped as ``promo:seedFloor`` on every graph the
# migratable seed sequence (``apply_seed_floor``) has run against.
# Bump when any ``_seed_*`` step's content changes so the catalogue can
# flag draft ontology forks that predate the current floor.
SEED_FLOOR = "2026-09"

# Legacy prefixes used in old TriG files.
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

# Conforming equation ids: ``E_1`` … ``E_999999``.  Anything else
# (notably legacy ``E_<epoch-ms>`` ids minted by the equation editor)
# is renumbered by ``_migrate_equation_ids``.
_EQUATION_ID_RE = re.compile(r"^E_(\d{1,6})$")

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
#   promo:dimensionKind    — "structural" | "content"  (structural dims compose
#                          entity types; content dims bind per model-node
#                          instance, e.g. phase as constitutive selector)
#   promo:hasDomain        — links a scale dimension to the domain where it is defined
#   promo:ScaleValue       — a value in a scale dimension's hierarchical tree
#   promo:hasScale         — links a scale value to its dimension
#   promo:scaleValueLabel  — label for a scale value (e.g. "microscopic", "macroscopic")
#
# Tokens
#   promo:Token            — a token type (what lives in a domain)
#   promo:tokenKind        — "conserved" | "reference"  (conserved tokens
#                          accumulate and ride token-flow arcs; reference
#                          tokens expose variable access on reference arcs)
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
    ONTOLOGY_GRAPH_IRI = URIRef("https://w3id.org/promo/ontology")

    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        if data_dir is None:
            self.data_dir = get_data_dir()
        else:
            self.data_dir = Path(data_dir)
        self.dataset = Dataset()
        self._id_counters: Dict[str, int] = {}
        # Persistence state: True when in-memory triples diverge from the
        # last saved TriG file.  Set by the mutation middleware in main.py
        # (and directly by store-level writes); cleared by save().
        self.dirty: bool = False
        self.last_saved: Optional[datetime.datetime] = None

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
        ontology graph is still empty, the default ontology is seeded.
        """
        ontology_path = self.data_dir / "ontology.trig"
        legacy_layout = False
        if ontology_path.exists():
            try:
                self.dataset.parse(str(ontology_path), format="trig")
            except Exception:
                pass
            else:
                # Legacy single-file layout: ontology.trig held the
                # whole dataset.  At this point the dataset contains
                # only that file's graphs — any non-empty graph outside
                # the ontology line (the ontology plus its versionOf
                # children) means a split is needed.
                line = {self.ONTOLOGY_GRAPH_IRI} | {
                    g.identifier for g in self.dataset.graphs()
                    if (g.identifier, PROMO["versionOf"],
                        self.ONTOLOGY_GRAPH_IRI) in g}
                legacy_layout = any(
                    len(g) and g.identifier not in line
                    for g in self.dataset.graphs())

        if not len(self.ontology_graph):
            self.seed_default_ontology()
        else:
            # Idempotent marker migration: existing ontology.trig files
            # predate artefact-type markers.
            g = self.ontology_graph
            marker = (g.identifier, RDF.type, PROMO["Ontology"])
            if marker not in g:
                g.add(marker)
            # Idempotent seed-floor migration: constants (ADR-008),
            # scale regimes, transport mechanisms + arc sub-indices
            # (§16) and §20 capabilities postdate existing
            # ontology.trig files.  The core graph is suite-owned, so
            # the floor is applied automatically; forks opt in via
            # POST /api/ontology/apply-seed-floor (hub ticket #7).
            self.apply_seed_floor(g, str(self.ONTOLOGY_GRAPH_IRI))

        # Load any additional var/expr named graphs that are already in the
        # data directory, but do not replace the editable ontology graph.
        for path in sorted(self.data_dir.glob("*.trig")):
            if path.name == "ontology.trig":
                continue
            try:
                self.dataset.parse(str(path), format="trig")
            except Exception:
                continue

        # Idempotent data migration: legacy ``E_<epoch-ms>`` equation
        # ids → sequential ``E_n`` (readable in the printed document).
        self._migrate_equation_ids()
        # …and equation IRIs minted under the promo# vocabulary
        # namespace are rehomed into their graph's own namespace.
        self._migrate_equation_iris()

        if legacy_layout:
            # Split the legacy single-file store into per-line files
            # now — before any edit lands — so the tracked files match
            # the per-artefact layout (hub ticket #4).
            self.save()

    def _migrate_equation_ids(self) -> None:
        """Renumber non-conforming equation ``internalID`` literals.

        Only the literal changes — equation IRIs stay stable.  Ids are
        unique dataset-wide (the printed document hyperlinks by number),
        so the scan covers every named graph.
        """
        used: set = set()
        legacy: List[Any] = []
        for g in self.dataset.contexts():
            for s in g.subjects(RDF.type, PROMO["Equation"]):
                raw = g.value(s, PROMO["internalID"])
                m = _EQUATION_ID_RE.match(str(raw) if raw is not None else "")
                if m:
                    used.add(int(m.group(1)))
                else:
                    legacy.append((g, s))
        next_free = 1
        for g, s in sorted(legacy, key=lambda t: str(t[1])):
            while next_free in used:
                next_free += 1
            g.set((s, PROMO["internalID"], Literal(f"E_{next_free}")))
            used.add(next_free)
        if legacy:
            self.mark_dirty()

    def _migrate_equation_iris(self) -> None:
        """Rehome equation IRIs minted under ``promo#`` into their
        graph's own namespace (``{graphIRI}#``).

        ``promo#`` is the vocabulary namespace — instance IRIs belong
        to the artefact graph.  Besides the discipline violation, a
        ``promo#E_x`` subject in two graphs is the *same* resource, so
        rehoming also fixes cross-artefact identity collisions.  The
        fragment prefers the (already renumbered) ``internalID``;
        object references (``promo:hasEquation``, assignment
        sequences) are rewritten dataset-wide."""
        promo_ns = str(PROMO)
        # old IRI -> {owning graph identifier: new IRI}
        moves: Dict[str, Dict[URIRef, URIRef]] = {}
        for g in self.dataset.contexts():
            base = str(g.identifier)
            for s in list(g.subjects(RDF.type, PROMO["Equation"])):
                if not str(s).startswith(promo_ns):
                    continue
                frag = str(s)[len(promo_ns):]
                iid = g.value(s, PROMO["internalID"])
                if iid is not None and _EQUATION_ID_RE.match(str(iid)):
                    frag = str(iid)
                new = URIRef(f"{base}#{frag}")
                n = 1
                while (new, None, None) in g and new != s:
                    new = URIRef(f"{base}#{frag}_{n}")
                    n += 1
                moves.setdefault(str(s), {})[g.identifier] = new
                for _s, p, o in list(g.triples((s, None, None))):
                    g.remove((_s, p, o))
                    g.add((new, p, o))
        if not moves:
            return
        # Rewrite object references dataset-wide: prefer the rehome in
        # the referencing graph itself, else the unique/first target.
        for g in self.dataset.contexts():
            for s, p, o in list(g.triples((None, None, None))):
                if isinstance(o, URIRef) and str(o) in moves:
                    targets = moves[str(o)]
                    new = targets.get(g.identifier)
                    if new is None:
                        new = targets[sorted(targets, key=str)[0]]
                    g.remove((s, p, o))
                    g.add((s, p, new))
        self.mark_dirty()

    def _line_key(self, g: Graph) -> URIRef:
        """The artefact line a graph belongs to: itself, or its
        ``versionOf`` target for frozen version graphs."""
        base = g.value(g.identifier, PROMO["versionOf"])
        return URIRef(str(base)) if base is not None else g.identifier

    @staticmethod
    def _line_filename(line_iri: URIRef, taken: set) -> str:
        """Filesystem name for a line: the IRI's last segment, with a
        deterministic hash suffix when two lines slug alike."""
        text = str(line_iri)
        seg = text.rstrip("/").rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", seg).strip("_") \
            or "graph"
        name = f"{slug}.trig"
        if name in taken:
            digest = hashlib.sha1(text.encode()).hexdigest()[:6]
            name = f"{slug}-{digest}.trig"
        taken.add(name)
        return name

    def save(self, filename: Optional[str] = None) -> Path:
        """Serialise the dataset — one ``.trig`` per artefact line.

        A line file holds the draft graph plus its frozen version
        graphs ("the file is the history"); the core ontology line
        keeps the tracked ``ontology.trig`` name.  ``filename``
        selects the legacy whole-dataset single-file form (explicit
        export only).  Returns the data directory (fan-out) or the
        written file (single-file).
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if filename:
            path = self.data_dir / filename
            self.dataset.serialize(str(path), format="trig")
            self.dirty = False
            self.last_saved = datetime.datetime.now(datetime.timezone.utc)
            return path

        default_id = self.dataset.default_graph.identifier
        lines: Dict[URIRef, List[Graph]] = {}
        for g in self.dataset.graphs():
            if not len(g) or g.identifier == default_id:
                continue
            lines.setdefault(self._line_key(g), []).append(g)

        # Default-graph triples (e.g. a hand-edited file's unnamed
        # block) ride along in the ontology line file so they
        # round-trip back into the default graph.
        default = self.dataset.default_graph
        default_home = (
            self.ONTOLOGY_GRAPH_IRI if self.ONTOLOGY_GRAPH_IRI in lines
            else (sorted(lines, key=str)[0] if lines else None))

        written: set = set()
        for line_iri in sorted(lines, key=str):
            out = Dataset()
            for pfx, ns in self.dataset.namespaces():
                out.bind(pfx, ns)
            for g in lines[line_iri]:
                og = out.graph(g.identifier)
                for t in g:
                    og.add(t)
            if len(default) and line_iri == default_home:
                for t in default:
                    out.default_graph.add(t)
            name = self._line_filename(line_iri, written)
            out.serialize(str(self.data_dir / name), format="trig")
            written.add(name)

        # Remove files whose line no longer exists (renamed IRIs).
        if written:
            for stale in self.data_dir.glob("*.trig"):
                if stale.name not in written:
                    stale.unlink()

        self.dirty = False
        self.last_saved = datetime.datetime.now(datetime.timezone.utc)
        return self.data_dir

    def mark_dirty(self) -> None:
        """Flag the dataset as having unsaved changes."""
        self.dirty = True

    def seed_default_ontology(self) -> None:
        """Seed the default ProMo14 ontology (two-branch domain tree,
        tokens, classification axes, entity types, connection rules).

        Called when no ``ontology.trig`` exists.
        """
        g = self.ontology_graph
        # Namespace discipline (contract D1): promo# is vocabulary only;
        # instances mint under the owning graph's namespace.
        base = str(self.ONTOLOGY_GRAPH_IRI)

        # --- Domain tree: root + two branches ---
        # The root domain is the global scope: tokens and scale
        # dimensions bound to it are inherited by every branch.
        root_iri = self.mint_iri(base, "domain_root")
        self.add_domain(g, "root", iri=root_iri)

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
        # Physical branch: three axes, one question each
        # (design discussion 2026-09-24):
        #   determination — where is the value determined? interior|boundary
        #   function      — what does the variable physically do?
        #   variability   — is the value given or solved?
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
                      ("derived", None),
                      ("port", None),
                  ])
        seed_axis("function_physical", "function", "function", phys_iri, [
            ("state", None),
            ("fundamental-state", "state"),
            ("secondary-state", "state"),
            ("effort", None),
            ("flow", None),
            ("frame", None),
            ("reaction", None),
        ])
        seed_axis("variability_physical", "variability",
                  "variability", phys_iri, [
                      ("constant", None),
                      ("parameter", None),
                      ("variable", None),
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

    # ------------------------------------------------------------------
    # Named graph helpers
    # ------------------------------------------------------------------

    @property
    def ontology_graph(self) -> Graph:
        """Return the default editable ontology named graph."""
        return self.dataset.graph(self.ONTOLOGY_GRAPH_IRI)

    # ------------------------------------------------------------------
    # Ancestor chains and effective tokens (shared read helpers)
    # ------------------------------------------------------------------

    def ancestor_chain(self, graph: Graph, iri: URIRef) -> List[URIRef]:
        """Return ``[iri, parent, grandparent, ...]`` walking ``promo:parent``.

        Terminates on a missing parent or a cycle (silently truncated).
        """
        chain: List[URIRef] = []
        seen: set = set()
        current = iri
        while current is not None and current not in seen:
            seen.add(current)
            chain.append(current)
            current = graph.value(current, PROMO["parent"])
        return chain

    def effective_tokens(self, graph: Graph, domain_iri: URIRef) -> List[URIRef]:
        """Tokens active in a domain: own ``hasToken`` plus all ancestors'.

        Order preserved, deduplicated (own tokens first, then inherited
        nearest-ancestor-first).
        """
        tokens: List[URIRef] = []
        for d in self.ancestor_chain(graph, domain_iri):
            for t in graph.objects(d, PROMO["hasToken"]):
                if t not in tokens:
                    tokens.append(t)
        return tokens

    def tokens_comparable(self, graph: Graph, a: URIRef, b: URIRef) -> bool:
        """True iff ``a`` and ``b`` lie on the same root-to-leaf token path.

        Comparability = one is ancestor-or-self of the other (contract:
        binding a parent activates its refinements; a subtoken alone
        activates only that refinement).
        """
        return (a == b
                or a in self.ancestor_chain(graph, b)
                or b in self.ancestor_chain(graph, a))

    def declare_vocabulary(self, graph: Graph) -> int:
        """Declare every ``promo#`` term used in ``graph``.

        Predicates become ``rdf:Property``, ``rdf:type`` objects become
        ``rdfs:Class`` — RDF/RDFS level only, no OWL.  Self-maintaining:
        the vocabulary is whatever the data uses.  Returns the number of
        declarations added (idempotent).
        """
        added = 0
        for p in list(graph.predicates()):
            if (str(p).startswith(str(PROMO))
                    and (p, RDF.type, RDF.Property) not in graph):
                graph.add((p, RDF.type, RDF.Property))
                added += 1
        for c in list(graph.objects(None, RDF.type)):
            if (isinstance(c, URIRef) and str(c).startswith(str(PROMO))
                    and (c, RDF.type, RDFS.Class) not in graph):
                graph.add((c, RDF.type, RDFS.Class))
                added += 1
        # usesOntology / generatedFrom are declared unconditionally:
        # they are consumed by artefact graphs (var/expr, models,
        # assignments, generated code) pointing at a frozen version, so
        # they never appear inside the ontology itself.  The artefact
        # type classes are declared likewise — they mark graph IRIs,
        # which live outside the ontology's own instance data.
        for term in (PROMO["usesOntology"], PROMO["usesSpecies"],
                     PROMO["generatedFrom"],
                     PROMO["versionOf"], PROMO["versionInfo"],
                     PROMO["publishedOn"], PROMO["seedFloor"],
                     PROMO["valueCell"], PROMO["atIndexElement"],
                     PROMO["coordinate"]):
            if (term, RDF.type, RDF.Property) not in graph:
                graph.add((term, RDF.type, RDF.Property))
                added += 1
        for term in ([PROMO["Version"], PROMO["ValueCell"]]
                     + [PROMO[t] for t in ARTEFACT_TYPES]):
            if (term, RDF.type, RDFS.Class) not in graph:
                graph.add((term, RDF.type, RDFS.Class))
                added += 1
        return added

    def freeze_version(
        self,
        version: str,
        graph_iri: Optional[Union[str, URIRef]] = None,
    ) -> URIRef:
        """Freeze a named graph as an immutable version.

        Copies every triple of the source graph (default: the working
        ontology) into a new named graph ``{source}/{version}`` and
        stamps version metadata on the version IRI.  Applies to any
        artefact graph — the var/expr library is a vocabulary artefact
        under the same ADR-006 discipline as the ontology.  Raises
        ``ValueError`` if the source is empty or the version graph
        already exists — published versions are immutable.
        Returns the version graph IRI.
        """
        source = (URIRef(graph_iri) if graph_iri is not None
                  else URIRef(self.ONTOLOGY_GRAPH_IRI))
        src_graph = self.dataset.graph(source)
        if not len(src_graph):
            raise ValueError(f"nothing to freeze: {source} is empty")
        version_iri = URIRef(f"{source}/{version}")
        vg = self.dataset.graph(version_iri)
        if len(vg):
            raise ValueError(f"version already published: {version_iri}")
        for triple in src_graph:
            vg.add(triple)
        vg.add((version_iri, RDF.type, PROMO["Version"]))
        # The version graph carries the source's artefact-type marker(s)
        # on its own IRI so the catalogue can classify frozen graphs.
        for t in src_graph.objects(source, RDF.type):
            if isinstance(t, URIRef) and str(t).startswith(str(PROMO)):
                vg.add((version_iri, RDF.type, t))
        vg.add((version_iri, PROMO["versionOf"], source))
        vg.add((version_iri, PROMO["versionInfo"], Literal(version)))
        vg.add((version_iri, PROMO["publishedOn"], Literal(
            datetime.date.today().isoformat(), datatype=XSD.date)))
        # The frozen artefact is self-describing.
        self.declare_vocabulary(vg)
        return version_iri

    def graph(self, iri: Union[str, URIRef]) -> Graph:
        """Return or create a named graph."""
        if isinstance(iri, str):
            iri = URIRef(iri)
        return self.dataset.graph(iri)

    def create_artefact_graph(
        self,
        iri: Union[str, URIRef],
        artefact_type: str,
        label: Optional[str] = None,
        uses: Optional[List[Union[str, URIRef]]] = None,
        uses_species: Optional[List[Union[str, URIRef]]] = None,
    ) -> URIRef:
        """Create an empty artefact graph with type marker and pins.

        ``artefact_type`` is one of ``ARTEFACT_TYPES`` (case-insensitive).
        ``uses`` stamps ``promo:usesOntology`` pins — the ontology set the
        artefact is checked against (R2).  ``uses_species`` stamps
        ``promo:usesSpecies`` pins — the §20 reaction scheme the artefact
        draws its species vocabulary from.  Raises ``ValueError`` if the
        graph already exists or the type is unknown.
        """
        if artefact_type.lower() not in {t.lower() for t in ARTEFACT_TYPES}:
            raise ValueError(
                f"unknown artefact type: {artefact_type} "
                f"(expected one of {ARTEFACT_TYPES})")
        iri = URIRef(str(iri))
        g = self.dataset.graph(iri)
        if len(g):
            raise ValueError(f"graph already exists: {iri}")
        g.add((iri, RDF.type,
               PROMO[artefact_type.lower().capitalize()]))
        if label:
            g.add((iri, RDFS.label, Literal(label)))
        for pin in uses or []:
            g.add((iri, PROMO["usesOntology"], URIRef(str(pin))))
        for pin in uses_species or []:
            g.add((iri, PROMO["usesSpecies"], URIRef(str(pin))))
        self.declare_vocabulary(g)
        return iri

    def fork_graph(
        self,
        source_iri: Union[str, URIRef],
        new_iri: Union[str, URIRef],
        label: Optional[str] = None,
    ) -> URIRef:
        """Fork a graph into a new artefact line.

        Copies every triple, re-homing instance IRIs minted under the
        source graph's namespace (``{source}#…``) to the new graph's
        namespace (``{new}#…``) — required by D1: shared IRIs would merge
        under union semantics.  The source's self-description triples
        (artefact type, version stamps, pins) are not copied; the fork is
        stamped fresh with the source's artefact type, its pins, a
        ``promo:versionOf`` provenance link, and an optional label.
        Raises ``ValueError`` if the source is empty or the target
        exists.
        """
        source = URIRef(str(source_iri))
        new = URIRef(str(new_iri))
        src = self.dataset.graph(source)
        if not len(src):
            raise ValueError(f"nothing to fork: {source} is empty")
        dst = self.dataset.graph(new)
        if len(dst):
            raise ValueError(f"graph already exists: {new}")

        old_ns = f"{source}#"
        new_ns = f"{new}#"

        def rehome(term):
            if not isinstance(term, URIRef):
                return term
            if term == source:
                return new
            if str(term).startswith(old_ns):
                return URIRef(new_ns + str(term)[len(old_ns):])
            return term

        for s, p, o in src:
            if s == source:
                continue  # source self-description: re-stamped below
            dst.add((rehome(s), p, rehome(o)))

        # Fresh self-description: artefact type(s) minus Version, pins,
        # provenance, label.
        for t in src.objects(source, RDF.type):
            if (isinstance(t, URIRef) and str(t).startswith(str(PROMO))
                    and t != PROMO["Version"]):
                dst.add((new, RDF.type, t))
        for pin in src.objects(source, PROMO["usesOntology"]):
            dst.add((new, PROMO["usesOntology"], pin))
        for pin in src.objects(source, PROMO["usesSpecies"]):
            dst.add((new, PROMO["usesSpecies"], pin))
        # The seed-floor stamp is content-accurate on a fork: the copy
        # carries the same floor content as its source (re-homed), so
        # it inherits the source's staleness state — a fork of a stale
        # ontology stays stale, a fork of a current one stays current.
        floor = src.value(source, PROMO["seedFloor"])
        if floor is not None:
            dst.add((new, PROMO["seedFloor"], floor))
        dst.add((new, PROMO["versionOf"], source))
        if label:
            dst.add((new, RDFS.label, Literal(label)))
        self.declare_vocabulary(dst)
        return new

    def resolution_scope(
        self, graph_iri: Union[str, URIRef]
    ) -> List[URIRef]:
        """An artefact's resolution context: itself plus the transitive
        ``promo:usesOntology`` closure (R2/R4).  Cycle-safe; order is the
        artefact first, then pins breadth-first."""
        start = URIRef(str(graph_iri))
        scope: List[URIRef] = []
        seen: set = set()
        stack = [start]
        while stack:
            iri = stack.pop()
            if iri in seen:
                continue
            seen.add(iri)
            scope.append(iri)
            g = self.dataset.graph(iri)
            for pin in g.objects(iri, PROMO["usesOntology"]):
                if isinstance(pin, URIRef):
                    stack.append(pin)
        return scope

    # ------------------------------------------------------------------
    # Frozen-graph guard (R5: published versions are read-only)
    # ------------------------------------------------------------------

    @staticmethod
    def is_frozen(graph: Graph) -> bool:
        """True iff ``graph`` is a published version (immutable)."""
        return (graph.identifier, RDF.type, PROMO["Version"]) in graph

    def assert_editable(self, graph: Graph) -> None:
        """Raise ``ValueError`` if ``graph`` is a frozen version.

        Enforcement point for R5 — call before any mutation once graph
        selection (``?graph=``) lets requests reach arbitrary graphs.
        """
        if self.is_frozen(graph):
            raise ValueError(
                f"frozen graph is read-only: {graph.identifier}")

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
            iri = self.mint_iri(graph.identifier, f"network_{name}")
        graph.add((iri, RDF.type, PROMO["Network"]))
        graph.set((iri, PROMO["name"], _as_literal(name)))
        if parent is not None:
            if isinstance(parent, str):
                parent = self.mint_iri(graph.identifier, f"network_{parent}")
            graph.set((iri, PROMO["parent"], parent))
        if children:
            for child in children:
                child_iri = self.mint_iri(graph.identifier, f"network_{child}")
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
            iri = self.mint_iri(graph.identifier, f"domain_{name}")
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
        self._set_literal(graph, iri, RDFS.label, var.get("label"))
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

        # Pre-bound value slot (universal constants; ADR-008).
        self._set_literal(graph, iri, PROMO["value"], var.get("value"))

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

        # Aliases use replace semantics: the direct predicates are cleared
        # first so an alias removed by the caller does not linger.
        if var.get("aliases") is not None:
            for key in ("internal_code", "latex", "matlab"):
                graph.remove((iri, PROMO[key], None))
            self._add_aliases(graph, iri, var["aliases"])

        # Nested equations (dict of E_N -> equation record)
        equations = var.get("equations")
        if equations:
            for eq_id, eq in equations.items():
                eq_iri = eq.get("iri") or str(self.mint_iri(graph.identifier, eq_id))
                self.add_equation(graph, URIRef(eq_iri), iri, eq)

        return iri

    def add_index_dict(self, graph: Graph, idx: dict) -> URIRef:
        """Add an index record to the graph using the ProMo14 schema."""
        iri = URIRef(idx["iri"])
        graph.add((iri, RDF.type, PROMO["Index"]))
        self._set_literal(graph, iri, RDFS.label, idx.get("label"))
        self._set_literal(graph, iri, PROMO["internalID"], idx.get("internal_id"))
        self._set_literal(graph, iri, PROMO["shortName"], idx.get("short_name"))
        self._set_literal(graph, iri, PROMO["network"], idx.get("network"))
        self._set_literal(graph, iri, PROMO["indexClass"], idx.get("index_class"))
        self._set_literal(graph, iri, PROMO["doc"], idx.get("doc"))

        if idx.get("token"):
            graph.set((iri, PROMO["token"], URIRef(idx["token"])))

        # Sub-index partitioning (§16): promo:subIndexOf points at the
        # base index, promo:selector at the entity type/classification
        # term defining membership.  Instantiation resolves the element
        # set; the checker treats a sub-index as a plain distinct index.
        if idx.get("sub_index_of"):
            graph.set((iri, PROMO["subIndexOf"], URIRef(idx["sub_index_of"])))
        if idx.get("selector"):
            graph.set((iri, PROMO["selector"], URIRef(idx["selector"])))

        if idx.get("aliases"):
            self._add_aliases(graph, iri, idx["aliases"])

        return iri

    # ------------------------------------------------------------------
    # Value cells — the (reaction, species)-keyed value channel (§20 ν)
    # ------------------------------------------------------------------

    @staticmethod
    def _coord_key(elements: List[str]) -> str:
        """Serialise one cell coordinate: element IRIs in index order,
        ``|``-joined (IRIs never contain ``|``)."""
        return "|".join(elements)

    def set_value_cells(
        self,
        graph: Graph,
        variable: Union[str, URIRef],
        cells: Dict[str, Any],
    ) -> None:
        """Replace a variable's value-cell table in ``graph``.

        ``cells`` maps a coordinate key — ``|``-joined index-element
        IRIs in the variable's ``indexStructure`` order — to a scalar
        value.  Each entry becomes a ``promo:ValueCell`` resource under
        the artefact's IRI space: the variable links to it via
        ``promo:valueCell``; the cell carries ``promo:value``,
        ``promo:coordinate`` (the ordered element list as a JSON
        literal — the authoritative axis order) and one
        ``promo:atIndexElement`` per element for graph navigation.
        Existing cells of the variable are wiped first (replace
        semantics, like ``add_variable_dict`` aliases).
        """
        var = URIRef(str(variable))
        for cell in list(graph.objects(var, PROMO["valueCell"])):
            graph.remove((cell, None, None))
        graph.remove((var, PROMO["valueCell"], None))
        for key, value in cells.items():
            elements = [e for e in str(key).split("|") if e]
            digest = hashlib.sha1(
                f"{var}|{key}".encode()).hexdigest()[:12]
            cell = self.mint_iri(graph.identifier, f"cell_{digest}")
            graph.add((cell, RDF.type, PROMO["ValueCell"]))
            graph.add((var, PROMO["valueCell"], cell))
            graph.set((cell, PROMO["coordinate"],
                       Literal(json.dumps(elements))))
            for el in elements:
                graph.add((cell, PROMO["atIndexElement"], URIRef(el)))
            graph.set((cell, PROMO["value"], _as_literal(value)))

    def value_cells(
        self,
        graph: Graph,
        variable: Union[str, URIRef],
    ) -> Dict[str, Any]:
        """Read a variable's value-cell table back as
        ``{coordinate_key: value}`` — the inverse of
        ``set_value_cells``.  The key is rebuilt from the cell's
        ``promo:coordinate`` literal (ordered); cells without one fall
        back to their sorted ``atIndexElement`` set."""
        var = URIRef(str(variable))
        out: Dict[str, Any] = {}
        for cell in graph.objects(var, PROMO["valueCell"]):
            coord = graph.value(cell, PROMO["coordinate"])
            if coord is not None:
                try:
                    elements = json.loads(str(coord))
                except ValueError:
                    elements = []
            else:
                elements = sorted(
                    str(e) for e in
                    graph.objects(cell, PROMO["atIndexElement"]))
            val = graph.value(cell, PROMO["value"])
            if val is not None:
                out[self._coord_key(elements)] = val.toPython()
        return out

    def add_token(self, graph: Graph, iri: URIRef, label: str, parent: Optional[URIRef] = None, kind: Optional[str] = None) -> URIRef:
        """Add a token type to the graph.

        ``kind`` is ``"conserved"`` or ``"reference"`` — conserved tokens
        accumulate in capacities and ride token-flow arcs; reference
        tokens expose variable access on reference arcs.
        """
        graph.add((iri, RDF.type, PROMO["Token"]))
        self._set_literal(graph, iri, RDFS.label, label)
        if kind is not None:
            self._set_literal(graph, iri, PROMO["tokenKind"], kind)
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
        self._set_literal(graph, iri, PROMO["name"], name)
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
        self._set_literal(graph, iri, RDFS.label, label)
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
        kind: Optional[str] = None,
    ) -> URIRef:
        """Add a scale dimension (time scale, length scale, user-defined).

        ``kind`` is ``"structural"`` or ``"content"`` — structural
        dimensions compose entity types; content dimensions (e.g. phase)
        bind per model-node instance and never compose entity types.
        """
        graph.add((iri, RDF.type, PROMO["ScaleDimension"]))
        self._set_literal(graph, iri, PROMO["name"], name)
        if kind is not None:
            self._set_literal(graph, iri, PROMO["dimensionKind"], kind)
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
        self._set_literal(graph, iri, RDFS.label, label)
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
        scale_values: Optional[List[Union[str, URIRef]]] = None,
        parent: Optional[Union[str, URIRef]] = None,
    ) -> URIRef:
        """Add an entity type (CWA 17960 taxonomy) to the graph."""
        graph.add((iri, RDF.type, PROMO["EntityType"]))
        self._set_literal(graph, iri, RDFS.label, label)
        self._set_literal(graph, iri, PROMO["temporalType"], temporal_type)
        self._set_literal(graph, iri, PROMO["branch"], branch)
        if parent is not None:
            if isinstance(parent, str):
                parent = URIRef(parent)
            graph.set((iri, PROMO["parent"], parent))
        if spatial_type is not None:
            self._set_literal(graph, iri, PROMO["spatialType"], spatial_type)
        if spatial_size is not None:
            self._set_literal(graph, iri, PROMO["spatialSize"], spatial_size)
        if description:
            self._set_literal(graph, iri, PROMO["doc"], description)
        if scale_values is not None:
            graph.remove((iri, PROMO["hasScaleValue"], None))
            for sv in scale_values:
                if isinstance(sv, str):
                    sv = URIRef(sv)
                graph.add((iri, PROMO["hasScaleValue"], sv))
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
        carrier: Optional[str] = None,
        scope: Optional[str] = None,
        description: str = "",
    ) -> URIRef:
        """Add a connection rule definition to the graph."""
        graph.add((iri, RDF.type, PROMO["ConnectionRule"]))
        self._set_literal(graph, iri, PROMO["ruleType"], rule_type)
        if direction is not None:
            self._set_literal(graph, iri, PROMO["direction"], direction)
        if carrier is not None:
            self._set_literal(graph, iri, PROMO["carrier"], carrier)
        if scope is not None:
            self._set_literal(graph, iri, PROMO["scope"], scope)
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
        self._set_literal(graph, iri, RDFS.label, label)
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
