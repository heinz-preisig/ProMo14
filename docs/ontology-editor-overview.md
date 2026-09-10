# Ontology Editor Overview

## Role in the suite

The Ontology Editor is the source of truth for all downstream
vocabulary.  It defines the domain tree (networks), variables, indices,
tokens, and core equations that every other module consumes.  It is the
first module in the pipeline.

See `docs/suite-overview.md` for the full pipeline and cross-cutting
contracts.

## Consumes

- Nothing upstream — it is the origin of ontology definitions.
- External ontologies (QUDT for quantities, units, dimensions) may be
  referenced but are not edited here.

## Produces

- **Ontology named graph** (versioned, RDF) containing:
  - Domain tree (`promo:Network` resources with `promo:parent` edges).
  - Variables (`promo:Variable` with IRI, label, units, index
    structures, tokens, network, aliases).
  - Indices (`promo:Index` with IRI, label, token binding, network).
  - Tokens (`promo:Token` with hierarchy via `promo:parent`).
  - Core equations (`promo:Equation` with LHS, RHS token sequence,
    incidence list, equation class, network).
  - Ontology version metadata.

## Key design decisions

| Decision | ADR / doc | Summary |
|----------|-----------|---------|
| IRI-identified, immutable resources | ADR-006 | Resources are stable within a version; evolution creates new versions. |
| Versioned named graphs | ADR-006 | Published ontology is never edited in place; new version = new graph. |
| Change classification | ADR-006 | Additive, annotation, deprecation always allowed; semantic modification only in new version; deletion requires cascade check. |
| Labels are annotations | ADR-006 | Renaming changes label, not IRI; stored artefacts survive via IRI references. |
| Indices frozen at editor level | ADR-006 | No more `diffSpace`/`MakeIndex` in the equation editor; indices pre-declared per network. |
| `EquationContext` as seam | `equation-context-contract.md` | Equation editor consumes a read-only snapshot; provider implementation can change. |
| Units: both SI vector and QUDT IRI | `ontology-data-model.md` | Vector for checking; IRI for semantic identity. |

## Domain tree

The domain tree is a rooted hierarchy of networks (also called
domains).  Each network represents a physical domain or modelling level.

```
root
└── physical
    ├── macroscopic
    ├── microscopic
    │   └── reactions
    ├── thermo
    │   ├── liquid
    │   └── gas
    └── energy
```

The tree determines **accessible networks** for expression authoring:
variables defined in a network are visible from all its descendants.

## Data model

Full RDF schema for variables, indices, equations, tokens, and the
domain tree: see `docs/ontology-data-model.md`.

## UI design

Full layout and workflow design: see `docs/ontology-editor-design.md`.

Three-pane layout:
- **Left:** domain tree (editable, drag-drop).
- **Center:** variable table (filtered by selected domain).
- **Right:** detail/editor pane (identity, domain, semantics, indices,
  equations).

Equation editing within the ontology editor launches the Equation
Editor (modal/inline) with the selected variable as LHS and the active
network as context.

## Interaction with other modules

- **Sends to Equation Editor:** variables, indices, domain tree via
  `EquationContext` protocol.
- **Sends to Modeller:** entity types, arc types, connection rules,
  graphical definitions via `SemanticCatalogue` / `ConnectionRuleResolver`.
- **Sends to Behaviour Linker:** ontology vocabulary for entity
  behaviour definitions.
- **Receives from Equation Editor:** checked equations are written back
  into the ontology named graph.

## What is NOT authored here

- **Empirical / user-function equations** — registered by signature and
  linked to an external implementation (e.g. Peng–Robinson EOS).
- **Arcs** — arcs are model-level (flowsheet connections), not
  ontology-level.  Physical domain arcs are continuity conditions
  expressed as equations; the actual graph connections are drawn in the
  Modeller.
