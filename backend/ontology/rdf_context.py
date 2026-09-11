"""RDF-backed ``EquationContext`` provider.

``RdfContext`` reads the ontology vocabulary (variables, indices, domain tree)
from an ``RdfStore`` and presents it to the equation checker as a read-only
snapshot.  It is the first concrete provider that replaces the temporary
legacy-file loader.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Set

from rdflib import Namespace, URIRef
from rdflib.namespace import RDF

from backend.core.graph_store import RdfStore
from backend.equation.compile_space import Index, Variable
from backend.equation.context import EquationContext
from backend.equation.units import Units

PROMO = Namespace("http://example.org#")


def _str(value) -> str:
    return str(value) if value is not None else ""


def _literal_list(graph, subject, predicate) -> List[str]:
    """Return all URIRef / Literal object values for a predicate as strings."""
    return [str(o) for o in graph.objects(subject, predicate)]


def _one_literal(graph, subject, predicate, default: str = "") -> str:
    value = graph.value(subject, predicate, default=None)
    return str(value) if value is not None else default


def _one_bool(graph, subject, predicate, default: bool = False) -> bool:
    value = graph.value(subject, predicate, default=None)
    if value is None:
        return default
    text = str(value).lower()
    return text in ("true", "1", "yes")


def _one_unit_list(graph, subject, predicate) -> List[int]:
    value = graph.value(subject, predicate, default=None)
    if value is None:
        return [0] * 8
    try:
        parsed = json.loads(str(value))
        if isinstance(parsed, list) and len(parsed) == 8:
            return [int(x) for x in parsed]
    except (json.JSONDecodeError, ValueError):
        pass
    return [0] * 8


def _aliases(graph, subject) -> Dict[str, str]:
    """Collect language aliases from direct predicates or the JSON map."""
    aliases: Dict[str, str] = {}
    for key in ("internal_code", "latex", "matlab"):
        pred = PROMO[key]
        value = graph.value(subject, pred, default=None)
        if value is not None:
            aliases[key] = str(value)

    raw = graph.value(subject, PROMO["aliases"], default=None)
    if raw is not None:
        try:
            parsed = json.loads(str(raw))
            if isinstance(parsed, dict):
                aliases.update({k: str(v) for k, v in parsed.items()})
        except (json.JSONDecodeError, ValueError):
            pass

    return aliases


class RdfContext(EquationContext):
    """Equation context backed by an ``RdfStore``.

    The context is a snapshot: it is built once when the provider is created
    and does not change while an expression is being checked.
    """

    def __init__(self, store: RdfStore):
        self.store = store
        self._graph = store.ontology_graph
        self._variables = self._load_variables()
        self._indices = self._load_indices()
        self._tree = self._load_network_tree()
        self._parent_of = self._build_parent_of(self._tree)

    # ------------------------------------------------------------------
    # EquationContext protocol
    # ------------------------------------------------------------------

    def variables(self) -> Dict[str, Variable]:
        return self._variables

    def indices(self) -> Dict[str, Index]:
        return self._indices

    def accessible_networks(self, network: str) -> Set[str]:
        if network is None:
            return set()
        accessible: Set[str] = {network}
        current = network
        while current in self._parent_of:
            current = self._parent_of[current]
            accessible.add(current)
        return accessible

    def tree(self) -> Dict[str, List[str]]:
        """Return the parent -> children network tree (used by the API)."""
        return self._tree

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------

    def _load_variables(self) -> Dict[str, Variable]:
        variables: Dict[str, Variable] = {}
        for s in self._graph.subjects(RDF.type, PROMO["Variable"]):
            iri = str(s)
            aliases = _aliases(self._graph, s)
            units = Units.from_list(_one_unit_list(self._graph, s, PROMO["unitVector"]))
            variables[iri] = Variable(
                iri=iri,
                label=_one_literal(self._graph, s, PROMO["label"], iri),
                network=_one_literal(self._graph, s, PROMO["network"], "root"),
                type=_one_literal(self._graph, s, PROMO["variableClass"], "state"),
                units=units,
                index_structures=_literal_list(self._graph, s, PROMO["indexStructure"]),
                doc=_one_literal(self._graph, s, PROMO["doc"], ""),
                port_variable=_one_bool(self._graph, s, PROMO["portVariable"], False),
                internal_id=_one_literal(self._graph, s, PROMO["internalID"])
                or aliases.get("global_ID")
                or iri,
                aliases=aliases,
                tokens=_literal_list(self._graph, s, PROMO["carriesToken"]),
            )
        return variables

    def _load_indices(self) -> Dict[str, Index]:
        indices: Dict[str, Index] = {}
        for s in self._graph.subjects(RDF.type, PROMO["Index"]):
            iri = str(s)
            aliases = _aliases(self._graph, s)
            short = _one_literal(self._graph, s, PROMO["shortName"])
            if short and "internal_code" not in aliases:
                aliases["internal_code"] = short
            indices[iri] = Index(
                iri=iri,
                label=_one_literal(self._graph, s, PROMO["label"], iri),
                network=_one_literal(self._graph, s, PROMO["network"], "root"),
                index_class=_one_literal(self._graph, s, PROMO["indexClass"], "index"),
                aliases=aliases,
                token=_one_literal(self._graph, s, PROMO["token"]) or None,
            )
        return indices

    def _load_network_tree(self) -> Dict[str, List[str]]:
        """Build a parent -> children map from ``promo:child`` triples."""
        tree: Dict[str, List[str]] = {}
        name_to_iri: Dict[str, URIRef] = {}

        for s in self._graph.subjects(RDF.type, PROMO["Network"]):
            name = _one_literal(self._graph, s, PROMO["name"])
            if name:
                name_to_iri[name] = s

        # First pass: explicit children.
        for parent, child in self._graph.subject_objects(PROMO["child"]):
            parent_name = _one_literal(self._graph, parent, PROMO["name"])
            child_name = _one_literal(self._graph, child, PROMO["name"])
            if parent_name and child_name:
                tree.setdefault(parent_name, []).append(child_name)

        # Second pass: make sure leaf networks appear in the tree.
        for name in name_to_iri:
            if name not in tree:
                tree[name] = []

        return tree

    def _build_parent_of(self, tree: Dict[str, List[str]]) -> Dict[str, str]:
        parent_of: Dict[str, str] = {}
        for parent, children in tree.items():
            for child in children:
                parent_of[child] = parent
        return parent_of
