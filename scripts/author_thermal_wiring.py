#!/usr/bin/env python3
"""Thermal/total-balance wiring on etype_lumped (authored 2026-11-24 PM).

Wires dHdt/dEtotdt into the dynamic lumped assignment as diagnostic
outputs — the §50 pattern ("balances are readings, no new state")
extended from the mechanical to the thermal balance.

Root-cause fix first:

- E_53 (h): `H * inv(n)` -> `ParDiff(physical!H, physical!n)`.
  H is the [N] lump total, n is [N,S] — the old rhs divided total
  enthalpy by per-species moles, which is not the partial molar
  enthalpy the doc promises.  ParDiff(H, n) is the formalism's
  n-conjugate effort of H — same pattern as mu := ParDiff(U, n)
  and Cp := ParDiff(H, T).  The equation stays in the library for
  EOS-bearing scopes; on etype_lumped h is INSTANTIATED property
  data (like Mm/N) so the un-emittable EOS layer stays out.

Selection deltas on etype_lumped (ports cut the chain — fnc/fnd/fQx
are all port-carried, produced by the arc etypes, so the
species/reaction/EOS stack never enters the lump closure):

- sequence  += E_54(fhc) E_55(fhd) E_56(ahc) E_57(ahd) E_58(ah)
              E_59(ahq) E_62(akp) E_61(dHdt) E_66(dEtotdt)
- ports     += fnc(V_77) fnd(V_79) fQx(V_55)
- instantiated += h(V_96)
- outputs   += dHdt(V_103) dEtotdt(V_114)
- state_variables unchanged — readings, not slots.

test_01 note: idx_species/idx_arc_diffusion/idx_arc_heat are empty,
so the species/heat legs gather zero (fWs precedent) — the wiring is
structural; species-bearing models light it up.  Transport-side
export of fnc (cac·fV needs upwind c — §32 pairing) remains open.

etype_lumped_qss untouched: dEtotdt -> akp -> fKin -> v -> P needs
the absent P slot — same deferral as §50's mechanical wiring.

RELOAD FOOTGUN: run, save inside the same process — no source edits
between mutation and save.
"""
import json
import sys
import urllib.parse
import urllib.request

API = "http://localhost:8000/api"
LIB = "https://w3id.org/promo/library"
ONT = "https://w3id.org/promo/ontology"
ASG = "https://w3id.org/promo/library/assignments"


def req(method, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    g = urllib.parse.quote(LIB, safe="")
    st, ctx = req("GET", f"{API}/equation/context?graph={g}")
    assert st == 200, ctx
    existing = {v["iri"]: v for v in ctx["variables"]}
    failures = []

    # -- E_53 fix: partial molar enthalpy is ParDiff(H, n) -------------
    h_iri = f"{LIB}#V_96"
    h_rec = existing[h_iri]
    e53 = h_rec["equations"]["E_53"]
    e53["rhs"] = "ParDiff( physical!H, physical!n )"
    enc = urllib.parse.quote(h_iri, safe="")
    st, out = req("PUT", f"{API}/equation/variables/{enc}?graph={g}",
                  h_rec)
    if st != 200:
        failures.append((h_iri, f"PUT {st}: {str(out)[:300]}"))
    else:
        print("V_96 h: PUT", st, "E_53 ->", out["equations"]["E_53"]["rhs"])

    # -- extended lumped assignment ------------------------------------
    sel = {
        "entity_type": f"{ONT}#etype_lumped",
        "sequence": [
            f"{LIB}#E_m_def", f"{LIB}#E_F_g", f"{LIB}#E_dPdt",
            f"{LIB}#E_P_int", f"{LIB}#E_v_fromP",
            f"{LIB}#E_fKin", f"{LIB}#E_fPot", f"{LIB}#E_fPflow",
            f"{LIB}#E_aw", f"{LIB}#E_al", f"{LIB}#E_amech",
            f"{LIB}#E_dEmdt",
            f"{LIB}#E_54", f"{LIB}#E_55",
            f"{LIB}#E_56", f"{LIB}#E_57", f"{LIB}#E_58",
            f"{LIB}#E_59", f"{LIB}#E_akp",
            f"{LIB}#E_dHdt", f"{LIB}#E_dEtotdt",
            f"{LIB}#E_29"],
        "base_equation": f"{LIB}#E_29",
        "state_variables": [f"{LIB}#V_121", f"{LIB}#V_57"],
        "instantiated": [f"{ONT}#V_34", f"{ONT}#V_11", f"{ONT}#V_115",
                         f"{LIB}#V_96"],
        "ports": [f"{LIB}#V_117", f"{LIB}#V_118", f"{LIB}#V_56",
                  f"{LIB}#V_109", f"{LIB}#V_104",
                  f"{LIB}#V_77", f"{LIB}#V_79", f"{LIB}#V_55"],
        "outputs": [f"{LIB}#V_121", f"{LIB}#V_113",
                    f"{LIB}#V_103", f"{LIB}#V_114"],
    }
    st, out = req(
        "PUT",
        f"{API}/behaviour/assignment"
        f"?graph={urllib.parse.quote(ASG, safe='')}",
        sel)
    if st != 200:
        failures.append(("assignment", f"PUT {st}: {str(out)[:300]}"))
    else:
        print(f"etype_lumped: PUT {st} closed={out.get('closed')}")
        for u in out.get("unresolved", []):
            print("  unresolved:", u["variable"].split("#")[-1],
                  "candidates:",
                  [c.split("#")[-1] for c in u.get("candidates", [])])

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" ", f)
        sys.exit(1)

    # -- save immediately (reload footgun) ------------------------------
    st, out = req("POST", f"{API}/ontology/save")
    print("save:", out)
    print("\nthermal balance wired — h instantiated, ports cut the chain")


if __name__ == "__main__":
    main()
