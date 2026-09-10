# ADR-006: Ontology Evolution — What May Change and What It Costs

## Status

Draft — extends ADR-004 (model architecture) and ADR-005 (equation editor).

## Context

The suite pipeline is:

```
Ontology Editor → Equation Editor → Behaviour Linker → Modeller → Instantiation → Codegen
```

Everything downstream *consumes* ontology definitions: indices, variable
types, domains/networks, token types, entity and arc types, connection rules,
graphical definitions. The equation editor's semantic checks (units, index
structures, variable resolution) are only meaningful against a fixed
vocabulary — the ADR-005 publish–consume contract says a checked expression is
trusted, which presumes the vocabulary it was checked against is stable.

ProMo13 allowed *expanding* the ontology but not *modifying* it, and it let the
equation editor mint indices on the fly (`diffSpace`, `MakeIndex` in
`variable_framework.py`). That loophole is closed: index creation moves up into
the ontology editor, so the index set is frozen by the time equations are
authored.

The open question is what happens when the ontology *does* change after
variables, equations, and models already reference it. Do we have to throw the
var/expr graph away? No — provided changes are classified and references are
by IRI.

## Decision

### 1. Ontology resources are IRI-identified and immutable within a version

Every ontology resource — index, variable type, domain, token type, entity
type, arc type, connection rule, graphical definition — is a resource with a
stable IRI inside a **versioned named graph**. A published ontology graph is
never edited in place; evolution produces a new named graph (new version).

Each authored artefact (var/expr graph, model graph) records which ontology
graph it was checked against, e.g. `promo:checkedAgainst <ontology-graph-iri>`.
This is the same pattern ADR-005 already uses for published domain sets.

### 2. Change classification

Not all "changes" are equal. The editor enforces different rules per class:

| Change | Examples | Allowed? | Consequence |
|--------|----------|----------|-------------|
| **Additive** | new index, new variable type, new domain, new token type, new entity/arc type, new rule | always | none — existing graphs don't reference the new resource |
| **Annotation** | label, doc, graphical definition, alias | always | display-only; see §3 on labels |
| **Deprecation** | mark resource `owl:deprecated` / `promo:deprecatedBy` | always | hidden from new authoring; existing references still resolve |
| **Semantic modification** | retype a variable type, change a domain's token set, change an index's carried token, edit a connection rule, change type hierarchy | only in a new version | triggers re-validation of dependent graphs (§4) |
| **Deletion** | remove a resource | only if unreferenced | if referenced: blocked, or explicit migration with a cascade report |

### 3. Labels are annotations; IRIs are identity

Renaming a domain or variable type changes its *label*, not its IRI. Stored
artefacts survive because they reference IRIs:

- Equations are stored as **token sequences of IRIs** (ADR-005), so a renamed
  domain does not break a stored expression.
- The **source string** (`network!label`) may no longer resolve after a label
  rename. Re-parsing the source against the new ontology can fail or resolve
  differently. Mitigation: keep the token list authoritative; treat the source
  string as regenerable display text, or run a re-resolution pass that rewrites
  labels via the stored IRIs.

### 4. Semantic modifications require re-validation, never silent drift

When a new ontology version changes semantics, dependent graphs are re-checked:

- **Variable types.** Retyping a *variable* is a model edit, not an ontology
  edit — allowed, but it re-triggers the variable's checks (e.g. the old RULE
  that state variables cannot be deleted). Changing the *type vocabulary* or
  hierarchy is a semantic change: rules that dispatch on type (deletion rules,
  codegen ordering, connection rules) may yield different results, so affected
  graphs are flagged for re-validation.
- **Domains/networks.** Merging, splitting, or moving variables between
  networks changes the accessible-name-space resolution (the local-first /
  globally-unique / `network!label` rule). A previously unique label can become
  ambiguous. Re-resolution runs over stored token IRIs; conflicts surface as a
  migration report, not silent re-binding.
- **Token types and connection rules.** Changing token sets or rules does not
  alter stored topology, but existing arcs/interfaces may no longer be valid.
  Re-validation marks now-invalid arcs; the user resolves them. Nothing is
  deleted automatically.
- **Indices.** Frozen at editor level; additive only. `diffSpace` no longer
  mints indices — the spatial differential index must be pre-declared per
  network in the ontology. A needed-but-missing index is an ontology edit, not
  an equation edit.

### 5. Migration path

- `promo:deprecatedBy` / `promo:replaces` links point old resource → new
  resource, so a migration tool can offer to re-point references.
- A model that fails re-validation stays pinned to its declared
  `checkedAgainst` version until the user migrates. Old ontology versions
  remain loadable — that is what named graphs are for.
- Deleting a referenced resource is a two-step explicit operation: the tool
  lists all referencing variables/equations/arcs (the cascade), the user
  confirms or cancels. There is no silent cascade.

### 6. What this means for the equation-editor port

- `CompileSpace` receives a **read-only** index/variable/type context built
  from a specific ontology graph. No code path in the checker may add an index
  or variable type.
- `diffSpace` checks that the argument carries the pre-declared differential
  index; `MakeIndex` is dropped entirely.
- `newTemp` still allocates temp variables, but through the backend ID
  allocator (`promo:nextVariableID`), not a local counter — temp IDs live in
  the var/expr graph, not the ontology.

## Consequences

- The ontology editor becomes the single place where vocabulary is created;
  it needs "add / annotate / deprecate / new-version" operations and a
  reference-count check before deletion.
- Re-validation is a batch job over stored IRIs — the same checker the editor
  uses, run headless. No separate migration verifier is needed.
- The answer to "do we delete the var/expr graph?" is no for every change
  class except an explicitly confirmed cascade. Worst case is a pinned old
  version plus a migration report.
- Cross-graph equivalence (`promo:equivalentTo`, ADR-005) is unaffected — it
  is asserted between graphs, and ontology versioning adds a second dimension
  (same resource, different version) that equivalence arcs may also span.

## Open questions

1. Version granularity: one version per published ontology graph, or per
   release bundle of several graphs?
2. Should `promo:checkedAgainst` live on the graph resource, or on each
   equation/variable individually (finer-grained but noisier)?
3. Deprecation UX: hide deprecated resources entirely, or show them greyed
   with a "still used by N artefacts" badge?
4. When a domain is split, do variables keep their IRIs and only change
   `promo:network`, or are they re-minted? (Keeping IRIs preserves expression
   token lists; re-minting is cleaner semantically but breaks references.)
