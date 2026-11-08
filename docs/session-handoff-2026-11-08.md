# Session handoff — 2026-11-08

## Ruled — submodel reuse (§33)

The 11-06 copy-vs-reference either/or dissolved: **the two modes
coexist** — the user's clarification "reuse requires open
connections" exposed that they serve different intents.  Recorded as
§33 of `docs/behaviour-linker-design-discussion.md` plus amendments
to `docs/design-principles.md` §12/§13.

- **Two insertion modes.**  *Copy insert* = paste-and-integrate
  (mechanically insert+dissolve; `dissolvedFrom` is the provenance
  and dies if the group is ungrouped; every leaf is a legal
  connection surface — emergent interface; copied open arcs persist,
  never auto-deleted).  *Referenced insert* = sealed contract use;
  declared ports are the only legal connection surface.
- **Interface = complete port contracts** — what flows
  (token/information), direction (§15 / inherent in-out for
  signals), arc kind, expected peer.  Token never stored (derived
  from inside entity type); `externalEntityType` demoted gate→hint;
  admissibility = rules between the two real entity types.
- **Two port origins.**  *Severed* (extraction — primary) and
  *authored* via **phantom peer**: pick inside leaf + name the
  imagined partner; the connection rules derive the contract;
  direction convention is a flippable default.  Nothing
  hand-written → nothing stale.
- **Phantom does double duty** — also the default boundary
  condition for standalone instantiation (expects a capacity →
  instantiate a minimal capacity to close the circuit).
- **Strict boundary ruled** — only declared ports connectable on a
  referenced occurrence, observational arcs included; missing port =
  artefact edit (or fork+re-point for foreign artefacts);
  **dissolve is the escape hatch** — strict is livable only because
  declaring is cheap and escape exists.
- **Standalone instantiation ruled** — ports exposed as boundary
  conditions; parts testable before placement.
- Friday's three questions resolved: pin variation lives in the
  referenced path (override map); propagation stays pin-gated there;
  the black-box case *is* the referenced insert.  `refersTo` stays
  as the contract-bound tier — **not** dormant.  The refresh
  machinery (`copiedFrom`/refresh) is demoted — `dissolvedFrom`
  suffices; refuse-to-clobber deferred until demanded.

## Open from §33

- Port multiplicity — gathering terminals need declared cardinality
  (cf. shared boundary var §29/§32).
- Strict enforcement surface — undeclared leaves must be
  non-targets in the connect gesture, not merely fail late.
- Phantom closures — instantiating the imagined peer as a minimal
  default entity is new instantiation machinery.
- Copied open arcs — keep expected-peer hints vs land as bare stubs.

## Status

- Design session only — no code changed; docs only (§33, principles
  §12/§13 + gap entry).
- Test case unchanged: `model2` → `model-2/tripot1`, still the first
  real referenced composite.

## Next up

- §33 implementation, roughly in dependency order: phantom-port
  authoring gesture (post-hoc declaration incl. imported models) →
  strict-boundary enforcement in resolve-connection/connect UX →
  standalone instantiation with phantom closures → copy-insert as
  insert+dissolve convenience.
- Still queued: §21 closure-moves rewrite; §32 stage-2
  `promo:Mechanism`; occurrence-path namespacing (still load-bearing
  — the referenced path survives); cross-artefact consistency
  review.
