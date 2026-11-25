#!/usr/bin/env python3
"""§50 energy wiring on etype_lumped_qss + the E_fKin stream-velocity fix
(authored 2026-11-25).

The §50 deferral resolved in discussion: the lump has a velocity at
each convective flow connection port — that is `v_str`, pressure-
driven on the arc and gathered on the peer.  `v` (bulk velocity) is
out of the energy chain entirely: `macroscopic!v` appeared in exactly
one place, `E_fKin`, and advected kinetic energy through a contact is
stream physics — the same ruling §49 made for `fl` ("the lump's bulk
velocity would be the wrong physics").  V_116's doc already records
the split: "Stream-velocity role on transports lives on v_str (port);
v stays the lump's bulk velocity."

Changes:

- E_fKin:  macroscopic!v -> macroscopic!v_str  (upstream fix — no
  alternative; the bulk-v form was wrong everywhere)
- etype_lumped:  ports += v_str (V_122);  sequence -= E_P_int,
  E_v_fromP (dead cone — nothing consumed v but fKin; P stays a
  state via the dPdt slot, the aliases just emitted for fKin)
- etype_lumped_qss:  full §50 wiring — sequence += E_z, E_fKin,
  E_fPot, E_fPflow, E_aw, E_al, E_amech, E_dEmdt;  ports += fl
  (V_109), fWs (V_104), v_str (V_122);  instantiated += r (V_115 —
  fPot's z := e_z·r needs node position);  outputs += dEmdt (V_113).
  No v, no P — the qss bulk momentum does not exist by design.

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

E_FKIN_V_STR = ("( ( macroscopic!fmc * half ) * "
                "reduceSum( ( macroscopic!v_str * macroscopic!v_str ), "
                "C ) )")


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

    # -- E_fKin: stream velocity, not bulk (the §49 ruling applied) ---
    fkin_iri = f"{LIB}#V_106"
    fkin = existing[fkin_iri]
    # dict keys are internal_ids (E_67), not IRI names (E_fKin)
    eq = next(v for v in fkin["equations"].values()
              if v["iri"].endswith("#E_fKin"))
    eq["rhs"] = E_FKIN_V_STR
    eq["doc"] = ("advected kinetic energy per contact = 1/2 * fmc * "
                 "v_str^2 (v^2 = sum_C v_str^2) — stream velocity, "
                 "same ruling as fl (§49/§50): the lump's bulk v is "
                 "the wrong physics through a contact")
    enc = urllib.parse.quote(fkin_iri, safe="")
    st, out = req("PUT", f"{API}/equation/variables/{enc}?graph={g}",
                  fkin)
    if st != 200:
        failures.append(("E_fKin", f"PUT {st}: {str(out)[:300]}"))
    else:
        print(f"V_106 fKin: PUT {st} — rhs on v_str")

    # -- etype_lumped: v_str port in; P/v aliases out (dead cone) -----
    sel = {
        "entity_type": f"{ONT}#etype_lumped",
        "sequence": [
            f"{LIB}#E_m_def", f"{LIB}#E_F_g", f"{LIB}#E_dPdt",
            f"{LIB}#E_fKin", f"{LIB}#E_z", f"{LIB}#E_fPot",
            f"{LIB}#E_fPflow", f"{LIB}#E_aw", f"{LIB}#E_al",
            f"{LIB}#E_amech", f"{LIB}#E_dEmdt", f"{LIB}#E_29"],
        "base_equation": f"{LIB}#E_29",
        "state_variables": [f"{LIB}#V_121", f"{LIB}#V_57"],
        "instantiated": [f"{ONT}#V_34", f"{ONT}#V_11", f"{ONT}#V_115"],
        "ports": [f"{LIB}#V_117", f"{LIB}#V_118", f"{LIB}#V_56",
                  f"{LIB}#V_109", f"{LIB}#V_104", f"{LIB}#V_122"],
        "outputs": [f"{LIB}#V_121", f"{LIB}#V_113"],
    }
    st, out = req("PUT", f"{API}/behaviour/assignment"
                         f"?graph={urllib.parse.quote(ASG, safe='')}",
                  sel)
    if st != 200:
        failures.append(("lumped", f"PUT {st}: {str(out)[:300]}"))
    else:
        print(f"etype_lumped: PUT {st} closed={out.get('closed')}")
        for u in out.get("unresolved", []):
            print("  unresolved:", u["variable"].split("#")[-1])

    # -- etype_lumped_qss: same wiring, no P/v machinery --------------
    sel = {
        "entity_type": f"{ONT}#etype_lumped_qss",
        "sequence": [
            f"{LIB}#E_m_def", f"{LIB}#E_F_g", f"{LIB}#E_dPdt",
            f"{LIB}#E_z", f"{LIB}#E_fKin", f"{LIB}#E_fPot",
            f"{LIB}#E_fPflow", f"{LIB}#E_aw", f"{LIB}#E_al",
            f"{LIB}#E_amech", f"{LIB}#E_dEmdt", f"{LIB}#E_29"],
        "base_equation": f"{LIB}#E_29",
        "state_variables": [f"{LIB}#V_57"],
        "instantiated": [f"{ONT}#V_34", f"{ONT}#V_11", f"{ONT}#V_115"],
        "ports": [f"{LIB}#V_117", f"{LIB}#V_118", f"{LIB}#V_56",
                  f"{LIB}#V_109", f"{LIB}#V_104", f"{LIB}#V_122"],
        "outputs": [f"{LIB}#V_121", f"{LIB}#V_113"],
    }
    st, out = req("PUT", f"{API}/behaviour/assignment"
                         f"?graph={urllib.parse.quote(ASG, safe='')}",
                  sel)
    if st != 200:
        failures.append(("qss", f"PUT {st}: {str(out)[:300]}"))
    else:
        print(f"etype_lumped_qss: PUT {st} closed={out.get('closed')}")
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
    print("\nqss energy wired — v_str is the contact velocity everywhere")


if __name__ == "__main__":
    main()
