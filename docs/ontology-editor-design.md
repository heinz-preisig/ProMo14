# Ontology Editor Design

A web-based ontology editor for ProMo14.  It defines the **framework**
within which variables and equations are later authored: the domain
tree, tokens, classification axes, scales, entity types, connection
rules, indices, and abstract graphical symbols.

Variables and equations are **not** authored here — they are authored
in the Equation Editor.  See `docs/ontology-design-discussion-2026-09-11.md`
for the full design discussion.

## Scope

Managed in the ontology editor:

- **Tokens** — token types and their hierarchy.
- **Domain tree** (networks) — hierarchy of physical and information
  domains, defined by which tokens live in them.
- **Classification axes + terms** — per-domain, hierarchical, for
  variable classification (role, extensivity, origin, ...).
- **Scale dimensions + values** — time scale, length scale, and
  user-defined; for entity type composition.
- **Entity types** — compositions of scale values.  CWA 17960's
  temporal×spatial is a seed/default, not a hardcoded schema.
- **Connection rules** — 3 types: same-domain physical, cross-domain
  physical, signal.
- **Indices** — index definitions, aliases, and token bindings.
- **Abstract graphical symbols** — level-1 graphics: sketchable glyphs
  for paper/pencil work, part of the visual language definition.

**Not** authored in the ontology editor:

- **Variables and equations** — authored in the Equation Editor.
- **Empirical / user-function equations** — registered by signature
  and linked to an external implementation.
- **Concrete base graphics (level 2)** — assigned by the Behaviour
  Linker.
- **Composite / tailored graphics (level 3)** — authored in the
  Modeller.
- **Glasses** — domain-specific visual skins; separate artefact,
  separate authoring, separate named graph.
- **Arcs** — model-level (flowsheet connections), not ontology-level.

## Staged workflow

The editor uses a **staged workflow** that respects dependencies between
ontology elements.  Each stage provides full CRUD (create, read,
update, delete) for its element type.  Later stages become available
once their prerequisites exist.

### Stage 1: Tokens

No dependencies.  Tokens are the fundamental building blocks.

- Token hierarchy (`promo:Token` with `promo:parent`).
- Each token has IRI, label, internal_id, aliases, and optional
  parent.
- Physical tokens: mass, energy, momentum, charge, species, ...
- Information tokens: signal, ...
- Token hierarchy allows refinement (e.g. `mass` -> `species A/B/C`).

### Stage 2: Domains

Depend on tokens.  A domain is implicitly defined by which tokens live
in it.

- Domain tree (`promo:Network` with `promo:parent` edges).
- Two main branches: **physical** (conserved/balanced quantities) and
  **information** (elementary information pieces).
- Each domain has IRI, label, parent, and associated tokens.
- Subdomains inherit tokens from parent domains and may add new ones.
- Selecting a domain sets `accessible_networks` context for the
  equation editor.

### Stage 3: Classification axes + terms

Depend on domains.  Per-domain with inheritance.

- Each axis is a hierarchical tree of terms (not a flat enum).
- Variable class dissolves into one axis ("role") among several.
- Example axes (thermo/transport domain): role (state, effort,
  transport, ...), extensivity (extensive, intensive), origin
  (fundamental, derived).
- Axes are domain-dependent: thermo has role/extensivity/origin;
  molecular modelling has positions/momenta/forces; mechanical/fluid
  has stress/strain rate.
- Subdomains inherit axes from parent domains and may add terms.
- Tagging is the primary mechanism; optional user-defined validation
  rules.
- Inferred defaults reduce clicking: domain defaults, equation class
  inference, token binding inference, bulk tagging.

### Stage 4: Scale dimensions + values

Depend on domains (scales are per-domain).  No dependency on axes
(scales classify base entities, not variables).

- Scale dimensions: time scale, length scale, and user-defined.
- Each dimension has a hierarchical tree of values.
- **The temporal triple domain lives within the time scale as child
  values of each scale level.**  Each time scale level (e.g.
  molecular, nano, milli, macro) has three children: constant,
  dynamic, event-dynamic.
- **Multi-scale stacking:** the lower scale's constant becomes the
  larger scale's event-dynamic.  This is encoded in the hierarchy:
  `molecular/constant` is a child of `molecular`; at `nano` scale,
  `molecular/constant` appears as instantaneous (= event-dynamic).
- Length scale levels (infinitesimal, microscopic, macroscopic,
  infinite) each have spatial sub-values (point/finite, uniform/
  distributed).
- CWA 17960's temporal x spatial is a seed/default, not a schema.
- Scale values are seeds — user can rename, restructure, add, or
  delete levels and children.
- Entity types (stage 5) are compositions of fine-grained scale
  values (e.g. `macro/dynamic` + `macroscopic/uniform`).

See `docs/ontology-design-discussion-2026-09-11.md` section 25.

### Stage 5: Entity types

Depend on scales.  Entity types are pure compositions of fine-grained
scale values.

- Each entity type references one or more scale values (e.g.
  `macro/dynamic` for time + `macroscopic/uniform` for length).
- The legacy `temporal_type` / `spatial_type` / `spatial_size` fields
  are kept for backward compat but the canonical definition is the
  scale value composition.
- CWA 17960's 5 physical capacity types and 3 information capacity
  types are a seed/default set, not a hardcoded schema.
- The ontology editor authors the taxonomy; the Behaviour Linker
  assigns a specific scale level to a base entity.
