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
    if isinstance(value, list):
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

    def add_variable_dict(self, graph: Graph, var: dict) -> URIRef:
        """Add a variable record to the graph using the ProMo14 schema."""
        iri = URIRef(var["iri"])
        graph.add((iri, RDF.type, PROMO["Variable"]))
        self._set_literal(graph, iri, PROMO["label"], var.get("label"))
        self._set_literal(graph, iri, PROMO["internalID"], var.get("internal_id"))
        self._set_literal(graph, iri, PROMO["network"], var.get("network"))
        self._set_literal(graph, iri, PROMO["variableClass"], var.get("type"))
        self._set_literal(graph, iri, PROMO["doc"], var.get("doc"))
        self._set_literal(
            graph, iri, PROMO["portVariable"], var.get("port_variable", False)
        )

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
    # Helpers
    # ------------------------------------------------------------------

    def as_trig(self) -> str:
        """Return the whole dataset as a TriG string."""
        return self.dataset.serialize(format="trig")
