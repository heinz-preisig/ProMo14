# Equation Editor — Known Issues and Follow-ups

This file tracks the equation-editor work items that are intentionally
deferred until the rest of the ProMo14 architecture (ontology graph store,
RDF persistence, network domain tree) is in place. It mirrors the
test-corpus findings in ``backend/equation/test_corpus.py``.

## 1. Corpus checker pass-rate is now 70/73

`backend/equation/test_corpus.py` replays all 73 expressions from the
ProMo13 `packages/Common/ontologies/var_equ_rdf.ttl` export.  All 73 parse
successfully.  With real `index_structures`, units, and the domain tree
loaded from the v8 JSON/TriG files, 70 of 73 expressions now pass full
checks.  The 3 remaining failures are caused by legacy interface variables
that no longer exist in the new arc/connection model (see section 5 below).

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

This is now implemented.  `test_corpus.py` builds the `CompileSpace` from
`RdfContext`, which loads real `Variable.index_structures` from the v8 JSON
seed in `Ontology_Repository/processes_distributed_no_interface_eqs`.  The
reduce/product suite (E_30, E_43–E_91, etc.) now passes.

## 3. Network hierarchy — mechanism done, data still missing

**Update:** ``CompileSpace`` now accepts ``accessible_networks`` (the
expression network plus its ancestors) and ``resolve`` is hierarchy-aware —
see ``docs/equation-context-contract.md``.  ``DictContext`` computes the
ancestor set from a parent→children ``tree``.

### What is still missing

The real domain tree is now loaded from the v8 `ontology.json` into
`RdfContext`, and the expression network is taken from the LHS variable.
Most `AmbiguousVariableError` cases are resolved by nearest-ancestor network
resolution.  The few remaining `T`/`V` ambiguities (`E_59`, `E_63`) were
fixed once `RdfContext` parsed the legacy `>>>` interface network notation
and the corpus loader started using the most-specific network.  The still
failing `E_63` is a legacy interface variable (`promo:_V`) that is not valid
in the new arc/connection model.

### What to do once fixed

This is implemented.  `test_corpus.py` constructs the `CompileSpace` with
`network_tree=rdf_ctx.tree()` and the per-expression
`expression_definition_network` derived from the LHS variable.  No further
checker changes are needed for hierarchy-aware resolution.

## 4. Units are absent from the old variable export

The corpus TTL variable blocks do not contain `promo:units` or equivalent
properties.  The checker is therefore built with every variable as
dimensionless.

### Consequence

Unit propagation rules (`Add` / `TotalDiff` / `ParDiff` / `Power` /
`UFunc`) run, but because all inputs are dimensionless, unit errors cannot
be detected in the corpus replay.

### What to do once fixed

This is now implemented.  `RdfContext` reads the v8 `unitVector` and the
TriG `promo:unit_*` fields.  The corpus `CompileSpace` uses real `Units`
values.  The one remaining unit error (`E_92: anc + and_x`) is in legacy
interface/arc data and is not expected to pass against the old export.

## 5. Remaining failures are legacy interface variables

The ProMo13 `var_equ_rdf.ttl` contains interface/domain-to-domain variables
such as `promo:_T`, `promo:_V`, and `promo:an`.  In the new ProMo14 model
networks are linked by arcs/connections instead, so these variables are not
valid.  The three still-failing expressions are therefore expected to fail
against the old export:

- `E_54: chemPotStandard + R . T . ln ( x )` — index mismatch
  `[N, S] + [N, S, p]` in the old export.
- `E_63: F_NI_source * I_1 V` — `V` ambiguity involving the legacy
  `promo:_V` interface variable.
- `E_92: anc + and_x` — unit mismatch in `promo:an`-related legacy data.

### What to do

Switch the corpus smoke test to the new arc/connection data in
`Ontology_Repository/processes_distributed_no_interface_eqs/variableExpression.trig`
(or the canonical v9 TriG file).  Update `RdfContext` to read all named
graphs and lowercase `promo:variable` / `promo:index` types so it can
consume the new TriG directly.  Once that is in place, these three legacy
failures should disappear.

## 6. FastAPI endpoint dependencies

`backend/equation/service.py` declares ``POST /api/equation/parse`` and
``POST /api/equation/check``.  The endpoints are importable and tested with
stubs.  FastAPI/uvicorn are installed in `.venv`; the server starts and
`/api/health` returns `{"status":"ok"}`.

## Files involved

- `backend/equation/checker.py`
- `backend/equation/compile_space.py`
- `backend/equation/parser.py`
- `backend/equation/test_corpus.py`
- `backend/equation/service.py`
- ProMo13 source: `packages/Common/ontologies/var_equ_rdf.ttl`
