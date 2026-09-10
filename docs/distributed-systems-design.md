# Distributed Systems and Meshing — Design Concept

**Status:** Future concept — not yet implemented or fully designed.

## Idea

Distributed systems described by partial differential equations (PDEs)
are first-class entities in the suite.  They are defined upstream
(ontology, equation editor, behaviour linker) and composable in the
modeller alongside lumped and event-dynamic systems.  Before numerical
code generation, a **meshing operation** discretises the spatial domain
of each distributed system and maps it into a network of coupled lumped
systems.  After meshing, everything is lumped and goes through normal
code generation.

## Pipeline position

```
... → Modeller → Model Reuse → Instantiation
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
              lumped/event    distributed      distributed
                    │               │               │
                    │          meshing op      meshing op
                    │               │               │
                    │          lumped network   lumped network
                    │               │               │
                    └───────┬───────┘───────────────┘
                            │
                     Code Generation
```

Meshing sits after instantiation (parameters and geometry must be
concrete) and before code generation.  Lumped and event-dynamic systems
skip meshing and go directly to code generation.

## Why this works with the existing architecture

- **Equation editor already has spatial operators.** `TotalDiff`,
  `ParDiff`, `diffSpace` — the spatial differential index is in the
  language.  PDEs are expressions with spatial differential operators
  over a spatial domain.
- **Modeller stays generic.** A distributed system is a base entity
  with spatial extent and boundary interfaces.  The modeller connects
  boundaries the same way it connects lumped ports.
- **Meshing output is a standard model.** After discretisation, the
  result is a flat RDF topology + hierarchy of lumped nodes — exactly
  what the modeller already produces.
- **Event dynamics stays lumped.** Meshing resolves only the spatial
  dimension; temporal event dynamics are handled at the lumped level
  after meshing.

## Open questions

1. **Ontology vocabulary:** Entity types for distributed systems,
   spatial domain descriptions, boundary condition types, mesh
   parameters.
2. **Equation editor:** Does it need to know an equation is a PDE, or
   is the presence of a `diffSpace` index sufficient signal?
3. **Behaviour linker:** How to describe boundary I/O behaviour of
   distributed entities — which variables are exposed at which
   boundaries.
4. **Meshing module:** Mesh specification (scheme, resolution, element
   type), mapping from PDE operators to lumped equations (finite
   volume, finite element, finite difference), output topology +
   hierarchy.
5. **Mesh resolution timing:** Is mesh resolution chosen at
   instantiation time or at code-generation time?
6. **Hybrid models:** A model may mix lumped, event-dynamic, and
   distributed subsystems.  Meshing must identify and transform only
   the distributed subgraphs.
7. **Provenance:** Meshed models should record origin (distributed
   system), mesh scheme, and version — same provenance pattern as model
   reuse.
