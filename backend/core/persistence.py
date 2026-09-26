"""Dataset persistence — the ``PersistenceMixin`` half of ``RdfStore``.

Split out of ``core/graph_store.py`` for size: TriG load/save (one
file per artefact line), the legacy id/IRI migrations, and the dirty
flag.  Composed back onto ``RdfStore`` via multiple inheritance.
"""

from __future__ import annotations

import datetime
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import RDF

from .vocab import PROMO, _EQUATION_ID_RE


class PersistenceMixin:
    """TriG load/save, legacy migrations and the dirty flag."""
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
        self._migrate_domain_membership()

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

    def _migrate_domain_membership(self) -> None:
        """Use domain IRIs as identity while retaining legacy network labels."""
        old_root = self.mint_iri(self.ONTOLOGY_GRAPH_IRI, "domain_root")
        universe = self.mint_iri(self.ONTOLOGY_GRAPH_IRI, "domain_universe")
        changed = False

        for graph in self.dataset.graphs():
            if (old_root, RDF.type, PROMO["Domain"]) in graph:
                for _s, predicate, obj in list(graph.triples((old_root, None, None))):
                    graph.remove((old_root, predicate, obj))
                    graph.add((universe, predicate, obj))
                changed = True
            for subject, predicate, obj in list(graph.triples((None, None, old_root))):
                graph.remove((subject, predicate, obj))
                graph.add((subject, predicate, universe))
                changed = True
            if (universe, RDF.type, PROMO["Domain"]) in graph \
                    and str(graph.value(universe, PROMO["name"]) or "") != "universe":
                graph.set((universe, PROMO["name"], Literal("universe")))
                changed = True
            for subject in graph.subjects(PROMO["network"], Literal("root")):
                graph.set((subject, PROMO["network"], Literal("universe")))
                changed = True

        ontology = self.ontology_graph
        if (universe, RDF.type, PROMO["Domain"]) not in ontology:
            ontology.add((universe, RDF.type, PROMO["Domain"]))
            changed = True
        if str(ontology.value(universe, PROMO["name"]) or "") != "universe":
            ontology.set((universe, PROMO["name"], Literal("universe")))
            changed = True

        domains_by_name: Dict[str, URIRef] = {}
        for graph in self.dataset.graphs():
            for domain in graph.subjects(RDF.type, PROMO["Domain"]):
                name = graph.value(domain, PROMO["name"])
                if name is not None:
                    domains_by_name[str(name)] = domain
        domains_by_name["root"] = universe
        domains_by_name["universe"] = universe

        for graph in self.dataset.graphs():
            for rdf_type in (PROMO["Variable"], PROMO["Equation"], PROMO["Index"]):
                for subject in graph.subjects(RDF.type, rdf_type):
                    if graph.value(subject, PROMO["inDomain"]) is not None:
                        continue
                    name = graph.value(subject, PROMO["network"])
                    domain = domains_by_name.get(str(name or "universe"))
                    if domain is not None:
                        graph.set((subject, PROMO["inDomain"], domain))
                        changed = True
        if changed:
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
