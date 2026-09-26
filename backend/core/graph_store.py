"""Shared RDF graph store for the ProMo suite.

``RdfStore`` wraps an ``rdflib.Dataset`` and provides the low-level storage
that the ontology editor, equation editor, and modeller share.  It is
intentionally thin: it loads/saves named graphs from ``PROMO_DATA_DIR`` and
offers a few helpers for minting IRIs.

The store uses the ProMo vocabulary (``https://w3id.org/promo#``).  When no
``ontology.trig`` exists, a default two-branch ontology is seeded.

Split for size (2026-09-25): vocabulary constants live in
``core/vocab.py`` (re-exported here), TriG persistence in
``core/persistence.py`` (``PersistenceMixin``) and ontology seeding in
``core/seed.py`` (``SeedMixin``).  The public surface is unchanged —
``from backend.core.graph_store import PROMO, get_store`` keeps
working.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rdflib import Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

from .config import get_data_dir
from .persistence import PersistenceMixin
from .seed import SeedMixin
from .vocab import (
    ARTEFACT_TYPES,
    PROMO,
    PROMOLG,
    QUDT,
    SEED_CONSTANTS,
    SEED_FLOOR,
    UNIT_FIELDS,
    XSD,
    _EQUATION_ID_RE,
    _as_literal,
)

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


class RdfStore(PersistenceMixin, SeedMixin):
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
        if var.get("domain_iri"):
            graph.set((iri, PROMO["inDomain"], URIRef(var["domain_iri"])))
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
        if idx.get("domain_iri"):
            graph.set((iri, PROMO["inDomain"], URIRef(idx["domain_iri"])))
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
        if eq.get("domain_iri"):
            graph.set((eq_iri, PROMO["inDomain"], URIRef(eq["domain_iri"])))
        self._set_literal(graph, eq_iri, PROMO["doc"], eq.get("doc"))
        if eq.get("incidence_list"):
            graph.set((eq_iri, PROMO["incidenceList"], _as_literal(eq["incidence_list"])))
        if eq.get("created"):
            self._set_literal(graph, eq_iri, PROMO["created"], eq["created"])
        if eq.get("modified"):
            self._set_literal(graph, eq_iri, PROMO["modified"], eq["modified"])
        return eq_iri
