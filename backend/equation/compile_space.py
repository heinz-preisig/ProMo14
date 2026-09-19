"""Compile space — the read-only context the expression checker runs against.

Ported from ProMo13 ``variable_framework.CompileSpace`` and
``PhysicalVariable``. A compile space bundles the variables and indices that
are visible while one expression is being checked, plus the two networks that
matter for resolution:

- ``variable_definition_network`` — where the LHS variable is defined;
- ``expression_definition_network`` — where the equation is written.

Differences from the ProMo13 original:

- **Read-only.** Per ADR-006 the ontology is frozen at editor level — nothing
  here mutates the index or variable sets. ``diffSpace``/``MakeIndex`` style
  on-the-fly index creation is gone.
- **No rendering state.** The old ``getVariable`` set ``v.language`` and
  ``v.indices`` on the returned variable so ``__str__`` could render it.
  Rendering moves to ``codegen/``; resolution here is a pure lookup.
- **Explicit records.** ``Variable`` and ``Index`` are dataclasses with named
  fields instead of ``self.__dict__ = kwargs``.
- **IRI-keyed.** Variables and indices are keyed by IRI; the internal ID
  (``V_12`` / ``I_3``) is a field, matching ADR-005's three-names scheme.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .errors import AmbiguousVariableError, VarError
from .symbols import DEFAULT_TABLE, SymbolTable
from .units import Units

#: Template for temporary-variable labels (old ``TEMPLATES["temp_variable"]``).
TEMP_VARIABLE_TEMPLATE = "temp_%s"

#: Index kinds recognised in the ``type`` field (old ``indices[i]["type"]``).
INDEX_TYPES = ("index", "block_index")


@dataclass
class Index:
    """An index structure declared by the ontology.

    ``aliases`` maps language name → surface form; ``internal_code`` is the
    alias the expression language uses (what ``get_index`` resolves).
    """

    iri: str
    label: str
    network: str
    index_class: str = "index"  # "index" | "block_index"
    aliases: Dict[str, str] = field(default_factory=dict)
    token: Optional[str] = None  # IRI of the token type this index carries
    internal_id: Optional[str] = None

    def alias(self, language: str = "internal_code") -> str:
        return self.aliases.get(language, self.label)


@dataclass
class Variable:
    """A declared variable — the ported ``PhysicalVariable`` record.

    Only the fields the checker needs are explicit; everything else the old
    record carried (equation lists, timestamps, …) belongs to the var/expr
    graph, not the compile context.
    """

    iri: str
    label: str
    network: str
    type: str
    units: Units = field(default_factory=Units)
    index_structures: List[str] = field(default_factory=list)  # index IRIs
    doc: str = ""
    port_variable: bool = False
    internal_id: Optional[str] = None  # e.g. "V_12"
    aliases: Dict[str, str] = field(default_factory=dict)
    tokens: List[str] = field(default_factory=list)  # token-type IRIs
    value: Optional[str] = None  # pre-bound promo:value (universal constants)


@dataclass(frozen=True)
class ResolvedVariable:
    """Result of :meth:`CompileSpace.resolve`.

    ``imported`` is True when the variable was reached through an explicit
    ``network!label`` qualifier or by global-unique auto-resolution — i.e. it
    lives outside the expression's own network. Codegen uses this to decide
    whether to render the qualified name.
    """

    variable: Variable
    imported: bool


class CompileSpace:
    """Variable/index context for checking one expression."""

    def __init__(
        self,
        variables: Dict[str, Variable],
        indices: Dict[str, Index],
        variable_definition_network: str,
        expression_definition_network: str,
        table: SymbolTable = DEFAULT_TABLE,
        accessible_networks: Optional[set] = None,
        network_tree: Optional[Dict[str, List[str]]] = None,
    ):
        self.variables = variables
        self.indices = indices
        self.table = table
        self.variable_definition_network = variable_definition_network
        self.expression_definition_network = expression_definition_network
        # Networks whose variables are visible from the expression network
        # (itself + ancestors in the domain tree). Defaults to just the
        # expression network — the pre-hierarchy behaviour.
        self.accessible_networks = (
            accessible_networks
            if accessible_networks is not None
            else {expression_definition_network}
        )
        self.network_tree = network_tree or {}
        # Reverse map: child -> parent, used for nearest-ancestor resolution.
        self._parent_of: Dict[str, str] = {}
        for parent, children in self.network_tree.items():
            for child in children:
                self._parent_of[child] = parent

        # label and internal_code alias → index IRI (old ``inverse_indices``)
        self.inverse_indices: Dict[str, str] = {}
        self.base_indices: List[str] = []
        self.block_indices: List[str] = []
        for iri, idx in indices.items():
            if idx.index_class not in INDEX_TYPES:
                raise VarError(
                    "fatal error -- not a proper index type %s" % iri
                )
            self.inverse_indices[idx.label] = iri
            internal = idx.aliases.get("internal_code")
            if internal:
                self.inverse_indices[internal] = iri
            # The IRI fragment (e.g. ...#I_1) is also a valid surface token.
            tail = iri.split("#")[-1].split("/")[-1]
            if tail and tail not in self.inverse_indices:
                self.inverse_indices[tail] = iri
            if idx.index_class == "index":
                self.base_indices.append(iri)
            else:
                self.block_indices.append(iri)

        # internal ID → IRI, for the legacy by-ID lookup branch
        self._by_internal_id: Dict[str, str] = {
            v.internal_id: iri
            for iri, v in variables.items()
            if v.internal_id
        }

        self._temp_counter = 0

    # -- resolution ---------------------------------------------------------

    def _nearest_accessible(self, accessible: List[Variable]) -> Optional[Variable]:
        """Return the accessible variable with the nearest ancestor network.

        Distance is measured as the number of steps from
        ``self.expression_definition_network`` up to the candidate's network.
        If several candidates share the smallest distance, the label is still
        ambiguous and ``None`` is returned so the caller raises.
        """

        def distance(network: str) -> int:
            if network == self.expression_definition_network:
                return 0
            steps = 0
            current = self.expression_definition_network
            while current in self._parent_of:
                current = self._parent_of[current]
                steps += 1
                if current == network:
                    return steps
            return -1

        scored: List[Tuple[int, Variable]] = []
        for var in accessible:
            d = distance(var.network)
            if d >= 0:
                scored.append((d, var))

        if not scored:
            return None

        scored.sort(key=lambda x: x[0])
        best_distance = scored[0][0]
        top = [var for d, var in scored if d == best_distance]
        if len(top) == 1:
            return top[0]
        return None

    def resolve(self, symbol: str) -> ResolvedVariable:
        """Resolve a ``Var`` name to a variable.

        Rules (unchanged from ProMo13):

        - ``network!label`` — exact match on network and label; ``imported``.
        - internal ID / IRI — direct hit; not imported.
        - unqualified label — prefer the expression's own network; if absent
          there, prefer candidates from ancestor networks visible through
          ``accessible_networks``; if exactly one such candidate exists,
          auto-resolve (``imported``); if several, raise
          :class:`AmbiguousVariableError` carrying the candidates so the UI
          can ask.  A globally-unique label is a final fallback.
        """
        if "!" in symbol:
            network, _, label = symbol.partition("!")
            for var in self.variables.values():
                if var.label == label and var.network == network:
                    return ResolvedVariable(var, imported=True)
            raise VarError(" no such variable %s defined" % symbol)

        if symbol in self.variables:
            return ResolvedVariable(self.variables[symbol], imported=False)
        if symbol in self._by_internal_id:
            return ResolvedVariable(
                self.variables[self._by_internal_id[symbol]], imported=False
            )

        local: Optional[Variable] = None
        accessible: List[Variable] = []
        candidate_ids: List[str] = []
        for iri, var in self.variables.items():
            if var.label != symbol:
                continue
            candidate_ids.append(iri)
            if var.network == self.expression_definition_network:
                local = var
            elif var.network in self.accessible_networks:
                accessible.append(var)

        if local is not None:
            return ResolvedVariable(local, imported=False)

        # If we have a domain tree, prefer the accessible candidate closest
        # to the expression network (fewest steps up the tree).
        if self.network_tree and accessible:
            best = self._nearest_accessible(accessible)
            if best is not None:
                return ResolvedVariable(best, imported=True)

        if len(accessible) == 1:
            return ResolvedVariable(accessible[0], imported=True)
        if len(accessible) > 1:
            candidates = [
                {
                    "iri": iri,
                    "network": self.variables[iri].network,
                    "label": self.variables[iri].label,
                    "type": self.variables[iri].type,
                    "doc": self.variables[iri].doc,
                }
                for iri in candidate_ids
                if self.variables[iri].network in self.accessible_networks
            ]
            nets = sorted({c["network"] for c in candidates})
            suggestions = ", ".join("%s!%s" % (n, symbol) for n in nets)
            raise AmbiguousVariableError(
                "Variable %s is ambiguous. Use one of: %s"
                % (symbol, suggestions),
                symbol,
                candidates,
            )

        # fallback: globally unique label, even if not in an accessible network
        if len(candidate_ids) == 1:
            return ResolvedVariable(
                self.variables[candidate_ids[0]], imported=True
            )
        if len(candidate_ids) > 1:
            candidates = [
                {
                    "iri": iri,
                    "network": self.variables[iri].network,
                    "label": self.variables[iri].label,
                    "type": self.variables[iri].type,
                    "doc": self.variables[iri].doc,
                }
                for iri in candidate_ids
            ]
            nets = sorted({c["network"] for c in candidates})
            suggestions = ", ".join("%s!%s" % (n, symbol) for n in nets)
            raise AmbiguousVariableError(
                "Variable %s is ambiguous. Use one of: %s"
                % (symbol, suggestions),
                symbol,
                candidates,
            )
        raise VarError(" no such variable %s defined" % symbol)

    def get_variable(self, symbol: str) -> Variable:
        """Convenience wrapper returning just the variable."""
        return self.resolve(symbol).variable

    def get_index(self, symbol: str) -> Optional[str]:
        """Resolve an index surface name to its IRI, or ``None``."""
        return self.inverse_indices.get(symbol)

    # -- helpers for error messages ------------------------------------------

    def index_alias(self, iri: str, language: str = "internal_code") -> str:
        idx = self.indices.get(iri)
        return idx.alias(language) if idx else iri

    def pretty_index_list(self, iris: List[str]) -> str:
        """Render index IRIs as their internal-code aliases, for errors."""
        return "[%s]" % ", ".join(self.index_alias(i) for i in iris)

    # -- temp variables -------------------------------------------------------

    def new_temp(self) -> str:
        """Allocate a temporary-variable label (``temp_0``, ``temp_1``, …)."""
        label = TEMP_VARIABLE_TEMPLATE % self._temp_counter
        self._temp_counter += 1
        return label
