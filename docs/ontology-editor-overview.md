# Ontology Editor Overview

## Role in the suite

The Ontology Editor is the source of truth for all downstream
vocabulary.  It defines the **framework** within which variables and
equations are later authored: the domain tree, tokens, classification
axes, scales, entity types, connection rules, indices, and abstract
graphical symbols.  It is the first module in the pipeline.

Variables and equations are authored in the **Equation Editor**, not
here.  See `docs/ontology-design-discussion-2026-09-11.md` for the
full design discussion, including the staged workflow and the
three-level graphics model.

See `docs/suite-overview.md` for the full pipeline and cross-cutting
contracts.

## Consumes

- Nothing upstream — it is the origin of ontology definitions.
- External ontologies (QUDT for quantities, units, dimensions) may be
  referenced but are not edited here.

## Produces

- **Ontology named graph** (versioned, RDF) containing:
  - Domain tree (`promo:Network` resources with `promo:parent` edges).
  - Tokens (`promo:Token` with hierarchy via `promo:parent`).
  - Classification axes + terms (per-domain, hierarchical, for
    variable classification).
  - Scale dimensions + values (time scale, length scale,
    user-defined; for entity type composition).
  - Entity types (compositions of scale values; CWA 17960
    temporal×spatial as a seed/default, not a hardcoded schema).
  - Connection rules (3 types: same-domain physical, cross-domain
    physical, signal).
  - Indices (`promo:Index` with IRI, label, token binding, network).
  - Abstract graphical symbols (level-1 graphics: sketchable glyphs
    for paper/pencil work; part of the visual language definition).
  - Ontology version metadata.

**Not** produced here:
- Variables and equations — authored in the Equation Editor.
- Concrete base graphics (level 2) — assigned by the Behaviour Linker.
- Composite/tailored graphics (level 3) — authored in the Modeller.
- Glasses (domain-specific visual skins) — separate artefact,
  separate authoring, separate named graph.

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

The editor uses a **staged workflow** that respects dependencies between
ontology elements:

1. Tokens — no dependencies
2. Domains — depend on tokens
3. Classification axes + terms — per domain, for variable classification
4. Scale dimensions + values — time scale, length scale, user-defined
5. Entity types — compositions of scale values
6. Indices — reference tokens + domains
7. Connection rules — reference domains + tokens (come last)

Each stage provides full CRUD for its element type.  Later stages become
available once their prerequisites exist.

## Interaction with other modules

- **Sends to Equation Editor:** tokens, indices, domain tree, and
  classification axes via `EquationContext` protocol (read-only
  snapshot; variables and equations are authored in the Equation
  Editor, not here).
- **Sends to Behaviour Linker:** entity types, connection rules,
  abstract graphical symbols (level 1), and ontology vocabulary for
  entity behaviour definitions.
- **Sends to Modeller:** entity types, connection rules via
  `SemanticCatalogue` / `ConnectionRuleResolver`.
- Glasses (domain-specific visual skins) are a **separate artefact**,
  not produced by the Ontology Editor.  See `docs/ontology-design-discussion-2026-09-11.md` §19–21.

## What is NOT authored here

- **Variables and equations** — authored in the Equation Editor.
- **Empirical / user-function equations** — registered by signature and
  linked to an external implementation (e.g. Peng–Robinson EOS).
- **Arcs** — arcs are model-level (flowsheet connections), not
  ontology-level.  Physical domain arcs are continuity conditions
  expressed as equations; the actual graph connections are drawn in the
  Modeller.
- **Concrete base graphics (level 2)** — assigned by the Behaviour
  Linker.
- **Composite/tailored graphics (level 3)** — authored in the Modeller.
- **Glasses** — domain-specific visual skins; separate artefact,
  separate authoring, separate named graph.
