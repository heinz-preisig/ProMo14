"""RDF-backed ``EquationContext`` provider.

``RdfContext`` reads the ontology vocabulary (variables, indices, domain tree)
from an ``RdfStore`` and presents it to the equation checker as a read-only
snapshot.  It is the first concrete provider that replaces the temporary
legacy-file loader.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set

from rdflib import Namespace, URIRef
from rdflib.namespace import RDF

from backend.core.graph_store import RdfStore
from backend.core.loader import _parse_network_literal
from backend.equation.compile_space import Index, Variable
from backend.equation.context import EquationContext
from backend.equation.units import Units

PROMO = Namespace("http://example.org#")


def _str(value) -> str:
    return str(value) if value is not None else ""


def _network(raw: str) -> str:
    """Return the most specific network from a list literal or path string."""
    if not raw:
        return "root"
    try:
        parsed = _parse_network_literal(raw)
        if parsed and (len(parsed) > 1 or parsed[0] != raw):
            return parsed[-1]
    except (ValueError, SyntaxError):
        pass
    if ">>>" in raw:
        return raw.split(">>>")[-1].strip()
    return raw


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
        self._domains = self._load_domains()
        self._axes = self._load_axes()
        self._entity_types = self._load_entity_types()
        self._connection_rules = self._load_connection_rules()

    # ------------------------------------------------------------------
    # New ontology entity accessors
    # ------------------------------------------------------------------

    def domains(self) -> List[Dict[str, Any]]:
        """Return domain records (two-branch tree)."""
        return self._domains

    def axes(self) -> List[Dict[str, Any]]:
        """Return classification axes with their terms."""
        return self._axes

    def entity_types(self) -> List[Dict[str, Any]]:
        """Return entity types (CWA 17960 taxonomy)."""
        return self._entity_types

    def connection_rules(self) -> List[Dict[str, Any]]:
        """Return connection rules."""
        return self._connection_rules

    def domain_tokens(self, domain_iri: str) -> List[str]:
        """Return token IRIs bound to a domain."""
        subject = URIRef(domain_iri)
        return [str(t) for t in self._graph.objects(subject, PROMO["hasToken"])]

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
            # Load multi-axis classifications (promo:axisValue -> axis term IRI).
            classifications: Dict[str, str] = {}
            for term_iri in self._graph.objects(s, PROMO["axisValue"]):
                # Find which axis this term belongs to.
                axis_iri = self._graph.value(term_iri, PROMO["hasAxis"])
                if axis_iri:
                    classifications[str(axis_iri)] = str(term_iri)
            variables[iri] = Variable(
                iri=iri,
                label=_one_literal(self._graph, s, PROMO["label"], iri),
                network=_network(_one_literal(self._graph, s, PROMO["network"], "root")),
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
            # Attach classifications as a dynamic attribute.
            setattr(variables[iri], "classifications", classifications)
            setattr(variables[iri], "imported", _one_bool(self._graph, s, PROMO["imported"], False))

            # Load nested equations (promo:hasEquation -> promo:Equation)
            equations: Dict[str, dict] = {}
            for eq_s in self._graph.objects(s, PROMO["hasEquation"]):
                eq_iri = str(eq_s)
                eq_internal_id = _one_literal(self._graph, eq_s, PROMO["internalID"])
                eq_rhs = _one_literal(self._graph, eq_s, PROMO["rhs"])
                eq_rhs_latex = _one_literal(self._graph, eq_s, PROMO["rhsLatex"])
                eq_class = _one_literal(self._graph, eq_s, PROMO["equationClass"])
                eq_network = _one_literal(self._graph, eq_s, PROMO["network"])
                eq_doc = _one_literal(self._graph, eq_s, PROMO["doc"])
                # incidence_list is stored as a JSON array literal
                inc_raw = self._graph.value(eq_s, PROMO["incidenceList"])
                eq_incidence: List[str] = []
                if inc_raw is not None:
                    try:
                        parsed = json.loads(str(inc_raw))
                        if isinstance(parsed, list):
                            eq_incidence = [str(x) for x in parsed]
                    except (json.JSONDecodeError, ValueError):
                        pass
                eq_key = eq_internal_id or eq_iri
                equations[eq_key] = {
                    "iri": eq_iri,
                    "internal_id": eq_internal_id or None,
                    "lhs": iri,
                    "rhs": eq_rhs,
                    "rhs_latex": eq_rhs_latex or None,
                    "equation_class": eq_class or None,
                    "network": eq_network or None,
                    "incidence_list": eq_incidence,
                    "doc": eq_doc or "",
                    "created": None,
                    "modified": None,
                }
            setattr(variables[iri], "equations", equations)
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
                network=_network(_one_literal(self._graph, s, PROMO["network"], "root")),
                index_class=_one_literal(self._graph, s, PROMO["indexClass"], "index"),
                aliases=aliases,
                token=_one_literal(self._graph, s, PROMO["token"]) or None,
                internal_id=_one_literal(self._graph, s, PROMO["internalID"])
                or aliases.get("global_ID")
                or iri,
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

    # ------------------------------------------------------------------
    # New entity loaders
    # ------------------------------------------------------------------

    def _load_domains(self) -> List[Dict[str, Any]]:
        """Load domains (promo:Domain) from the graph."""
        domains: List[Dict[str, Any]] = []
        for s in self._graph.subjects(RDF.type, PROMO["Domain"]):
            name = _one_literal(self._graph, s, PROMO["name"])
            parent = self._graph.value(s, PROMO["parent"])
            branch = self._graph.value(s, PROMO["branch"])
            tokens = [str(t) for t in self._graph.objects(s, PROMO["hasToken"])]
            domains.append({
                "iri": str(s),
                "name": name,
                "parent": str(parent) if parent else None,
                "branch": str(branch) if branch else None,
                "tokens": tokens,
            })
        return domains

    def _load_axes(self) -> List[Dict[str, Any]]:
        """Load classification axes from the graph."""
        axes: List[Dict[str, Any]] = []
        for s in self._graph.subjects(RDF.type, PROMO["ClassificationAxis"]):
            name = _one_literal(self._graph, s, PROMO["axisName"])
            domain = self._graph.value(s, PROMO["hasDomain"])
            parent = self._graph.value(s, PROMO["parent"])
            # Load terms for this axis.
            terms: List[Dict[str, str]] = []
            for term_s in self._graph.subjects(PROMO["hasAxis"], s):
                term_label = _one_literal(self._graph, term_s, PROMO["label"])
                term_parent = self._graph.value(term_s, PROMO["parent"])
                terms.append({
                    "iri": str(term_s),
                    "label": term_label,
                    "parent": str(term_parent) if term_parent else None,
                })
            axes.append({
                "iri": str(s),
                "domain": str(domain) if domain else "",
                "name": name,
                "parent": str(parent) if parent else None,
                "terms": terms,
            })
        return axes

    def _load_entity_types(self) -> List[Dict[str, Any]]:
        """Load entity types (CWA 17960) from the graph."""
        entity_types: List[Dict[str, Any]] = []
        for s in self._graph.subjects(RDF.type, PROMO["EntityType"]):
            label = _one_literal(self._graph, s, PROMO["label"])
            temporal = _one_literal(self._graph, s, PROMO["temporalType"])
            spatial_type = self._graph.value(s, PROMO["spatialType"])
            spatial_size = self._graph.value(s, PROMO["spatialSize"])
            branch = _one_literal(self._graph, s, PROMO["branch"])
            doc = _one_literal(self._graph, s, PROMO["doc"])
            entity_types.append({
                "iri": str(s),
                "label": label,
                "temporal_type": temporal,
                "spatial_type": str(spatial_type) if spatial_type else None,
                "spatial_size": str(spatial_size) if spatial_size else None,
                "branch": branch,
                "description": doc,
            })
        return entity_types

    def _load_connection_rules(self) -> List[Dict[str, Any]]:
        """Load connection rules from the graph."""
        rules: List[Dict[str, Any]] = []
        for s in self._graph.subjects(RDF.type, PROMO["ConnectionRule"]):
            rule_type = _one_literal(self._graph, s, PROMO["ruleType"])
            direction = self._graph.value(s, PROMO["direction"])
            source = self._graph.value(s, PROMO["sourceDomain"])
            target = self._graph.value(s, PROMO["targetDomain"])
            tokens = [str(t) for t in self._graph.objects(s, PROMO["sharedTokens"])]
            doc = _one_literal(self._graph, s, PROMO["doc"])
            rules.append({
                "iri": str(s),
                "rule_type": rule_type,
                "source_domain": str(source) if source else None,
                "target_domain": str(target) if target else None,
                "shared_tokens": tokens,
                "direction": str(direction) if direction else None,
                "description": doc,
            })
        return rules
