# Session handoff — 2026-11-03

State of the ProMo14 workspace at end of session.  Branch `main`,
remote `heinz-preisig/ProMo14`.  Supersedes
`session-handoff-2026-09-23.md`.

**Before switching machines:** everything below is committed in this
push.  On the other machine: `git pull && uv sync && npm install &&
./dev.sh start`.  Do **not** `wipe-restart` — `data/` is the sync
channel and `data/*.trig` changes made in the editors are part of
this state.

## Status at a glance

- **507 backend tests pass** (`uv run pytest backend/ -x -q`),
  including the new regression test
  `test_emit_python_lhs_index_conformity`.
- `GET /api/instantiate/code?graph=...&target=python` still returns
  `ok=False` for the test_01 model — but now fails *honestly*: a
  `VarError` naming the broken equation plus a `port-coverage`
  `Problem` in the report, instead of silently emitting broadcasting
  nonsense.  The remaining blockers are **model-level**, fixed in
  the editors, not in code.
- Today's discussion established the intended flow/balance semantics
  (below) — what remains is a **design decision** about arc index
  classes (`F_mass` vs `F_conv`) that only the modeller can make.

## Emitter semantics established today

All in `backend/instantiate/`; regression-covered in
`test_builder.py::test_emit_python_lhs_index_conformity`.

- **rhs ↔ lhs index conformity** (`emit_common.py::render_rhs`):
  after `check()`, the checked rhs index *order* is compared with
  the lhs variable's declared index order.
  - Same set, different order → new `Dialect.permute(src, perm)`
    hook wraps the rendered expression in a transpose at the
    assign/residual point.  Python emits `.transpose((perm))`,
    Julia emits `permutedims(...)` (1-based), **MATLAB is not
    implemented** — the base hook raises `VarError` (its
    `MultiDimVar` wrapper needs label-aware relabeling).
  - Different index sets → **positional flat binding** (sanctioned
    semantics — algebraic-loop residuals rely on it, e.g. rhs
    `[A_diff]` onto lhs `[N]`).  Only a flat-*size* gap is
    unemittable → `VarError "index mismatch in <eq> ... (N
    elements) but <lhs> is bound over ... (M elements)"`.
  - `PlanBlock.bound` (new field): per-entity-type
    index-IRI → bound-elements map, built in `plan()`.  Plans
    without it (hand-built/serialised) skip the size check —
    legacy positional behaviour.
- **Port-gather coverage** (`plan.py`): contacts fill a port var's
  slots positionally; supplied ≠ bound size → `Problem
  kind="port-coverage"` (visible in `/model` and `/code`
  `problems`).  `emit_python` `gather`/`gather_multi` then emit a
  deterministic pad/truncate `_fill` (first-wins, zero-pad,
  reshape to declared dims) so the module still runs.
- **Operand order is meaningless** for `*` and `.`: `*` contracts
  the *one* shared index IRI; `.` takes the ordered union.  The
  result axis order is normalised to the lhs declaration by the
  permute hook.
- Also in this commit (prior uncommitted work): `t0_layout`,
  constrained-balance solve, prescribed equations emitted as
  constraints, shape-aware unpacking, incidence-matrix data
  emission, `emit_matlab` reshape work, behaviour/closure fix,
  equation-editor + instantiation-app changes, and the day's
  `.trig` edits from the editors.

## Model diagnosis (test_01: env – ct – lumped)

- **E_4** `fmc = kConvX . Ayz . (F_mass * p)` — user changed
  `F_conv`→`F_mass` today.  Emits, but the result `[N, A_mass]`
  binds **positionally** onto `V_56 [A_conv, N]` — correct only
  because the arc sets coincide and `N`=1.  Fragile; resolves
  itself once `fmc` is re-indexed (then it becomes a clean
  permute).
- **E_29** `dmdt = F_mass * fmc` — `fmc`'s arc axis is
  `idx_arc_convection`, `F_mass`'s is `idx_arc_mass`: the only
  shared index is `N`, so `*` contracts *node* → `[A_mass,
  A_conv]` (4 elems) vs `[A_conv, N]` (2) → `VarError`.  Changing
  operand order cannot fix it — `*` contracts by shared index IRI.
- **`V_34` on the ct domain**: two bound ports (Arc_1→env Node_1,
  Arc_2→lumped Node_3) feed one `Node_2` slot → `port-coverage`.
  Decide: one bound contact, or arc-indexed `V_34` if the
  boundary pressure is per-arc.

## The intended semantics (agreed in discussion)

F is stored **arc-rows × node-cols** `[A, N]`:

- **Flow (gradient/constitutive)**: `ṁ_a = Σ_n F[a,n]·p_n` —
  `F * p` contracts the node axis → per-arc.
- **Balance (divergence)**: `dmdt_n = Σ_a ṁ_a·F[a,n]` —
  `ṁ * F` contracts the arc axis → per-node.
- **Same F in both directions** — incidence duality.

## Open design decision: `F_mass` vs `F_conv`

Both are `subIndexOf idx_arc` — **siblings**, selected by domain
type (`etype_mass_transport` vs `etype_convection_transport`).
Identical values here because the convection domain *is* the mass
domain; they differ in general (`A_mass ⊇ A_conv` when a domain
carries several mass-arc flavors).

- **Option A — everything convection**: keep `V_56`/`V_57` at
  `[idx_arc_convection, idx_node]`; E_4 uses `F_conv`; E_29 →
  `F_conv . fmc` (elementwise signed rates) **and** `F_conv` in
  E_29's incidence list (lumped must bind `F_conv`).
- **Option B — everything mass**: re-index `V_56`/`V_57` to
  `[idx_arc_mass, idx_node]`; E_29 → `F_mass . fmc` (elementwise;
  `*` would see two shared indices and is ambiguous); E_4 keeps
  `F_mass` — becomes a proper permute, not a positional bind.
  `F_conv` then goes unused in this model.
- **Option C — ontology semantics**: if convection arcs are meant
  to be a *subset* of mass arcs (balance sums all flavors),
  `idx_arc_convection` should declare `subIndexOf idx_arc_mass`.
  ⚠ The checker contracts by **exact index IRI** — sub-index
  relations do **not** unify operands today; this is a machinery
  gap, not a fix for E_29.

All edits go through the **editors** — `.trig` files are serialised
persistence; manual editing is forbidden.

## How to resume

```bash
./dev.sh start            # backend :8000
uv run pytest backend/ -x -q          # 507 passing

# re-verify after model edits:
.venv/bin/python - <<'EOF'
from backend.instantiate.service import _plan_for, _code_space
from backend.instantiate.emit_python import emit_python
cp, report, store = _plan_for('https://w3id.org/promo/model', None, None)
print([(p.kind, p.message[:80]) for p in report.problems])
try:
    emit_python(cp, _code_space(store, 'https://w3id.org/promo/library'))
    print('EMIT OK')
except Exception as e:
    print('EMIT FAIL:', type(e).__name__, e)
EOF
```

Expected once fixed: `EMIT OK`, then run the generated module's
`initial({}, steady_state=False)` — the original t=0 `matmul`
crash is gone; what remains is model semantics.
