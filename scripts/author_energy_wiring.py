#!/usr/bin/env python3
"""§50 mechanical-energy wiring on etype_lumped (authored 2026-11-24 PM).

Wires the §46 mechanical balance into the dynamic lumped assignment —
fl's first live consumer.  dEmdt := amech + aw − al, diagnostic
output (balances are readings; mass+momentum stay the integrated
contents).  dHdt/dEtotdt stay unwired: their enthalpy leg
(reduceSum(ah, S)) pulls the species layer — separate item.

New equation (the §48 pattern applied, not a new ruling):

- E_P_int on V_119:  P := Integral(dPdt :: t in [to, t])
  The dPdt state slot IS P; the running-integral alias is the
  dimensionally honest record (kg·m·s⁻¹·s = kg·m·s⁻¹) and emits the
  slot name like E_m_def does for m.  E_P_def (P := m·v) stays for
  models that compute P — it would loop against v := P·inv(m) here.

Selection deltas on etype_lumped:

- sequence  += E_P_int, E_v_fromP, E_fKin, E_fPot, E_fPflow,
              E_aw, E_al, E_amech, E_dEmdt   (E_29 still closes)
- ports     += fl (V_109 — gathered via al), fWs (V_104 — via aw)
- instantiated += r (V_115 — node position, geometric datum; fPot)
- outputs   += dEmdt (V_113 — the mechanical-balance reading)

QSS sibling untouched: without the dPdt state there is no P slot, so
v := P·inv(m) cannot fire — the quasi-steady energy wiring waits on
the §47 upgrade (ΣF(v)=0 determining v).

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
EQ_GENERIC = f"{ONT}#eqclass_generic"


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

    # -- E_P_int: the dPdt slot's content alias (§48 pattern) ----------
    p_iri = f"{LIB}#V_119"
    p_rec = existing[p_iri]
    p_rec["equations"]["E_P_int"] = {
        "iri": f"{LIB}#E_P_int",
        "internal_id": "E_P_int",
        "lhs": p_iri,
        "rhs": ("Integral( macroscopic!dPdt :: t in "
                "[ to, t ] )"),
        "equation_class": EQ_GENERIC,
        "network": "macroscopic",
        "doc": "content-of-state alias — the dPdt slot carries P; "
               "running integral like E_m_def (§48 pattern).",
    }
    enc = urllib.parse.quote(p_iri, safe="")
    st, out = req("PUT", f"{API}/equation/variables/{enc}?graph={g}",
                  p_rec)
    if st != 200:
        failures.append((p_iri, f"PUT {st}: {str(out)[:300]}"))
    else:
        print(f"V_119 P: PUT {st} eqs={sorted(out['equations'])}")

    # -- extended lumped assignment ------------------------------------
    sel = {
        "entity_type": f"{ONT}#etype_lumped",
        "sequence": [
            f"{LIB}#E_m_def", f"{LIB}#E_P_int", f"{LIB}#E_v_fromP",
            f"{LIB}#E_F_g", f"{LIB}#E_dPdt",
            f"{LIB}#E_fKin", f"{LIB}#E_fPot", f"{LIB}#E_fPflow",
            f"{LIB}#E_aw", f"{LIB}#E_al", f"{LIB}#E_amech",
            f"{LIB}#E_dEmdt", f"{LIB}#E_29"],
        "base_equation": f"{LIB}#E_29",
        "state_variables": [f"{LIB}#V_121", f"{LIB}#V_57"],
        "instantiated": [f"{ONT}#V_34", f"{ONT}#V_11", f"{ONT}#V_115"],
        "ports": [f"{LIB}#V_117", f"{LIB}#V_118", f"{LIB}#V_56",
                  f"{LIB}#V_109", f"{LIB}#V_104"],
        "outputs": [f"{LIB}#V_121", f"{LIB}#V_113"],
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
    print("\nmechanical balance wired — fl gathered via al into dEmdt")


if __name__ == "__main__":
    main()
