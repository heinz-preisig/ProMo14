# Session handoff — 2026-11-25 (charge balance stages 1–2)

Five commits, `5df8a62` → `ef27b20`.  Suite 589 green; store
saved; tree clean at `ef27b20`.

## Landed

**Stage 1 — charge transport + first model** (`5df8a62`,
`d43e65d`, `7bc06e0`, §56 landed note):
- `etype_charge_transport` → `etype_conduction_transport`
  (drives `token_charge`), `idx_arc_charge`/`A_el`, `F_el`.
- Vars `V_130`–`V_136`: `qel`/`dqeldt`/`fe`/`Ue`/`Cel`/`kEl`/`Rel`;
  eqs `E_dqeldt`, `E_qel_def`, `E_fe_ohm`+`E_fe_res`, `E_Ue_cap`;
  `etype_lumped_conductor`; both assignments closed.
- `Ue` on `etype_environment` — voltage-source boundary.
- `model-charge` (`charge_01`): source→resistor→conductor.
  `/model` **0 problems**, python emit clean DAE,
  `POST /initial` t=0 solve ok, `par_needed` empty.
  Value cells: `kEl` 0.05 S, `Rel` 20 Ω, `Cel` 1 µF, `Ue` 5 V,
  `dqeldt` datum + IC.

**Stage 2 — electrochemistry var/expr from `U(S,V,n,qel)`**
(`afc814d`, `ef27b20`, §57):
- `z_el` [S] (valence; **not** `z` = `V_127` coordinate),
  `mu_el` [N,S] `{cm,charge}`, `Pel` [A_el,N] `{energy}`;
  `E_mu_el`, `E_Pel`, `E_qel_species` alt on `qel`,
  `E_fnd_el` alt on `fnd`.
- Constants: `const_e` bound; `const_F := Avo·const_e`
  (mirrors `R := Boltz·Avo`).
- **`design-principles.md` §19 — derivation program (user-ruled
  in principle):** everything derives from the base relation;
  the only primitives are the kinetic datums (`v`, `D`, `τ`,
  carrier density).  Coefficient skeleton:
  `k = (content-per-effort density) × (carrier speed)`.

## Traps hit (don't repeat)

- **Equation records need all referenced vars to exist** or the
  write path silently stores no `incidenceList` → §30
  `flow-uncovered` at instantiation.  Author scripts re-PUT in a
  second pass (`author_charge_stage1/2.py`).
- **Labels are flat per network** — `z` collided with `V_127`
  (coordinate), `e` is taken (control error).  Checker catches
  it via `UnitError` — always run `/api/equation/consistency`.
- `value` field on constants takes a **string**.

## Next (in order)

1. `D_s` [N,S] primitive (species diffusivity) →
   `E_kEl_ionic` alternative on `kEl`
   (`const_F²·inv(R·T)·reduceSum(z_el²·D_s·c_s, S)`).
2. **Electrode etype** — first real §32 pairing consumer
   (species + charge on one boundary = port-domain-ambiguous).
3. `Pel` into the charged-lump energy balance (stage-2 energy
   term is authored but not wired into any assignment).
4. Electrolyte lump (`E_qel_species`/`E_fnd_el` consumers).

## Machine notes

`data/*.trig` is tracked — `git pull` on the other machine,
restart backend, **no wipe-restart**.  `./dev.sh sync` builds
apps.
