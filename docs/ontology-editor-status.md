# Ontology Editor — Implementation Status

**Last updated:** 2026-09-10

## Current state

Design complete.  No implementation yet — backend and frontend are
empty scaffolds.

## Design

| Document | Content |
|----------|---------|
| `docs/ontology-editor-design.md` | UI layout, variable table, detail editor, equation editor integration, user function registration |
| `docs/ontology-data-model.md` | RDF schema for variables, indices, equations, tokens, domain tree; loader contract |
| `docs/ADR-006-ontology-evolution.md` | Versioning, change classification, migration rules |
| `docs/equation-context-contract.md` | `EquationContext` protocol (the seam to the equation editor) |

## Backend

`backend/ontology/` — empty scaffold.

### Planned backend

- RDF graph store (rdflib or persistent triple store).
- `RdfContext` provider implementing `EquationContext` — loads
  variables, indices, and domain tree from a named graph.
- CRUD operations for variables, indices, tokens, networks, equations.
- Versioning: create new named graph on semantic changes; additive
  changes within a version.
- Reference-count check before deletion (cascade report).

## Frontend

`apps/ontology-editor/` — empty scaffold.

### Planned frontend

- React with Tailwind or shadcn/ui.
- Three-pane layout: domain tree, variable table, detail editor.
- TanStack Table for sort/filter/selection.
- Equation editor integration (modal/inline) for core equations.
- User function registration dialog.
- Publication exports (LaTeX, variable table, domain tree diagram).

## Pending items

1. Implement backend graph store and `RdfContext` provider.
2. Build frontend domain tree pane.
3. Build variable table with filtering.
4. Build detail/editor pane with tabs (identity, domain, semantics,
   indices, equations).
5. Integrate equation editor for equation authoring.
6. Implement ontology versioning and change classification.
7. Add publication export functionality.

## Dependencies

- Equation editor backend (for equation checking within the ontology
  editor).
- `backend/core` shared services (RDF store, IRI minting).
