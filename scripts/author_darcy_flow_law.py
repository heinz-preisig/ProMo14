#!/usr/bin/env python3
"""Darcy flow-law alternatives — quadratic Δp∝v² constitutives beside the
linear kConvX laws (authored 2026-11-25).

Design ruling (session discussion): the pressure-driven direction —
pressure drop across a flow network determines the branch flows — is
already the authored structure (E_4: fmc = kConvX·Ayz·Δp; E_v_str:
v_str = e_align·kConvX/ρ·Δp).  Darcy-Weisbach is the QUADRATIC
resistance law Δp = λ·(L/d)·ρ·v²/2 → v = sign(Δp)·√(|Δp|·d/(λ·L·ρ·½)).
It cannot fold into the linear kConvX form, so it lands as ALTERNATIVE
equations on the same lhs — the assignment sequence picks the regime
(E_P_def vs E_P_int precedent).  No assignment wiring here: the BL
user swaps E_4→E_fmc_darcy and E_v_str→E_v_str_darcy to take the Darcy
regime; mixed models would need a sibling etype.

    D := reduceSum( (sigma * p_mech), X )          -- signed contact Δp
    v_str := e_align · sign(D)·√(|D|·dp·inv(λ)·inv(Lp)·inv(ρ)·inv(½))
    fmc   := (ρ·Ayz) · sign(D)·√(|D|·dp·inv(λ)·inv(Lp)·inv(ρ)·inv(½))

fmc derives consistently as ρ·A·v_n with the same Darcy velocity — so
fmom = fmc·v_str and fl = λ·(L/d)·ṁ·v²/2 = |Δp|·ṁ stay coherent (the
dissipated power then equals the pressure drop times the mass flow).

RELOAD FOOTGUN: run this, then save immediately — do not edit any
file under the watched tree between mutation and save.
"""
import json
import sys
import urllib.parse
import urllib.request

API = "http://localhost:8000/api"
BASE = f"{API}/equation"
LIB = "https://w3id.org/promo/library"
ONT = "https://w3id.org/promo/ontology"

EQ_GENERIC = f"{ONT}#eqclass_generic"

# signed pressure drop over the contact, per direction X
D = "reduceSum( ( physical!sigma * physical!p_mech ), X )"

# |D|·dp·λ⁻¹·Lp⁻¹·ρ⁻¹·(½)⁻¹   —  v² under the Darcy law
SQ = ("( abs( %s ) * ( ( macroscopic!dp * inv( macroscopic!lam ) ) * "
      "( inv( macroscopic!Lp ) * ( inv( properties!rho ) * "
      "inv( universe!half ) ) ) ) )" % D)

# sign(D)·√(...)   —  the Darcy stream velocity magnitude+sign
V = "( sign( %s ) * sqrt( %s ) )" % (D, SQ)

E_V_STR_DARCY = ("( physical!e_align * %s )" % V)
E_FMC_DARCY = ("( ( properties!rho * geometry!Ayz ) * %s )" % V)

NEW_EQS = [
    (f"{LIB}#V_122", "v_str", "E_v_str_darcy", E_V_STR_DARCY,
     "stream velocity under the Darcy-Weisbach law — alternative to "
     "E_v_str (linear kConvX conductance): v = sign(Δp)·√(|Δp|·dp/"
     "(λ·Lp·ρ·½)) — quadratic Δp∝v² regime; the BL sequence picks one."),
    (f"{LIB}#V_56", "fmc", "E_fmc_darcy", E_FMC_DARCY,
     "mass flow under the Darcy-Weisbach law — alternative to E_4 "
     "(linear kConvX conductance): fmc = ρ·Ayz·v_darcy with v_darcy "
     "the quadratic-law stream velocity; pair with E_v_str_darcy."),
]


def req(method, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r) as resp:
            body = resp.read()
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    st, ctx = req("GET", f"{BASE}/context?graph={LIB}")
    assert st == 200, ctx
    existing = {v["iri"]: v for v in ctx["variables"]}
    failures = []

    for iri, label, eq_id, rhs, doc in NEW_EQS:
        rec = existing[iri]
        rec["equations"][eq_id] = {
            "iri": f"{LIB}#{eq_id}",
            "internal_id": eq_id,
            "lhs": iri,
            "rhs": rhs,
            "equation_class": EQ_GENERIC,
            "network": "macroscopic",
            "doc": doc,
        }
        enc = urllib.parse.quote(iri, safe="")
        st, out = req("PUT", f"{BASE}/variables/{enc}"
                             f"?graph={urllib.parse.quote(LIB, safe='')}",
                      rec)
        if st != 200:
            failures.append((eq_id, f"PUT {st}: {str(out)[:400]}"))
        else:
            print(f"{label} {iri.split('#')[-1]}: PUT {st} "
                  f"eqs={sorted(out['equations'])}")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" ", f)
        sys.exit(1)

    # -- consistency report --------------------------------------------
    st, rep = req("GET", f"{BASE}/consistency"
                         f"?graph={urllib.parse.quote(LIB, safe='')}")
    if st == 200:
        print("consistency:", json.dumps(rep)[:300])

    # -- save immediately (reload footgun) ------------------------------
    st, out = req("POST", f"{API}/ontology/save")
    print("save:", out)

    print("\nDarcy alternatives authored — BL sequence picks the regime")


if __name__ == "__main__":
    main()
