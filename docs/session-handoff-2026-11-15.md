# Session handoff — 2026-11-15

## Delivered

### §43 — `function:flow` grants port export

A variable classified `function:flow` is peer-readable across a
contact **without** `portVariable`; the flag stays as the explicit
override for non-flow exports.  `exportable = port_variable or
flow` (`VarInfo.exportable`) drives state hiding, candidate
preference and self-donation in `builder.py`, and phantom-boundary
fill-ins in `service.py` (`VarInfo.flow` derived from the
classification).  `hasPortVariable` unchanged — the assignment-side
demand declaration.  Rationale: a through-flow lives on the arc by
nature; `function:effort` was precedent (classification already
drives pairing).

Data: flow vars unflagged where the flag became redundant;
`ahc`/`and`/`ahd` reclassified `function:flow`→`function:state`
(accumulations, user correction); `fhc`/`fhd` unflagged — the flag
tripped the `portVariable ⇒ carriesToken` consistency rule (they
carry no token).

Regression: `test_exportable_flag_or_flow`; `J` fixture moved to
unflagged `flow=True` so the port tests exercise the new path.

### §44 — balances specialize to connected ports

A declared flow port that **binds nothing** — no carrier-matching
arcs, or contacts whose peers export no comparable flow — is
*absent*, not unbound: no `PortBinding`, no `unbound-port` problem,
no balance term.  An all-mechanisms assignment now instantiates
cleanly on any subset of mechanisms — no zero-instantiated unused
ports, no per-configuration entity types.  The asymmetry: non-flow
demands still report `unbound-port` (an unconnected effort makes
the law ill-posed, not absent); `ambiguous` and `effort-unavailable`
unchanged.

Implemented in `builder.py` — `var.flow` skips `emit_port` on
`unbound` in all three binding paths (arc-indexed, node-indexed,
scalar).  Regression: `test_absent_flow_port_is_silent` — energy
flow port on a mass-only topology is silent while a non-flow twin
still reports.

### §41 σ[X] — committed (machinery from 2026-11-14 session)

The reference-coordinate direction vector landed earlier and is now
in-tree: `seed._seed_coordinate` seeds `idx_x` (`coordinate` class,
selector-less arc-like sub-index) and `sigma` (constant+parameter,
dimensionless, token-neutral); `builder` binds `X`-indexed vars
`binding="direction"`; `plan._direction_signs` emits the
per-contact ±1 literal from the entity's F row, reporting
`direction-ambiguous` for arcs touching the scope at ≠1 ends;
`persistence`/seed skips selector-less sub-indices for `F_k`
factor materialisation; `SEED_FLOOR` → 2026-11-14;
`direction-ambiguous` catalogued.

## State

- **561 backend tests green.**  No frontend changes; no dist rebuild
  needed.
- Living docs realigned: `design-principles.md` §3 (§43/§44
  amendment), `behaviour-linker-status.md` (export semantics, absent
  rule, σ direction slots, header → 2026-11-15).  Rulings recorded in
  `behaviour-linker-design-discussion.md` §43/§44.
- `data/*.trig` saved with all of the above (seed + flag migration).

## Open items

- **§41 remainder.**  σ machinery is committed; verify whether the
  transport-law rewrites (`fmc = k·A·reduceSum(σ*p_mech, X)` —
  E_4/E_11, `fhc`/`fhd`/`fQx`/`fnd`, upwinds) are actually in
  `library.trig` — the post-§40 `reduceSum(...,N)` breakage this
  fixes is documented in the §41 record.  The C fold
  (`vx,vy,vz→v[C]`, `r_x,r_y,r_z→r[C]`, `idx_component` seed) is
  still a deferred batch.
- **Continuity completeness check** (discussed, not requested):
  nothing verifies that every incident flow of a mechanism actually
  appears in the capacity's state equation — a possible advisory,
  pending ruling.
- **§32 stage-2 leftovers** unchanged: pairing resolver
  (`port-domain-ambiguous` still terminates), `promo:Mechanism`
  resource layer.
