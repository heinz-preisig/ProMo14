# Session handoff — 2026-09-16

State of the ProMo14 workspace at end of session. Commit `00e2570`
(pushed to `heinz-preisig/ProMo14`, branch `main`).

## Root domain + binding scope (the big change)

The domain tree now has an explicit root:

```
root                global scope: signal token, time scale
├── physical
│   ├── macroscopic     capacity
│   ├── transport       transport nodes (flat)
│   ├── reactions       service
│   ├── properties      service
│   └── geometry        service
└── information
    └── control
```

**Binding scope semantics** (decided today): a scale dimension's
`hasDomain` binding defines the subtree where its values apply.

- bound to `root` → global (all branches)
- bound to a branch root → inherited down that branch
- bound to a subdomain → that subtree only; not usable for
  entity-type composition (entity types are branch-scoped)
- unbound → treated as global (permissive fallback)

`time` is bound to `root` (dynamic systems are global); `length` and
`phase` stay bound to `physical`. The entity-type editor enforces
this: the scale-value checkbox list shows only structural dimensions
whose bound domain is an ancestor-or-self of the draft's branch root.

**Signal token** moved to `domain_root` — inherited by every branch
(supersedes the interim physical-root + information binding, and the
original transport-only binding).

**Information entity types carry no scale values** — the earlier seed
wrongly attached physical scale values to `info_constant` /
`info_dynamic` / `info_event`. Their classification is
`temporal_type` (constant | dynamic | event-dynamic) only. Physical
entity types compose time + length scale values as before.

## Kind attributes (from the morning session)

- `promo:tokenKind` on tokens: `conserved` | `reference`. Conserved =
  accumulate in capacities, carried by token-flow arcs. Reference =
  variable access (signal + subtokens observation/manipulation).
- `promo:dimensionKind` on scale dimensions: `structural` |
  `content`. Structural dims compose entity types; content dims
  (phase) bind per model-node instance and never compose entity
  types.
- Role axis = var/expr graph positions only; domain-echo terms
  removed. Phase vocabulary: `solid, fluid{liquid, gas}, pseudo`.

Full rationale: `docs/ontology-design-discussion-2026-09-16.md`.

## Ontology editor UX

- **Dirty-state Save buttons** — all nine forms disable Save while
  the draft matches the persisted record; after a successful save the
  draft re-syncs from the reloaded record and Save greys out.
- **Responsive checkbox lists** — token/scale-value/shared-token
  lists shrink to fit the window (`flex 0 1 auto`, `minHeight 80`,
  `overflow auto`).
- **Entity-type ordering** — list sorted by scale-tree DFS rank
  (small→large); header button cycles `scale ↓` → `scale ↑` → `a–z`.
- **Ordered scale values** — checkbox lists and parent dropdowns
  render in dimension order + DFS rank (parents before children).
- **Root domain protected** — no delete button, parent dropdown
  disabled; "+ New" domain defaults to `parent = root`.

## Bug fixes

- `add_entity_type` now persists `scale_values` (replaces the
  `hasScaleValue` set on save, mirroring `add_domain`'s `hasToken`
  handling); `create_entity_type` passes `record.scale_values`
  through. Previously scale-value edits silently reverted.

## Reproduce on another machine

`data/` is gitignored — the ontology lives in
`data/ontology.trig` on each machine.

```bash
git pull
uv run python scripts/extend_ontology_hap.py   # idempotent migration
./dev.sh restart                              # backend picks up the file
```

The script now also: creates `domain_root`, reparents both branches,
rebinds `scale_time` to root, moves `signal` to root, strips physical
scale values from the three `etype_info_*` records.

If starting from scratch (no `ontology.trig`): the backend seeds the
current ontology on first load — the seed already includes the root
domain — then run the script for the HAP extensions.

## Verified

- 112 backend tests pass (`uv run pytest backend/ontology/test_service.py backend/equation`).
- `npx tsc --noEmit` clean in `apps/ontology-editor`.

## Caveats (unchanged)

- In-memory state: ontology changes persist only via the editor's
  Save / `POST /save`.
- `mint_iri` has no collision check.
- `resolve-connection` matches domains + scope only — no token-level
  check yet (sharedTokens are declared but not enforced).
- Sibling order in scale-value trees follows backend list order — no
  explicit sibling-order attribute in the schema.
- UI-side enforcement only: nothing backend-side rejects a
  cross-branch `hasScaleValue` or a content-dimension value on an
  entity type.

## Next tasks

- Verify w3id redirect post-merge (perma-id/w3id.org#6700).
- Modeller `ConnectionRuleResolver` → `resolve-connection`.
- Persistence UX (autosave / dirty-warning on exit).
- Optional: backend checker rule for binding scope (reject
  cross-branch `hasScaleValue`, content dims on entity types).
- Optional: token-level matching in `resolve-connection` (subtokens
  observation/manipulation are ready for it).
- BL design continues; ontology v2 (versioning ADR-006, QUDT).
