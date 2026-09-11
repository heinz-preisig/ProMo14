"""Context contract between the ontology layer and the equation editor.

The checker and the service endpoints never access the ontology graph store
directly; they work through a :class:`CompileSpace` that is built from an
:class:`EquationContext`.  This file defines the protocol and a simple
in-memory implementation.

Responsibilities:

- ``EquationContext`` — the abstract shape the ontology side must satisfy:
  variables, indices, and the network domain tree (via
  ``accessible_networks``).
- ``DictContext`` — an in-memory provider used by tests, the corpus replay,
  and the request-body ``/check`` endpoint until a graph-store provider
  exists.
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Set

from .compile_space import Index, Units, Variable


class EquationContext(Protocol):
    """Read-only source for the compile-time context of one expression.

    Implementations are expected to be cheap snapshots — the checker holds
    the returned dictionaries and does not call back into the provider
    during the check pass.
    """

    def variables(self) -> Dict[str, Variable]:
        """Return a dict keyed by variable IRI."""
        ...

    def indices(self) -> Dict[str, Index]:
        """Return a dict keyed by index IRI."""
        ...

    def accessible_networks(self, network: str) -> Set[str]:
        """Networks whose variables are visible from ``network``.

        This is the expression network plus all ancestor networks in the
        domain tree.  The default in :class:`DictContext` is just
        ``{network}`` unless a tree is supplied.
        """
        ...


class DictContext:
    """In-memory context provider.

    The optional ``tree`` is a parent→children map describing the domain
    hierarchy.  ``accessible_networks`` is derived from it by walking up to
    the root.
    """

    def __init__(
        self,
        variables: Dict[str, Variable],
        indices: Dict[str, Index],
        tree: Optional[Dict[str, List[str]]] = None,
    ):
        self._variables = variables
        self._indices = indices
        self._tree = tree or {}

    @classmethod
    def from_legacy(cls, data_dir: Optional[Path] = None):
        """Build a DictContext from the legacy v8 JSON/TriG files in PROMO_DATA_DIR.

        This is a stop-gap until ``RdfContext`` is fully wired.  It loads the
        real v8 records and converts them into the ``Variable``/``Index``
        dataclasses that ``CompileSpace`` expects.
        """
        from backend.core.loader import load_context

        raw = load_context(data_dir)

        var_fields = {f.name for f in fields(Variable)}
        idx_fields = {f.name for f in fields(Index)}

        def as_variable(rec: Dict[str, Any]) -> Variable:
            rec = dict(rec)
            units = rec.pop("units", [0] * 8)
            rec["units"] = Units.from_list(units) if isinstance(units, list) else Units()
            rec = {k: v for k, v in rec.items() if k in var_fields}
            return Variable(**rec)

        def as_index(rec: Dict[str, Any]) -> Index:
            rec = {k: v for k, v in rec.items() if k in idx_fields}
            return Index(**rec)

        variables = {iri: as_variable(v) for iri, v in raw["variables"].items()}
        indices = {iri: as_index(i) for iri, i in raw["indices"].items()}
        return cls(variables, indices, tree=raw["network_tree"])

    def variables(self) -> Dict[str, Variable]:
        return self._variables

    def indices(self) -> Dict[str, Index]:
        return self._indices

    def tree(self) -> Dict[str, List[str]]:
        """Return the parent -> children network tree."""
        return self._tree

    def accessible_networks(self, network: str) -> Set[str]:
        if network is None:
            return set()
        # build child -> parent reverse map
        parent_of: Dict[str, str] = {}
        for parent, children in self._tree.items():
            for child in children:
                parent_of[child] = parent
        accessible: Set[str] = {network}
        current = network
        while current in parent_of:
            current = parent_of[current]
            accessible.add(current)
        return accessible
