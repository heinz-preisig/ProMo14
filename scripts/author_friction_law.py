#!/usr/bin/env python3
"""§46 follow-up — Darcy friction law on `fl` (authored 2026-11-24 PM).

Replaces the *imposed* boundary port with the constitutive law the
§46 ruling queued:  fl = λ·(L/d)·ṁ·v²/2  (Darcy-Weisbach dissipated
power per convection contact).  `fl` stays a port — the lump still
gathers it via `al` (E_63) — but the transport now *computes* it.

New transport-side parameters (all bound [A_conv], the arc being the
pipe; value-bound at instantiation → `instantiated`):

- lam  — Darcy friction factor, dimensionless
- Lp   — pipe length, m      (`d` is taken — the direction var V_26)
- dp   — pipe diameter, m

Equation (index trace: [A]·[A]·([A,N]·[A,N]) → [A,N] = declared):
    fl := (half * lam) * ((Lp * inv(dp))
          * (fmc * reduceSum((v_str * v_str), C)))

`v_str` is the transport's stream velocity — the dissipation lives in
the pipe, not the lump's bulk `v`.  v² folds component-wise per the
§41 convention.

Assignment wiring (etype_convection_transport): E_fl enters the
sequence after E_fP; fl joins `outputs` (computed export, same role
as fP/fmom/v_str/fmc); lam/Lp/dp join `instantiated`.  The lump-side
consumption path (al/dEmdt/dHdt into an assignment) is the separate
energy-balance wiring item.

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
ASG = "https://w3id.org/promo/library/assignments"

IDX_AC = f"{ONT}#idx_arc_convection"
T_DET_VAR = f"{ONT}#term_determination_variable"
T_FUN_PARAM = f"{ONT}#term_function_parameter"
AX_DET = f"{ONT}#axis_determination_physical"
AX_FUN = f"{ONT}#axis_function_physical"
EQ_GENERIC = f"{ONT}#eqclass_generic"

CLS_PARAM = {AX_DET: T_DET_VAR, AX_FUN: T_FUN_PARAM}
U_DIMLESS = [0, 0, 0, 0, 0, 0, 0, 0]
U_LENGTH = [0, 1, 0, 0, 0, 0, 0, 0]


def req(method, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def var(frag, label, doc, *, units, latex):
    iri = f"{LIB}#{frag}"
    return {
        "iri": iri,
        "label": label,
        "network": "macroscopic",
        "domain_iri": None,
        "type": None,                       # derive from classifications
        "units": units,
        "index_structures": [IDX_AC],
        "internal_id": frag,
        "aliases": {"latex": latex, "global_ID": iri},
        "doc": doc,
        "port_variable": False,
        "frozen": False,
        "tokens": [],                       # coefficients/geometry neutral
        "token_vector": None,
        "value": None,
        "equations": {},
        "classifications": CLS_PARAM,
    }


NEW_VARS = [
    var("V_123", "lam",
        "Darcy friction factor on a convection arc — the pipe's "
        "resistance coefficient; value bound at instantiation "
        "(eventually a function of Re/roughness).",
        units=U_DIMLESS, latex="{\\lambda}"),
    var("V_124", "Lp",
        "pipe length of the convection arc, m — transport-side "
        "geometry bound at instantiation.",
        units=U_LENGTH, latex="{L}"),
    var("V_125", "dp",
        "pipe diameter of the convection arc, m — `d` is taken by the "
        "direction var; can later constrain Ayz.",
        units=U_LENGTH, latex="{d}_{p}"),
]

E_FL_RHS = ("( ( half * macroscopic!lam ) * ( ( macroscopic!Lp * "
            "inv( macroscopic!dp ) ) * ( macroscopic!fmc * "
            "reduceSum( ( macroscopic!v_str * macroscopic!v_str ), "
            "C ) ) ) )")


def main():
    st, ctx = req("GET", f"{BASE}/context?graph={LIB}")
    assert st == 200, ctx
    existing = {v["iri"]: v for v in ctx["variables"]}
    failures = []

    # -- new params (POST; PUT if present — idempotent re-run) --------
    for rec in NEW_VARS:
        iri = rec["iri"]
        enc = urllib.parse.quote(iri, safe="")
        g = urllib.parse.quote(LIB, safe="")
        method = "PUT" if iri in existing else "POST"
        url = (f"{BASE}/variables/{enc}?graph={g}" if method == "PUT"
               else f"{BASE}/variables?graph={g}")
        st, out = req(method, url, rec)
        if st != 200:
            failures.append((iri, f"{method} {st}: {str(out)[:300]}"))
        else:
            print(f"{iri.split('#')[-1]} {rec['label']}: {method} {st}")

    # -- fl gains its constitutive equation -----------------------------
    fl_iri = f"{LIB}#V_109"
    fl = existing[fl_iri]
    fl["doc"] = (
        "friction-dissipation flow on a convection contact — Darcy law "
        "lam·(Lp/dp)·fmc·v_str²/2; mechanical energy converted to "
        "thermal, gathered by the lump as al.  Port export (imposed "
        "boundary port before E_fl).")
    fl["equations"]["E_fl"] = {
        "iri": f"{LIB}#E_fl",
        "internal_id": "E_fl",
        "lhs": fl_iri,
        "rhs": E_FL_RHS,
        "equation_class": EQ_GENERIC,
        "network": "macroscopic",
        "doc": "Darcy-Weisbach dissipated power per contact — "
               "λ·(L/d)·ṁ·v²/2 (§46 follow-up: constitutive law "
               "replacing the imposed port).",
    }
    enc = urllib.parse.quote(fl_iri, safe="")
    st, out = req("PUT", f"{BASE}/variables/{enc}"
                         f"?graph={urllib.parse.quote(LIB, safe='')}", fl)
    if st != 200:
        failures.append((fl_iri, f"PUT fl {st}: {str(out)[:300]}"))
    else:
        print(f"V_109 fl: PUT {st} eqs={sorted(out['equations'])}")

    # -- transport assignment: E_fl sequenced, fl exported, params in --
    g = urllib.parse.quote(ASG, safe="")
    et = f"{ONT}#etype_convection_transport"
    sel = {
        "entity_type": et,
        "sequence": [f"{LIB}#E_4", f"{LIB}#E_v_str", f"{LIB}#E_fmom",
                     f"{LIB}#E_fP", f"{LIB}#E_fl", f"{LIB}#E_29"],
        "base_equation": f"{LIB}#E_29",
        "state_variables": [],
        "instantiated": [f"{LIB}#V_57", f"{ONT}#F_conv",
                         f"{LIB}#V_123", f"{LIB}#V_124", f"{LIB}#V_125"],
        "ports": [f"{ONT}#V_34"],
        "outputs": [f"{LIB}#V_117", f"{LIB}#V_118", f"{LIB}#V_122",
                    f"{LIB}#V_56", fl_iri],
    }
    st, out = req("PUT", f"{API}/behaviour/assignment?graph={g}", sel)
    if st != 200:
        failures.append(("assignment", f"PUT {st}: {str(out)[:300]}"))
    else:
        print(f"convection_transport: PUT {st} closed={out.get('closed')}")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" ", f)
        sys.exit(1)

    # -- save immediately (reload footgun) ------------------------------
    st, out = req("POST", f"{API}/ontology/save")
    print("save:", out)

    print("\nDarcy law authored — fl is computed, lam/Lp/dp instantiated")


if __name__ == "__main__":
    main()
