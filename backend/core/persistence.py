"""Dataset persistence — the ``PersistenceMixin`` half of ``RdfStore``.

Split out of ``core/graph_store.py`` for size: TriG load/save (one
file per artefact line), the legacy id/IRI migrations, and the dirty
flag.  Composed back onto ``RdfStore`` via multiple inheritance.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import RDF

from .vocab import PROMO, _EQUATION_ID_RE

# §26: relative ``promo:X`` URIs — pseudo-prefixed names stored
# verbatim.  Matches whole tokens inside literals too (path-shaped
# ones like ``promo:Model/Node_1`` as well as bare ``promo:d``).
_PROMO_REL_RE = re.compile(r"promo:[A-Za-z_][\w.-]*(?:/[A-Za-z_][\w.-]*)*")


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
        # §26: instance IRIs belong to their artefact — rehome the
        # relative ``promo:X`` spellings before anything else reasons
        # about them.
        self._migrate_variable_iris()
        # §25: incidence factors are seeded scheme objects in the
        # ontology graph — drop hand-authored copies elsewhere so the
        # union read sees one description.
        self._migrate_incidence_factors()
        self._migrate_canonical_rhs()

        # Idempotent vocabulary migration: every artefact graph is
        # self-describing (ADR-006).  Besides the declarations,
        # ``declare_vocabulary`` stamps the ``promo:doc`` convention
        # notes (VOCAB_DOCS — docs/value-cells.md) wherever the terms
        # are declared, so artefacts authored before a term existed
        # pick its doc up on load.  Frozen version graphs are skipped —
        # their content is fixed at publish time.
        for g in self.dataset.contexts():
            if (len(g) and (g.identifier, RDF.type,
                            PROMO["Version"]) not in g):
                self.declare_vocabulary(g)

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

    def _migrate_variable_iris(self) -> None:
        """§26: instance IRIs live under the owning artefact's
        namespace.

        Relative ``promo:X`` URIs — pseudo-prefixed names stored
        verbatim — are consolidated and rehomed: variables to
        ``{home}#<name>``, model records to ``{graph}<name>`` (the
        ``model/Composite_0`` convention).  When a variable's record
        is split across graphs the copies merge into one home: the
        graph holding an equation whose ``lhs`` is the variable, else
        the richest record, ontology winning ties.  References —
        URIRef objects and ``promo:`` tokens inside literals —
        rewrite to the canonical IRI; tokens with no subject anywhere
        expand to ``promo#`` (arc types, dangling refs).  Frozen
        version graphs keep their published spellings.
        """
        graphs = [g for g in self.dataset.contexts()
                  if len(g) and not self.is_frozen(g)]
        rel: Dict[str, List[Graph]] = {}
        for g in graphs:
            for s in g.subjects():
                if isinstance(s, URIRef) and str(s).startswith("promo:"):
                    rel.setdefault(str(s), []).append(g)
        if not rel:
            return
        ont_id = self.ONTOLOGY_GRAPH_IRI

        def home_for(iri: URIRef, holders: List[Graph]) -> Graph:
            # A record already in the ontology artefact is
            # scheme-owned — scopes that pin the ontology but not the
            # var/expr graph must still see it.
            ont = next((g for g in holders
                        if g.identifier == ont_id), None)
            if ont is not None:
                return ont
            for g in holders:
                if (None, PROMO["lhs"], iri) in g:
                    return g
            return max(
                holders,
                key=lambda g: len(list(g.predicate_objects(iri))))

        moves: Dict[str, str] = {}
        for iri_str in sorted(rel):
            s = URIRef(iri_str)
            tail = iri_str[len("promo:"):]
            local = tail.rsplit("/", 1)[-1]
            holders = sorted(rel[iri_str], key=lambda g: str(g.identifier))
            home = home_for(s, holders)
            is_var = any((s, RDF.type, PROMO["Variable"]) in g
                         for g in holders)
            new = URIRef(f"{home.identifier}#{local}" if is_var
                         else f"{home.identifier}{local}")
            moves[iri_str] = str(new)
            # Richest record first, the home record winning ties — its
            # literals become canonical; poorer copies contribute only
            # non-conflicting extras (their stubs lose).
            ordered = sorted(
                holders,
                key=lambda g: (-len(list(g.predicate_objects(s))),
                               g.identifier != home.identifier))
            for g in ordered:
                for _s, p, o in list(g.triples((s, None, None))):
                    if self._absorbable(home, new, p, o):
                        home.add((new, p, o))
                    g.remove((s, p, o))

        def remap(token: str) -> str:
            return moves.get(token) or f"{PROMO}{token[len('promo:'):]}"

        # Reference rewrite: URIRef objects and literal tokens.
        for g in graphs:
            for s, p, o in list(g.triples((None, None, None))):
                if p == PROMO["doc"]:
                    continue   # VOCAB_DOCS prose — re-stamped each load
                if isinstance(o, URIRef) and str(o).startswith("promo:"):
                    g.remove((s, p, o))
                    g.add((s, p, URIRef(remap(str(o)))))
                elif isinstance(o, Literal) and "promo:" in str(o):
                    text = _PROMO_REL_RE.sub(
                        lambda m: remap(m.group(0)), str(o))
                    if text != str(o):
                        g.remove((s, p, o))
                        g.add((s, p, Literal(text)))
        self.mark_dirty()

    @staticmethod
    def _absorbable(g: Graph, new: URIRef, p, o) -> bool:
        """Whether ``(new, p, o)`` may be added during a rehome merge:
        exact duplicates are skipped and for literal-valued
        predicates the existing (canonical) value wins."""
        if (new, p, o) in g:
            return False
        if isinstance(o, Literal):
            for ex in g.objects(new, p):
                if isinstance(ex, Literal) and ex != o:
                    return False
        return True

    def _migrate_incidence_factors(self) -> None:
        """§25/§26: ``{ontology}#F_<mech>`` incidence factors are seeded
        scheme objects — the ontology graph's copy is the single
        description.
        Older stores may carry hand-authored duplicates (the
        port-variable-era ``F_conv``, API-made ``F_heat``) in var/expr
        artefact graphs; under the union read those would merge with —
        or shadow — the seeded record.  Remove their *subject* triples
        from every graph except the ontology.  References *to* the IRI
        (equations, incidence lists) are untouched — shared references
        are the point.
        """
        ont = self.ontology_graph
        base = str(self.ONTOLOGY_GRAPH_IRI)
        arc_iri = URIRef(f"{base}#idx_arc")
        mechs = set()
        for sub in ont.subjects(PROMO["subIndexOf"], arc_iri):
            short = str(ont.value(sub, PROMO["shortName"]) or "")
            if short.startswith("A_"):
                mech = short[2:]
            else:
                mech = str(sub).rsplit("#", 1)[-1].removeprefix("idx_arc_")
            if mech:
                mechs.add(mech)
        if not mechs:
            return
        # §26 canonical form: ``{ontology}#F_<mech>`` — and only in
        # the ontology graph.  Any other subject whose local name is
        # ``F_<mech>`` (relative, vocabulary-ns or artefact-ns
        # spelling) is a duplicate and goes.
        canonical = {URIRef(f"{base}#F_{m}") for m in mechs}
        changed = False
        for g in self.dataset.contexts():
            if self.is_frozen(g):
                continue
            home = g.identifier == self.ONTOLOGY_GRAPH_IRI
            for s in list(g.subjects()):
                local = re.split(r"[#/:]", str(s))[-1]
                if not local.startswith("F_") or local[2:] not in mechs:
                    continue
                if home and s in canonical:
                    continue
                g.remove((s, None, None))
                changed = True
        if changed:
            self.mark_dirty()

    def _migrate_canonical_rhs(self) -> None:
        """Persist semantic RHS trees for equations that only have source text.

        Migration is deliberately best-effort: an equation that cannot be
        checked in its graph's resolution scope keeps its literal ``promo:rhs``
        untouched and can be migrated later once its context is valid.
        """
        from backend.equation.canonical import from_checked, to_source
        from backend.equation.canonical_rdf import (
            RHS_EXPRESSION,
            attach_rhs_expression,
        )
        from backend.equation.checker import check
        from backend.equation.codegen import render
        from backend.equation.compile_space import CompileSpace
        from backend.equation.errors import VarError
        from backend.equation.parser import ParseError, parse
        from backend.equation.syntax import Var
        from backend.ontology.rdf_context import RdfContext

        changed = False
        for graph in self.dataset.graphs():
            equations = [
                equation
                for equation in graph.subjects(RDF.type, PROMO["Equation"])
                if graph.value(equation, PROMO["rhs"]) is not None
                and graph.value(equation, RHS_EXPRESSION) is None
            ]
            if not equations:
                continue

            context = RdfContext(
                self,
                graph_iris=self.resolution_scope(graph.identifier),
            )
            for equation in equations:
                owner = graph.value(None, PROMO["hasEquation"], equation)
                variable = (
                    context.variables().get(str(owner))
                    if owner is not None else None
                )
                if variable is None:
                    continue
                network = str(
                    graph.value(equation, PROMO["network"])
                    or variable.network
                )
                space = CompileSpace(
                    context.variables(),
                    context.indices(),
                    variable_definition_network=variable.network,
                    expression_definition_network=network,
                    accessible_networks=context.accessible_networks(network),
                    network_tree=context.tree(),
                )
                try:
                    checked = check(
                        parse(str(graph.value(equation, PROMO["rhs"]))),
                        space,
                        Var(variable.label),
                    )
                    canonical = from_checked(checked, space)
                    latex = render(checked, space, "latex")
                    source = to_source(canonical, space)
                except (ParseError, VarError):
                    continue

                attach_rhs_expression(
                    graph,
                    equation,
                    canonical,
                    URIRef("%s/expression" % equation),
                )
                graph.set((equation, PROMO["rhs"], Literal(source)))
                graph.set((
                    equation,
                    PROMO["incidenceList"],
                    Literal(json.dumps(sorted(checked.incidence))),
                ))
                graph.set((equation, PROMO["rhsLatex"], Literal(latex)))
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
