# Behaviour Linker — Implementation Status

**Last updated:** 2026-09-10

## Current state

Not started.  Backend and frontend are empty scaffolds.  Design is TBD.

## Backend

`backend/behaviour/` — empty scaffold.

## Frontend

`apps/behaviour-linker/` — empty scaffold.

## Design

Role is defined in ADR-004 (selects equations for I/O behaviour,
assigns graphical representation, spawns Graphic Object Editor).  No
detailed design document exists yet.

## Pending items

1. Define the behaviour-linking workflow.
2. Specify the data contract for base-entity definitions (behaviour +
   graphical assignments + connection rules).
3. Design the graphical assignment interaction (Graphic Object Editor).
4. Specify how connection rules are authored.
5. Implement backend service.
6. Build frontend.

## Dependencies

- Equation Editor backend (for equation data).
- Ontology Editor (for vocabulary and entity types).
- Graphic Object Editor (shared component, not yet built).
