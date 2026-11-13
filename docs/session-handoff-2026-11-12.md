# Session handoff — 2026-11-12

## Start here next session

Continue the **reaction-kinetics port** — the skeleton is in place and
the full ProMo12 mapping is below.  Remaining equations: `xi` (Π over
species), `Ko`/`Ea` constants, `k_rxn` (Arrhenius), `np` (stoich
contraction), and the `dndt` species-balance production term.

The reaction index is now **`K`** (`idx_reaction_q`, `I_11` kept —
renamed `q`→`K` via `POST /api/ontology/indices`, matching ProMo12's
`N_{S,K}`).  `q` no longer resolves in expressions.

## Delivered today

- **`POST /api/equation/parse` restored** (`9d9816e`) — the route had
  been dropped during token simplification; the editor's "Parse
  failed" fallback fired on any expression.
- **Reduce-operator rule clarified** (design-principles §8): `*`
  contracts **exactly one** shared index IRI, implicitly; multi-shared
  operands need the explicit-index forms `reduceSum(body, K)` /
  `Product(body, K)`.  Triggered by `E_42` (`reduceSum(F_diff . fnd,
  A_diff)` — `A_diff` reduced, `N,S` survive).  No language change.
- **Stoichiometry provenance confirmed** (design-principles §9, was
  already ruled): ν is a **parameter-class** variable `[S,K]`, valued
  at instantiation — *not* a port.  The species doc carries only
  reactant/product **sets** (±/zero pattern of ν); coefficient
  magnitudes stay §20-open.
- **Instantiate check race fixed** (`bfc3b83`): `handleCheck` synced
  the function pick to `parameter`, then built the `/check` request
  from the stale render closure — the draft LHS went out as
  `fundamental-state` and the §24 bound-value gate rejected it.
  `clsOverride` now threads `buildRequest → contextVariables →
  draftVariable`.  `Instantiate(n)` → `no` verified end-to-end
  (`mol`, `[N,S]`, empty incidence).
- **ProMo12 reaction section extracted** from
  `CAM12/Ontology_Repository/processes_distributed_001/LaTeX/main.pdf`
  — mapping table below.

## ProMo12 → ProMo14 reaction-kinetics mapping

ProMo12 carried an interface index `p` (its distributed port machinery)
which collapses in ProMo14 — reactions are node-hosted, `K` binds
per-node at instantiation.

| ProMo12 | Kind | ProMo14 |
|---|---|---|
| `N_{S,K}` stoich matrix | constant, dimless | `N` (`V_85`) — **authored** |
| `K^o_K` frequency factor | constant, mol m⁻³ s⁻¹ | `Ko` — pending |
| `E^a_K` activation energy | constant, J/mol | `Ea` — pending |
| `R` gas constant | — | **authored as `R = Avo . Boltz`** (`E_44`) |
| `f_{N,S,K} := x^{\|N\|}` | conversion, dimless | **`f := xa ^ abs(N)`** (`E_46`, `xa` = normed activity) — authored |
| `ξ_{N,K} := Π_S f` | conversion, dimless | `xi := Product( f, S )` — pending |
| `K_{N,K} := K^o . exp(−E^a . inv(R.T))` | conversion, mol m⁻³ s⁻¹ | `k_rxn` — pending (`exp`,`neg`,`inv` all exist) |
| `ñ_{N,S} := N ⋆ (K . ξ)` | conversion, mol m⁻³ s⁻¹ | `np := N * ( k_rxn . xi )` — pending; `*` legal: single shared index `K` |
| `ṅ := ṅcx + ṅdx + V.ñ`; `n := ∫ṅ + n^o` | state | `dndt` + `Instantiate`-class initial |

Authored by the user in-editor today: `x^o := Instantiate(c)` (`E_43`),
`xnorm := c . inv(x^o)` (`E_45`), plus `fnd` corrected to
`reduceSum(F_diff . fnd, A_diff)` (`E_42`).

## Live audit snapshot at shutdown

Scope `https://w3id.org/promo/library` incl. pins: **52 equations —
0 errors, all consistent.**

## Open threads

- **Reaction kinetics** — see mapping table; `xi`, `k_rxn`, `np`,
  `dndt` remain.
- **Controller output** — `y = pGain . e` discussed; check current
  state (signal-token advisories were the prior blocker).
- **Connection licensing** — observation + actuation arcs in the
  modeller still unexercised.
- **§20-open**: whether `promo:Reaction` should carry coefficient
  magnitudes so ν auto-binds fully (today only the ±/zero pattern is
  derivable from reactant/product sets).
- `ontology/1.0` snapshot still carries the old `q` index record —
  frozen as published; live `ontology` graph resolves `K`.
