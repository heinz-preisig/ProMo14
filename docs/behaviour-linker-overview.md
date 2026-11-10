# Behaviour Linker Overview

> **Superseded:** this predates the §1–§33 design work.  The living
> docs are `behaviour-linker-status.md` (implementation state) and
> `behaviour-linker-design-discussion.md` (rulings); kept as the
> pre-design record — banner added 2026-11-10.

## Role in the suite

The Behaviour Linker selects which equations describe the input/output
behaviour of a base entity and assigns its graphical representation.  It
is the bridge between mathematical definitions (from the Equation
Editor) and the graphical model composition (in the Modeller).

See `docs/suite-overview.md` for the full pipeline and cross-cutting
contracts.

## Consumes

- **Var/expr knowledge graph** from the Equation Editor — checked
  variables, equations, index structures, token sequences.
- **Ontology** from the Ontology Editor — domain tree, variable types,
  token types, entity types, arc types.

## Produces

- **Base-entity definitions** — for each entity:
  - Semantic identity (IRI), domain, tokens.
  - Selected equations describing I/O behaviour (which equations apply,
    which variables are inputs, which are outputs).
  - Graphical definition (shape, fill, stroke, ports, labels) —
    assigned via the Graphic Object Editor.
  - Connection rules (which entity types may connect via which arc
    types).

## Key concepts

### I/O behaviour selection

A base entity may have multiple defining equations (ADR-005: variables
with multiple equations are real — selection is a modelling decision).
The Behaviour Linker is where the user selects which equations describe
the entity's input/output behaviour for a given modelling context.

### Graphical assignment

The Behaviour Linker spawns the **Graphic Object Editor** — the same
editor the Modeller uses for composite graphical assignment (ADR-004
§5).  The editor receives the target entity as context and returns its
graphical-definition assignment.  Both entry points use the same
graphical vocabulary and persistence format.

### Arcs as equations

*Superseded model (banner 2026-11-10):* physical domain arcs
(continuity conditions) and information flow arcs (output = input)
were meant to be expressed as equations.  Under §13 the arc *is* the
boundary coupling — it carries no equations; the coupling is the
shared variable itself.

## Design status

*As of writing:* not yet designed in detail — the role is defined in
ADR-004, but the workflow, UI, and data contracts have not been
specified.  **Superseded:** the design is resolved through
`behaviour-linker-design-discussion.md` §1–33 (move-based closure
engine landed 2026-10-28; strict-boundary and §33 rulings
2026-11-08/10) — banner 2026-11-10.

## Interaction with other modules

- **Receives from:** Equation Editor (var/expr graph), Ontology Editor
  (vocabulary, entity types).
- **Sends to:** Modeller (base-entity catalogue with graphical
  assignments and connection rules via `SemanticCatalogue` /
  `ConnectionRuleResolver`).
- **Spawns:** Graphic Object Editor (shared with Modeller).

## Open design questions

1. What is the workflow for selecting I/O behaviour equations?
2. How are input/output variables identified and exposed as interfaces?
3. What is the data format for graphical-definition assignments?
4. How are connection rules defined — per entity type pair, or per
   domain/token combination?
5. How does the Behaviour Linker interact with the ontology graph store?
