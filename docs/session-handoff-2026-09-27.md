# Session handoff — 2026-09-27

State of the ProMo14 workspace at end of session. Branch `main`, remote `heinz-preisig/ProMo14`. Supersedes `session-handoff-2026-09-26.md`.

**On the other machine:** run `./dev.sh sync`. Backend and tracked `data/` changed; no frontend source changed in this commit. Do not use `wipe-restart`; `data/` remains the sync channel.

## Tomorrow, first decision

Resolve the indexed `inv` semantics before further equation cleanup.

- Current rule: `inv` is **scalar reciprocal**. `checker.py` rejects any indexed argument (`inv(V[N])`, `inv(rho[N])`).
- Intended library semantics appear to be **elementwise reciprocal**: `inv(V) . n` should mean `(1 / V_i) * n_i` (or the indexed analogue for the actual operand structures), preserving `N`.
- Decide whether `inv` becomes index-preserving (`inv(x[N]) -> [N]`) or whether a distinct operation name is needed for elementwise inverse.
- If changed, update `checker.py`, canonical operation coverage if required, codegen/tests/docs, then reload and save the store so the remaining literal-only equations can migrate.
- Separately, migrate stale `root!` qualifiers inside legacy source text to `universe!` (or teach resolution that `root` aliases `universe`). `root!half` currently fails even though `half` is seeded on `universe`.

## What landed today

### Canonical expression model

- `backend/equation/canonical.py` now defines immutable canonical arguments:
  - `Expression(operation_iri, ordered arguments)`
  - `VariableReference(iri)`
  - `IndexReference(iri)`
- Operation argument kinds are declared and recursively validated.
- Checked trees convert to canonical form with IRI-bound variable/index references.
- Canonical trees regenerate source from current labels and network qualifiers.

### Canonical RDF persistence

- New `backend/equation/canonical_rdf.py` stores equations as semantic RDF:
  - equation `promo:rhsExpression` → root expression/reference
  - `rdf:type promo:Expression`
  - `promo:hasOperation` → `promolg:` operation IRI
  - `promo:hasArguments` → ordered RDF list
- Variable/index arguments reference their entity IRIs directly; nested expressions use blank nodes.
- `promo:rhs` remains a regenerated compatibility source cache.
- `RdfContext` reads canonical RHS as authoritative and regenerates source from current labels. Malformed or missing canonical trees fall back to `promo:rhs`.

### Save/load integration

- `POST`/`PUT /api/equation/variables` canonicalise each successfully checked RHS before writing.
- Canonical RDF is attached after `add_variable_dict`; incidence and LaTeX caches are refreshed from the checked tree.
- Domain-move rewrites update `promo:rhs`, incidence, LaTeX, and the canonical subtree together.
- Variable replacement/delete clears canonical expression subgraphs before removing equation nodes.
- Uncheckable source is still stored literal-only; this preserves legacy data while making valid equations semantic.

### Automatic data migration

- `RdfStore.load()` now runs `_migrate_canonical_rhs()` after equation IRI and domain migrations.
- Each literal-only equation is parsed/checked in its graph's `usesOntology` resolution scope.
- Successful migration writes `promo:rhsExpression` and refreshes `promo:rhs`, `promo:incidenceList`, and `promo:rhsLatex`.
- Migration is idempotent and best-effort: uncheckable equations remain literal-only.
- The running backend was saved with `POST /api/ontology/save`.

## Actual migration result

- `data/ontology.trig`: **9/9 equations canonical**
- `data/library.trig`: **5/10 equations canonical**
- Remaining literal-only equations:
  - `E_10`: `inv(V) . n` — `V` is indexed by `N`; current `inv` is scalar-only.
  - `E_12`: contains stale qualifier `root!half`; `half` is now on `universe`.
  - `E_13`: `Instantiate(n)` — LHS `no` remains class `state`, but `Instantiate` requires `constant` or `parameter`.
  - `E_14`: `inv(V) . m` — indexed `V` under scalar-only `inv`.
  - `E_15`: `inv(rho) . ...` — indexed `rho` under scalar-only `inv`.

## State

- Backend suite: **361 tests passed** (`uv run python -m pytest backend -q`)
- Equation backend suite: **190 tests passed**
- Canonical/migration focused suite: **33 tests passed**
- `git diff --check`: clean
- Store after save: `dirty=false`
- Documentation updated: `docs/equation-editor-status.md`, this handoff.

## Important files

- `backend/equation/canonical.py` — canonical model, typed signatures, conversion, source regeneration.
- `backend/equation/canonical_rdf.py` — semantic RDF serializer/deserializer and subtree cleanup.
- `backend/equation/service.py` — save/update/domain-move integration.
- `backend/ontology/rdf_context.py` — authoritative canonical reads and source regeneration.
- `backend/core/persistence.py` — load-time canonical migration.
- `backend/equation/test_canonical_rdf.py` — RDF round-trip and validation tests.
- `backend/core/test_graph_store.py` — migration success/fallback/idempotency tests.
- `backend/equation/test_mutability.py` — save/load authoritative-cache regression.
- `data/ontology.trig`, `data/library.trig` — migrated persisted artefacts.

## Deferred / next review

- Indexed `inv` semantics (first item tomorrow).
- `root!` → `universe!` source-qualifier migration or alias.
- Reclassify `no` to `constant`/`parameter` if `Instantiate(n)` is intended.
- Once resolved, rerun backend load + save and verify no literal-only equations remain.
- Existing functional priorities remain unchanged: value-cell/codegen wiring, value-cell editor UI, reaction-domain equations, SHACL at publish, behaviour-linker UI, and multi-pin `usesSpecies`.