- Special cases: point system (zero-size, reactions), phase
  interface / intraface (zero-size, no reactions, arc element).
- Transport system is a **node** (event-dynamic distributed), not an
  arc.  Arcs are only intrafaces (continuity conditions).
- Entity types carry abstract graphical symbols (level-1 graphics).
- Multi-scale models: a model contains entities at different scale
  levels, connected by arcs.  The ontology allows this; the
  Behaviour Linker and code generation handle the mathematics.

### Stage 6: Indices

Depend on tokens + domains.

- Each index has IRI, label, short_name, aliases, network,
  index_class, and token binding.
- Index sources: nodes, arcs, tokens, conversion, signals.
- `differential_space` is an index like any other.
- Indices are ontological (concept); specific count is model-level.

### Stage 7: Connection rules

Depend on domains + tokens.  Come last.

- Rule type 1: same domain, shared tokens -> physical arc
  (bidirectional, continuity).
- Rule type 2: different physical domains, shared tokens -> physical
  arc (bidirectional, continuity).
- Rule type 3: signal connections -> information arc (unidirectional):
  physical->info (observation), info->physical (manipulated variable),
  within info domain, within physical domain (token signal).
- Continuity is token-specific: an arc carries continuity only for
  tokens shared by both connected nodes.

## Abstract graphical symbols (level-1 graphics)

Every ontology entity gets a graphical representation — not just
nodes and arcs, but tokens, domains, scales, entity types, connection
rules.  Each has a visual symbol.

These are **level-1 graphics**: sketchable glyphs for paper/pencil
work.  Minimal, generic, domain-agnostic.  Part of the visual language
definition, not the behaviour.

- A capacity is a box.  A transport is an arrow.  A point is a dot.
- The symbols carry enough semantic meaning that a sketch is a
  partial model specification.
- This enables paper/pencil modelling ("playing") — explaining
  processes, documenting experiments, designing model structures
  without writing equations.
- The same symbols appear in the Modeller, so there is no translation
  gap between paper and screen.

See `docs/ontology-design-discussion-2026-09-11.md` section 14 for the
full graphical language discussion and sections 19-21 for the
three-level graphics model.

## Three-level graphics model

Graphics are not defined in one place:

| Level | Owner | What |
|-------|-------|------|
| 1 — Abstract symbol | Ontology Editor | Sketchable glyph, part of the visual language |
| 2 — Concrete base graphic | Behaviour Linker | Software-rendered graphic for a specific entity type |
| 3 — Composite / tailored graphic | Modeller | Custom graphics for composed entities |

**Dependency chain:** entity type (ontology) -> abstract symbol
(ontology) -> concrete base graphic (Behaviour Linker) -> composite
graphic (Modeller).  A graphic is only defined once the entity is
defined.

## Glasses

Glasses are **domain-specific visual skins** that override concrete
graphics (levels 2 and 3) with domain-specific alternatives:

- Chemical engineer: P&ID symbols (distillation columns, tanks,
  valves).
- Medical researcher: anatomical organ graphics.
- Brain modeller: neural/vascular tissue representations.
- Control engineer: block diagrams.

Glasses are:

- **Not ontology** — no new entities, just visual mappings.
- **Not behaviour** — no equations.
- **Not model-level** — not about a specific model instance.
- A **cross-cutting visual concern**: a mapping table from entity
  types to visual representations.

Glasses are stored separately, in their own RDF named graph.  Their
definition is a completely different task from ontology authoring.
The Modeller is the primary consumer — it applies glasses and lets
users switch between them.

See `docs/ontology-design-discussion-2026-09-11.md` sections 15, 20.

## Layout

The editor presents the staged workflow as a sequence of tabs or
steps.  Each stage shows:

- A **list** of existing items (with select for editing and delete).
- A **form** for creating/editing items with relevant fields.
- A **"New [item]"** button.
- Stage availability depends on prerequisites being met (e.g. the
  Entity Types tab is disabled until at least one scale dimension
  exists).

The layout is a two-pane design within each stage:
- **Left:** list of items for the current stage.
- **Right:** detail/editor form for the selected or new item.

## State and data flow

1. Editor loads the current ontology from the graph store.
2. All edits produce patches to the in-memory graph model.
3. Save commits the graph to the backend store (RDF/JSON/OWL).
4. The ontology `/context` endpoint provides a read-only snapshot to
   the Equation Editor (tokens, indices, domain tree, axes).

## Publication exports

From the ontology editor, the user can export:

- **Domain tree diagram** — SVG / PDF of the network hierarchy.
- **Token hierarchy** — tree of token types.
- **Classification axes** — per-domain axis trees.
- **Entity type taxonomy** — tree of entity types with scale
  compositions.
- **Connection rule table** — matrix of allowed connections.
- **Ontology report** — single markdown/PDF document combining the
  above, suitable for a paper or book appendix.

## Future decisions

- Web framework: React (current scaffold uses React + Vite).
- Tree editors for hierarchical structures (tokens, domains, axes,
  scales): a reusable tree component with drag-drop reordering.
- Scale dimension UI: how to present scale value composition for
  entity types (matrix editor?  multi-select per dimension?).
- Abstract symbol editor: how to author level-1 graphics (SVG
  picker?  simple shape selector?  freehand?).
- Downstream coupling: need to verify how tightly the Behaviour
  Linker and code generation are coupled to the CWA 17960 entity
  type schema (see section 17 of the design discussion).
