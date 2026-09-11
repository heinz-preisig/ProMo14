# Ontology Design Discussion — 2026-09-11

**Status:** In-progress design discussion.  Captures decisions and open
questions from the 2026-09-11 session.  These will be folded into the
ontology editor design docs once finalised.

## Context

After archiving the legacy corpus test and cleaning up the repository,
the session pivoted to a design discussion for the ontology editor.  The
goal is to define what the ontology contains and how it is structured
before building the editor frontend.

## Key decisions

### 1. Two-branch ontology structure

The ontology has two branches:

**Structure branch** — *what exists in a domain*
- A domain is implicitly defined by which tokens live in it (mass,
  energy, momentum, charge, species, signal, ...).
- Structural elements: nodes, arcs, tokens, conversion, signals.
- Each structural element can give rise to indices (see §2).

**Behaviour branch** — *how things behave in a domain*
- Defines variable classes (state, effort, transport, ...) for each
  structural element and domain/subdomain.
- **Inheritance applies**: a subdomain inherits variable classes from
  its parent domain and may add or specialise them.
- E.g. `thermo` defines `state` and `effort`; `liquid` (child of
  `thermo`) inherits both and may add `transport`.

The domain tree serves both branches:
- **Structurally**: a domain is characterised by its tokens.
- **Behaviourally**: variable classes are defined per domain with
  inheritance down the tree.

### 2. Index sources

Indices arise from multiple structural elements, not just tokens:

- **Nodes** — spatial discretisation or network topology (node 1, 2, … N).
- **Arcs** — connections between nodes (arc indices for
  incidence/adjacency).
- **Tokens** — physical quantities carried by the system (species,
  mass, energy, momentum, charge).
- **Conversion** — transformation processes (e.g. reaction → product).
- **Signals** — information/control quantities.  Kept as a single
  category without sub-refinement for now.  The token hierarchy
  (`promo:parent`) allows refinement later without schema changes.

An index is essentially "what does this dimension enumerate?" — and the
answer can be a structural element (node/arc), a physical quantity
(token), a process (conversion), or an information quantity (signal).

### 3. Two arc types

**Physical arcs** — bidirectional
- Continuity conditions on flow and effort variables.
- Closely tied together (flow and effort are coupled).
- Both sides of the connection are equal partners.

**Information arcs** — unidirectional
- Output of one function is input to the next.
- Directly uses the corresponding variable (no continuity condition).
- Direction matters: source → target.

**Cross-domain interaction** (information → physical)
- Information inputs can manipulate physical flows (e.g. valves).
- Observations are done by something like an instrument (physical →
  information).
- This is an exception to the pure bidirectional/unidirectional split
  and crosses domain boundaries.

### 4. Domain tree dual role

The domain tree has two roles:

- **Semantic** — different top-level domains (physical vs control vs
  information) have different tokens and physics.  These are
  fundamentally different kinds of systems.
- **Structural** — subdomains within one physics domain share the same
  physical properties (same tokens, same variable classes).  The
  subdivision is mainly organisational and may provide a frame for
  special equations (e.g. boundary conditions, interface equations).

### 5. Arcs are model-level, not ontology-level

Arcs are not defined in the ontology editor.  Physical domain arcs
(continuity conditions) and information flow arcs (output = input) are
expressed as equations in the equation editor.  The actual graph
connections are drawn in the Modeller, which generates the linking
equations.  The ontology editor only needs to know which variable
classes / tokens can carry a flow.

## Open questions

1. **Variable classes per structural element** — does the behaviour
   branch define variable classes separately for nodes vs arcs?  For
   example, in a physical domain, a node might have `state` and `effort`
   variables, while an arc might have `transport` and `flow` variables.

2. **Structure ↔ behaviour interaction** — does the structure branch
   constrain the behaviour branch?  I.e. do the tokens present in a
   domain determine *which* variable classes are meaningful?  For
   example, if a domain has `mass` and `energy` tokens, then `state`,
   `effort`, and `transport` variable classes make sense, but if a
   domain only has `signal`, then only `state` and `input`/`output` make
   sense.

3. **Node/arc indices: structural (model-level) or ontological?** — a
   spatial node index (`N`) exists once the mesh is defined — that is
   model-level.  But the concept "a network has nodes" seems
   ontological.  Where is the line?

4. **Time** — is time an index, or is it handled differently (as the
   integration variable, not a structural index)?

5. **Entity types** — the existing design docs say the ontology editor
   sends "entity types, arc types, connection rules" to the Modeller,
   but there is no UI or data model for authoring entity types.  Are
   entity types defined in the ontology editor, or created by the
   Behaviour Linker?  This connects to the open question: "Is the
   assignment tool the Behaviour Linker, or a separate step?"

6. **Variable class vocabularies per domain type** — the docs list
   `state`, `effort`, `transport`, `frame`, `network` as variable
   classes but never map them to domain types.  Physical domains
   (tokens + state) vs control/information domains (structural,
   functional, scope, temporal criteria) likely need different
   variable class vocabularies.
