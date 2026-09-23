# Session handoff — 2026-09-23

State of the ProMo14 workspace at end of session.  Branch `main`,
remote `heinz-preisig/ProMo14`.  Supersedes
`session-handoff-2026-09-22.md`.

**Before switching machines:** the day's later work is *uncommitted* —
run `./dev.sh save` (persists the in-memory store into the tracked
`data/*.trig` files), then `git add -A && git commit && git push`.
On the other machine: `git pull && uv sync && npm install && ./dev.sh
start`.  Do **not** `wipe-restart` — `data/` is the sync channel.

## What landed today

**§20 species distribution — completed** (commits `dee38ed` …
`f8e4ffb`): species-present readout endpoint, `Q` binding (reaction
index via the same fixpoint as `S`), species aliases reaching the
`/model` report labels, and the stoichiometry ruling — ν is a plain
`[Q,S]`-indexed parameter-class variable; the scheme carries **no
coefficient slots** (sparsity derivable from reactants ∪ products;
the scheme-side `promo:stoichiometry` experiment was reverted).

**Hub ticket — all 7 items done** (`docs/hub-session-ticket.md`;
`4249f30`, `231a98e` committed; #5–#7 still uncommitted):

- #1 `editable_param` 400s on writes without `?graph=`; reads keep
  the legacy default.  `backend/testing.py::GraphClient` injects the
  session graph on mutating test calls.
- #3 `editable_param` 404s empty graphs — pins are born at creation.
- #4 per-artefact `.trig` persistence — `save()` fans out per line,
  legacy single-file splits on load.
- #5 hub UX — frozen-version open buttons, creation form with pin
  multi-selects, dirty-guard + Save affordance.
- #6 `?dev` hub flag → Vite ports (instantiation moved to :3006,
  collided with modeller).
- #7 `apply_seed_floor(g, base)` shared by load/seed/endpoint;
  `promo:seedFloor` stamp + `SEED_FLOOR`; catalogue `staleFloor`;
  hub update-floor badge; fork carries the stamp.

**ν value channel — implemented (uncommitted):** the missing piece
from the §20 story.  `promo:value` is scalar, so `[Q,S]` parameter
tables live on the **model artefact** as `promo:ValueCell` resources:

- `RdfStore.set_value_cells` / `value_cells`
  (`backend/core/graph_store.py`) — cells keyed by `|`-joined element
  IRIs in `indexStructure` order; `promo:coordinate` (JSON) is the
  authoritative axis order, `promo:atIndexElement` for navigation;
  deterministic cell IRIs `sha1(var|key)`; replace semantics.
- `PUT /api/instantiate/values?graph=<model>` (`editable_param`) and
  `GET /api/instantiate/values?graph=&variable=`.
- `VarBindingOut.values` surfaces the stored table per binding in
  `/api/instantiate/model`; `indices` on the binding already lists
  the required element sets (coverage counting deferred to clients).
- Vocabulary: `ValueCell`/`valueCell`/`atIndexElement`/`coordinate`
  declared unconditionally by `declare_vocabulary`.
- Test: `test_values_endpoint` in `backend/instantiate/test_builder.py`.

## Key code locations

- `backend/core/graph_store.py` — `set_value_cells`/`value_cells`
  (~line 1523), `declare_vocabulary` (~line 1080), `apply_seed_floor`.
- `backend/instantiate/service.py` — `/values` endpoints (~line 579),
  `VarBindingOut.values` (~line 123).
- `backend/testing.py` — `GraphClient` (new, untracked → commit it).
- `backend/static/hub.html` — dev-mode toggle, save badge, pin
  pickers, update-floor badge.
- `docs/species-status.md` — §20 detail incl. the ν channel section.
- `docs/hub-session-ticket.md` — all items marked DONE.

## Verified

- 309 backend tests pass: `uv run pytest backend/ -x -q`

## Caveats

- In-memory store: changes persist only via Save / `POST /save` /
  `./dev.sh save`; restarting loses unsaved edits.
- Value cells are API-only — no editor UI yet; not yet wired into
  `plan()`/emitters' `par` lookups (emitters still expect a scalar
  per parameter instance).
- `usesSpecies` is multi-valued in RDF but the modeller UI uses the
  first pin only; a model doc save drops additional pins.

## Next tasks (priority order)

1. **ν → codegen** — feed stored value cells into `plan()` and the
   emitters' parameter lookups (indexed `par` slices, not scalars).
2. **Value-cell editor UI** — the instantiation app (:3006) is a
   scaffold; the report's `indices` + `values` give it required vs
   supplied cells.
3. **Reaction-domain equations** — kinetics over the `Q` index.
4. **SHACL at publish boundary** (ADR-006).
5. **Behaviour-linker UI** — backend assignment/closure is live.
6. **Multi-pin `usesSpecies`** — if a model ever needs two schemes.

## Ruled contracts (don't re-litigate)

See `session-handoff-2026-09-17.md` — R1–R8 versioning rules,
connection-rule semantics, namespace discipline (`promo#` = vocabulary
only, instance IRIs under `{graphIRI}#`), no OWL.  §20 adds: species
stay **artefact-external**; capabilities are **entity-type**
predicates; ν is a `[Q,S]` parameter, schemes carry no coefficients;
value tables are **model-artefact data** (`promo:ValueCell`), not
var/expr vocabulary.
