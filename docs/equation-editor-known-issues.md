# Equation Editor — Known Issues and Follow-ups

This file tracks the equation-editor work items that are intentionally
deferred until the rest of the ProMo14 architecture (ontology graph store,
RDF persistence, network domain tree) is in place. It mirrors the
test-corpus findings in ``backend/equation/test_corpus.py``.

## 1. Corpus checker pass-rate is 28/73

`backend/equation/test_corpus.py` replays all 73 expressions from the
ProMo13 `packages/Common/ontologies/var_equ_rdf.ttl` export.  All 73 parse
successfully.  When the checker is run with the reconstructed variable/index
context, only 28 of 73 expressions pass.

The failing cases cluster into two root causes (see below).  The test does
**not** assert the check pass-rate; it reports failures with diagnostics so
we can re-run the suite once the missing data becomes available.

## 2. `index_structures` are empty in the old TTL export

The ProMo13 RDF export populates `promo:index_structures_V_N` blocks, but
object IRIs are emitted as empty ``promo:`` references.  The old export
loses the index-structure membership of each variable.  This is a known
serialisation defect noted in ``docs/ADR-005-equation-editor.md``.

### Consequence

Because every variable in the checker context has an empty index list,
operators that require a common running index fail:

- `ReduceProduct` (``*``): fails with *"there must be exactly one common
  index"*.
- `Product(<expr>, <index>)`: fails with *"index X not in argument indices"*.

### What to do once fixed

When the ontology graph store can provide real `index_structures` for each
variable, update ``test_corpus.py`` to resolve them.  The test is written so
that the `CompileSpace` is built with real `Variable.index_structures`; the
expected outcome is that the reduce/product suite (E_30, E_43–E_91,
etc.) starts passing.

## 3. Network hierarchy — mechanism done, data still missing

**Update:** ``CompileSpace`` now accepts ``accessible_networks`` (the
expression network plus its ancestors) and ``resolve`` is hierarchy-aware —
see ``docs/equation-context-contract.md``.  ``DictContext`` computes the
ancestor set from a parent→children ``tree``.

### What is still missing

The corpus TTL does not export the domain tree, nor the per-expression
``expression_definition_network``.  ``test_corpus.py`` therefore uses a
hard-coded ``CORPUS_TREE`` and assumes the expression network equals the
LHS variable's network.  Some corpus expressions still report
``AmbiguousVariableError`` (e.g. ``U - T . S`` with ``T`` in
``macroscopic``/``reactions``) because the real authoring network — likely a
leaf network where ``T`` is local — is not recorded in the export.

### What to do once fixed

When the ontology graph store provides the real domain tree and the
per-equation authoring network, pass them through ``EquationContext`` /
``CheckRequest.network_tree`` / ``expression_definition_network``.  No
checker changes are needed.

## 4. Units are absent from the old variable export

The corpus TTL variable blocks do not contain `promo:units` or equivalent
properties.  The checker is therefore built with every variable as
dimensionless.

### Consequence

Unit propagation rules (`Add` / `TotalDiff` / `ParDiff` / `Power` /
`UFunc`) run, but because all inputs are dimensionless, unit errors cannot
be detected in the corpus replay.

### What to do once fixed

Once the graph store exposes variable units, build the corpus
``CompileSpace`` with real ``Units`` values.  The checker will then catch
the unit consistency errors that the old ProMo13 editor caught.

## 5. FastAPI endpoint dependencies

`backend/equation/service.py` declares ``POST /api/equation/parse`` and
``POST /api/equation/check``.  The endpoints are importable and tested with
stubs, but a full server test requires `fastapi`/`pydantic` installed
(``backend/requirements.txt`` already lists them).

## Files involved

- `backend/equation/checker.py`
- `backend/equation/compile_space.py`
- `backend/equation/parser.py`
- `backend/equation/test_corpus.py`
- `backend/equation/service.py`
- ProMo13 source: `packages/Common/ontologies/var_equ_rdf.ttl`
