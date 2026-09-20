"""RDF-backed ``EquationContext`` provider.

``RdfContext`` reads the ontology vocabulary (variables, indices, domain tree)
from an ``RdfStore`` and presents it to the equation checker as a read-only
snapshot.

Variables, indices and the network tree are collected from **all** named
graphs in the dataset — the editable ontology graph plus any var/expr graphs
published by the equation editor.  Ontology vocabulary (domains, axes,
entity types, rules) is read from the ontology graph only.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Union

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS

from backend.core.graph_store import PROMO, RdfStore
from backend.equation.compile_space import Index, Variable
from backend.equation.context import EquationContext
from backend.equation.units import Units


def _str(value) -> str:
    return str(value) if value is not None else ""


def _network(raw: str) -> str:
    """Return the network name, defaulting to ``"root"``."""
    return raw or "root"


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

    ``graph_iris`` selects the resolution scope (design doc R4): the
    graphs whose union supplies the ontology vocabulary *and* the
    variable/index population — typically the subject artefact plus its
    ``promo:usesOntology`` pin set.  ``None`` keeps the legacy scope:
    vocabulary from the working ontology graph, variables from every
    graph in the dataset.
    """

    def __init__(
        self,
        store: RdfStore,
        graph_iris: Optional[List[Union[str, URIRef]]] = None,
    ):
        self.store = store
        if graph_iris is None:
            self._graph = store.ontology_graph
            self._scope: Optional[List[Any]] = None
        else:
            graphs = [store.dataset.graph(URIRef(str(i)))
                      for i in graph_iris]
            union = Graph()
            for g in graphs:
                for t in g:
                    union.add(t)
            self._graph = union
            self._scope = graphs
        self._variables = self._load_variables()
        self._indices = self._load_indices()
        self._tree, self._parent_of = self._load_network_tree()
        self._domains = self._load_domains()
        self._axes = self._load_axes()
        self._entity_types = self._load_entity_types()
        self._connection_rules = self._load_connection_rules()

    def _all_graphs(self) -> List[Any]:
        """Graphs in scope: the explicit ``graph_iris`` set, or every
        graph in the dataset when unscoped (ontology + var/expr graphs)."""
        if self._scope is not None:
            return self._scope
        return list(self.store.dataset.contexts())

    @property
    def graph(self) -> Any:
        """The vocabulary view: the working ontology graph, or a union
        copy of ``graph_iris`` when scoped."""
        return self._graph

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
        """Return token IRIs bound directly to a domain (``hasToken``)."""
        subject = URIRef(domain_iri)
        return [str(t) for t in self._graph.objects(subject, PROMO["hasToken"])]

    def effective_tokens(self, domain_iri: str) -> List[str]:
        """Return tokens active in a domain: own plus inherited ancestors'."""
        return [str(t) for t in self.store.effective_tokens(
            self._graph, URIRef(domain_iri))]

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
            if current in accessible:  # cycle guard (derived >>> edges)
                break
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
        for graph in self._all_graphs():
            for s in graph.subjects(RDF.type, PROMO["Variable"]):
                iri = str(s)
                var = self._build_variable(graph, s, iri)
                existing = variables.get(iri)
                if existing is None:
                    variables[iri] = var
                else:
                    # Same variable in several graphs: merge equations
                    # rather than dropping one copy.
                    getattr(existing, "equations").update(
                        getattr(var, "equations")
                    )
        return variables

    def _build_variable(self, graph, s, iri: str) -> Variable:
        aliases = _aliases(graph, s)
        fragment = iri.split("#")[-1].split("/")[-1]
        if fragment and "global_ID" not in aliases:
            aliases["global_ID"] = fragment

        # Multi-axis classifications (promo:axisValue -> axis term IRI).
        classifications: Dict[str, str] = {}
        for term_iri in graph.objects(s, PROMO["axisValue"]):
            axis_iri = graph.value(term_iri, PROMO["hasAxis"])
            if axis_iri:
                classifications[str(axis_iri)] = str(term_iri)

        var = Variable(
            iri=iri,
            label=_one_literal(graph, s, RDFS.label) or iri,
            network=_network(_one_literal(graph, s, PROMO["network"], "root")),
            type=_one_literal(graph, s, PROMO["variableClass"], "state"),
            units=Units.from_list(
                _one_unit_list(graph, s, PROMO["unitVector"])
            ),
            index_structures=_literal_list(graph, s, PROMO["indexStructure"]),
            doc=_one_literal(graph, s, PROMO["doc"], ""),
            port_variable=_one_bool(graph, s, PROMO["portVariable"], False),
            internal_id=_one_literal(graph, s, PROMO["internalID"])
            or aliases.get("global_ID")
            or iri,
            aliases=aliases,
            tokens=_literal_list(graph, s, PROMO["carriesToken"]),
            value=_one_literal(graph, s, PROMO["value"]) or None,
        )
        setattr(var, "classifications", classifications)
        setattr(
            var,
            "imported",
            _one_bool(graph, s, PROMO["imported"], False),
        )
        setattr(var, "equations", self._variable_equations(graph, s, iri))
        return var

    def _variable_equations(self, graph, s, var_iri: str) -> Dict[str, dict]:
        """Collect ``promo:hasEquation`` -> ``promo:Equation`` resources."""
        equations: Dict[str, dict] = {}
        for eq_s in graph.objects(s, PROMO["hasEquation"]):
            eq_iri = str(eq_s)
            eq_internal_id = _one_literal(graph, eq_s, PROMO["internalID"])
            # incidence_list is stored as a JSON array literal
            inc_raw = graph.value(eq_s, PROMO["incidenceList"])
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
                "lhs": var_iri,
                "rhs": _one_literal(graph, eq_s, PROMO["rhs"]),
                "rhs_latex": _one_literal(graph, eq_s, PROMO["rhsLatex"])
                or None,
                "equation_class": _one_literal(graph, eq_s, PROMO["equationClass"])
                or None,
                "network": _one_literal(graph, eq_s, PROMO["network"]) or None,
                "incidence_list": eq_incidence,
                "doc": _one_literal(graph, eq_s, PROMO["doc"]) or "",
                "created": _one_literal(graph, eq_s, PROMO["created"]) or None,
                "modified": _one_literal(graph, eq_s, PROMO["modified"]) or None,
            }
        return equations

    def _load_indices(self) -> Dict[str, Index]:
        indices: Dict[str, Index] = {}
        for graph in self._all_graphs():
            for s in graph.subjects(RDF.type, PROMO["Index"]):
                iri = str(s)
                if iri in indices:
                    continue
                indices[iri] = self._build_index(graph, s, iri)
        return indices

    @staticmethod
    def _build_index(graph, s, iri: str) -> Index:
        aliases = _aliases(graph, s)
        fragment = iri.split("#")[-1].split("/")[-1]
        if fragment and "global_ID" not in aliases:
            aliases["global_ID"] = fragment
        label = _one_literal(graph, s, RDFS.label) or fragment or iri
        # The short name is the surface token used in expressions; fall
        # back to the label when no explicit shortName is stored.
        short = _one_literal(graph, s, PROMO["shortName"]) or label
        if "internal_code" not in aliases:
            aliases["internal_code"] = short

        network = _network(_one_literal(graph, s, PROMO["network"], "root"))

        # The ontology's indexClass names the index *source* (node, arc,
        # token, conversion, signal); the checker's index_class only knows
        # "index" | "block_index".  Map across and keep the source kind in
        # the aliases for consumers that care.
        raw_class = _one_literal(graph, s, PROMO["indexClass"], "index")
        index_class = raw_class if raw_class in ("index", "block_index") else "index"
        if raw_class != index_class:
            aliases.setdefault("index_source", raw_class)

        return Index(
            iri=iri,
            label=label,
            network=network,
            index_class=index_class,
            aliases=aliases,
            token=_one_literal(graph, s, PROMO["token"]) or None,
            internal_id=_one_literal(graph, s, PROMO["internalID"])
            or aliases.get("global_ID")
            or iri,
            sub_index_of=_one_literal(graph, s, PROMO["subIndexOf"]) or None,
            selector=_one_literal(graph, s, PROMO["selector"]) or None,
        )

    def _load_network_tree(self) -> "tuple[Dict[str, List[str]], Dict[str, str]]":
        """Build the (display tree, parent map) pair for network names.

        Built from ``promo:Domain`` nodes linked by ``promo:parent``.
        Network names referenced by variables are included as well so a
        variable can never live in an invisible network.  Parentless
        top-level entries are attached under ``"root"`` so the frontend's
        tree select always has a single root.
        """
        names: Set[str] = set()
        parent_of: Dict[str, str] = {}

        for graph in self._all_graphs():
            for s in graph.subjects(RDF.type, PROMO["Domain"]):
                name = _one_literal(graph, s, PROMO["name"])
                if not name:
                    continue
                names.add(name)
                parent = graph.value(s, PROMO["parent"])
                if parent is not None:
                    parent_name = _one_literal(graph, parent, PROMO["name"])
                    if parent_name and parent_name != name:
                        parent_of[name] = parent_name
                        names.add(parent_name)

            # Register network names referenced by variables.
            for s in graph.subjects(RDF.type, PROMO["Variable"]):
                names.add(
                    _network(_one_literal(graph, s, PROMO["network"], "root"))
                )

        # Every parentless network hangs under "root" so the global scope
        # is reachable from everywhere.
        for name in names:
            if name != "root":
                parent_of.setdefault(name, "root")

        # Break cycles: if walking up from a node revisits a node, reattach
        # the starting node directly under "root".
        for name in list(names):
            seen = {name}
            current = name
            while current in parent_of:
                current = parent_of[current]
                if current in seen:
                    parent_of[name] = "root"
                    break
                seen.add(current)

        # Invert into a parent -> children display tree; parentless names go
        # under "root" so the frontend always has a single root.
        tree: Dict[str, List[str]] = {}
        for name in sorted(names):
            parent = parent_of.get(name, "root")
            if name == "root":
                continue
            tree.setdefault(parent, []).append(name)
        for name in names | {"root"}:
            tree.setdefault(name, [])

        return tree, parent_of

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
            effective = [str(t) for t in self.store.effective_tokens(
                self._graph, s)]
            domains.append({
                "iri": str(s),
                "name": name,
                "parent": str(parent) if parent else None,
                "branch": str(branch) if branch else None,
                "tokens": tokens,
                "effective_tokens": effective,
            })
        return domains

    def _load_axes(self) -> List[Dict[str, Any]]:
        """Load classification axes from the graph."""
        axes: List[Dict[str, Any]] = []
        for s in self._graph.subjects(RDF.type, PROMO["ClassificationAxis"]):
            name = _one_literal(self._graph, s, PROMO["name"])
            domain = self._graph.value(s, PROMO["hasDomain"])
            parent = self._graph.value(s, PROMO["parent"])
            # Load terms for this axis.
            terms: List[Dict[str, str]] = []
            for term_s in self._graph.subjects(PROMO["hasAxis"], s):
                term_label = _one_literal(self._graph, term_s, RDFS.label)
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
            label = _one_literal(self._graph, s, RDFS.label)
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
            carrier = self._graph.value(s, PROMO["carrier"])
            scope = self._graph.value(s, PROMO["scope"])
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
                "carrier": str(carrier) if carrier else None,
                "scope": str(scope) if scope else None,
                "description": doc,
            })
        return rules
