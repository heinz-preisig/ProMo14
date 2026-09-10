# Equation Editor Context Contract

The equation editor (``backend/equation``) does not read the ontology graph
directly.  Instead it consumes a **context** — a read-only snapshot of the
variables, indices, and network domain tree that are visible while one
expression is being parsed and checked.

This contract is the seam between the ontology layer and the equation editor.
The ontology side only has to satisfy the contract; the checker, parser, and
units code stay unchanged when the storage backend (dict, RDF, SQL, …) changes.

## 1. Protocol: ``EquationContext``

``backend/equation/context.py``:

```python
class EquationContext(Protocol):
    def variables(self) -> Dict[str, Variable]:
        ...
    def indices(self) -> Dict[str, Index]:
        ...
    def accessible_networks(self, network: str) -> Set[str]:
        ...
```

- ``variables()`` — keyed by **variable IRI** (not label).  The label is a
  field on the ``Variable`` record and may appear multiple times in the graph
  (e.g. ``physical!V`` and ``reactions!V``).
- ``indices()`` — keyed by **index IRI**.
- ``accessible_networks(network)`` — returns the expression network plus all
  its ancestors in the domain tree.  Variables defined in any of those
  networks are visible from ``network``; siblings are not.

## 2. Concrete provider: ``DictContext``

The in-memory implementation is used by:

- unit and checker tests,
- the ProMo13 corpus replay test,
- the ``/api/equation/check`` endpoint until a graph-store provider is wired in.

It takes a parent → children ``tree`` and walks up to the root to compute
``accessible_networks``.

## 3. ``CompileSpace`` resolution rules

``CompileSpace`` is the concrete context object the checker uses.
``CompileSpace.__init__`` accepts an optional
``accessible_networks: Set[str]`` parameter.  If omitted it defaults to
``{expression_definition_network}`` (the pre-hierarchy behaviour).

Unqualified variable resolution is, in order:

1. **Local network** — a variable with the requested label in
   ``expression_definition_network``.  Resolved as *not imported*.
2. **Accessible networks** — variables with the same label in any ancestor
   network.  If exactly one, resolved as *imported*.  If several, raise
   ``AmbiguousVariableError`` and surface the candidates.
3. **Globally unique fallback** — if the label is unique in the entire
   visible graph (but not in an accessible network), resolve as *imported*.
4. **Not found** or **ambiguous** otherwise.

Qualified names (``network!label``) always bypass the hierarchy and require
an exact network + label match.

## 4. Service endpoint consumption

``/api/equation/check`` accepts:

- ``variables`` / ``indices`` arrays — enough to build a ``DictContext``.
- ``network_tree`` — the parent → children domain tree.
- ``variable_definition_network`` and ``expression_definition_network``.

It builds a ``DictContext``, asks for ``accessible_networks(expr_net)``, and
constructs ``CompileSpace``.  In the future this will be replaced by a
graph-store provider that implements ``EquationContext``; the checker will not
change.

## 5. Why this matters for the corpus

The ProMo13 expression corpus (``var_equ_rdf.ttl``) does not export the
domain tree.  Once the ontology work provides the tree and the real
``index_structures``, the equation editor will run those 73 expressions
through the same unchanged code path — only the provider implementation will
change.
