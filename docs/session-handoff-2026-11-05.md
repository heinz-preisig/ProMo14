# Session handoff — 2026-11-05

## §22 referenced models render in place — read-only reference view

Clicking a referenced composite now opens the referenced artefact's
content **inside the host canvas** (no `?graph=` navigation, no empty
shell).  Header shows `◂ back · <view> · (referenced — read-only)`;
descending into nested composites/references works; every mutating
gesture is gated (`inRef`), pan/zoom/hover stay live.

- `ModelState`: `viewRefIri` + `refStates` (`RefViewState` = the maps
  `computeGraphView` needs); `setView` carries `refIri`;
  `setRefStates` command.
- `App`: `fetchRefStates` walks the `usesModel` closure on
  load/reload/insert; `refScope` swaps the doc maps into
  `computeGraphView`/`buildScene`; `readOnly` kills dragging.
- `useCanvasEvents`: `enterComposite` — prefetched state or lazy
  `loadModelDoc` on click, else shell-zoom fallback.

## Root-cause fix: duplicated `?graph=` (why clicks "did nothing")

`apiFetch`/`withParams` appended the session `?graph=` to **every**
call → `loadModelDoc(iri)` issued `?graph=<iri>&graph=<session>` →
scalar binding took the last → **host doc returned**, the ref view
rendered the host identically and `inRef` locked editing.  Worst case
was a write landing in the wrong artefact.

- `packages/ui/session.ts` — `withParams` never duplicates params the
  path already carries.
- `backend/core/deps.py` — `graph_param`/`editable_param` now read the
  request and **400 on duplicated `?graph=`** (verified: dup → 400).

## Rename / explode / gestures

- **Rename any node**: `setNodeLabel` (tree label + `modelNodes` label
  for leaves); Label input in Properties; header `View:` renames the
  open composite; Group prompts for a name.
- **Ungroup** (in-doc composites): children splice into the parent's
  slot, shell + its stores dropped.  **Dissolve** stays reference-only
  (Properties → Reference section).
- **Chained connect restored**: right-click connect arms the target as
  next source — node→node→node.
- Double-click leaf no longer zooms into an empty tree node;
  Ctrl/Shift+click composite selects it (plain click navigates);
  hint bar rewritten to real semantics.
- **`docs/modeller-gestures.md`** — canonical gesture map.

## Extract naming

One prompt: "Name for the extracted submodel" → slug-derived IRI
(`mix 1` → `model-2/mix-1`) → catalogue pre-check → re-prompt on
collision.  Backend `create_artefact_graph` 409 is the hard guard.

## Design ruling — `docs/design-principles.md` §12

Submodel composition: **two tiers stay** (in-doc composite vs `refersTo`
artefact); uniformity via *addressing* (composite IRIs when needed),
not uniform persistence.  Filed gap: **occurrence-path namespacing**
— two occurrences of one submodel share var IRIs; instantiation must
qualify by occurrence path before multi-instance models instantiate.

## Also landed (earlier uncommitted work)

Backend `extract_submodel` child-recovery (frontend children may lack
`iri`), dissolve endpoint, catalogue gesture renames, hub.html.

## Store state

`data/` persisted: library, assignments, ontology, species, `model`
(test_01), **`model-2.trig`** (new — host + extracted `mix_1`
submodel, pinned library/assignments/species).

## Test status

Backend: 48 passed (`backend/core` + `backend/modeller`).
Frontend: 2 pre-existing failures, unchanged (buildScene dash
assertion; ModelState.test `window` env error).

## Next up

- Occurrence-path namespacing (§12 gap) when multi-instance
  instantiation lands.
- Cross-artefact consistency review (still deferred per rules).
- Palette hint when no `usesAssignment` pin (silent-empty UX).
