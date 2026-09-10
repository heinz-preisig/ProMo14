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

from typing import Dict, List, Optional, Protocol, Set

from .compile_space import Index, Variable


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

    def variables(self) -> Dict[str, Variable]:
        return self._variables

    def indices(self) -> Dict[str, Index]:
        return self._indices

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
