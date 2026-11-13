# Session handoff — 2026-11-13

## Delivered

### UX: save confirmation + block-reason prominence (equation editor)

- **Save toast** (`App.tsx`): every `saveEditedVariable` call sets
  `savedNotice` → green fixed bottom-right toast
  "✓ E_48 saved — K recorded in the library" (variable-only saves show
  the label alone). Click or ~6 s auto-clear, re-arms per save. Covers
  Accept, Save equation, Save variable, table edits, equation deletes.
- **Block reason** (`DependentVariableEditor.tsx`): `acceptBlockReason`
  moved out of the cramped actions row onto its own bold 14 px line
  under the dialog title.
- An earlier, more elaborate attempt (signature-change banners +
  "modified" indicator) was reverted to `bfc3b83` mid-session after it
  produced contradictory messaging; the shipped version is the two
  minimal changes above.

### Index-order ruling (design-principles §8)

- **`signatureMismatch` (`variableUtils.ts`)** compared index
  *sequences*; the ruling is index-IRI **sets**. Now sorted-set
  comparison — a same-set order diff is no longer a signature
  violation. Test updated (`variableUtils.test.ts`). This unblocked
  `E_48` (`K` declared `[N,K]`, derives `[K,N]`).
- **`Add` (`checker.py`)** now conforms by index set too — the user
  ruled the fix after the over-enforcement was detected. Result order
  follows the left operand; **`codegen.py`** `_align` permutes the
  right operand onto the result axes (`np.transpose` /
  `permutedims`; matlab binds by label). Different sets still fail.
- Tests: `test_add_same_set_any_order_conforms`,
  `test_add_different_set_rejected`,
  `test_add_aligns_same_set_different_order` (+ `beta [N,T]` fixture).
  543 backend + 12 frontend tests pass; dist rebuilt.
- Docs: `design-principles.md` §8 amended;
  `behaviour-linker-status.md` + `behaviour-linker-design-discussion
  §2.2` superseded-note'd (records append-only).

## Equation authoring state

- `E_48` (Arrhenius `K`): `neg` exponent added by the user; signature
  block cleared by the set-conformity fix — save path open.
- Earlier audit: 52 consistent equations.
- Todo carried over: exercise connection licensing in the modeller
  (observation + actuation arcs).

## Env notes

- Backend serves `apps/*/dist` — rebuild after any frontend edit
  (`npm run build -w @promo/equation-editor`); browser may need a hard
  refresh (index.html caching).
