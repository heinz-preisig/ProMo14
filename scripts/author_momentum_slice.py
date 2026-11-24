#!/usr/bin/env python3
"""ONE-TIMER — applied 2026-11-24.  Safe to delete on cleanup.

§41 momentum slice — authored via the equation API (the editor write
path).  Two subjects, per ruling:

Fluid mechanics (convection transport scope)
- fP    [A_conv,C,N] port — contact pressure force:
        e_align * (sigma * p_mech) * Ayz       per-contact [X,C] rows
- v_str [A_conv,C,N] port — stream velocity:
        e_align * (kConvX * inv(rho) * reduceSum(sigma*p_mech, X))
  NOTE: the first pass put this equation on `v` and flipped
  port_variable — the write path 409'd (§18 structural lock, 12
  referencing equations).  v_str is the semantically better split
  anyway: the transport's stream velocity is not the lump's bulk v.
  SECOND NOTE: the first spelling used fmc·inv(rho·Ayz) — the emit
  rejected it (e_align{X,C} × fmc{A_conv,N} = outer product, index
  axes pair by NAME not bound elements).  Re-spelled X-typed:
  e_align·(kConvX·inv(rho)·Σσp,X) — u = k·Δp/ρ ≡ fmc/(ρ·A) via E_4.
- fmom  [C,N] port — convected momentum flow:  fmc * v_str

Contact exports declare the mechanism's arc index [A_conv,C,N]
(fmc precedent) — the N slot is what the peer gathers on.

Mechanics (lumped capacity scope)
- P     [C,N]      — bulk momentum content:    m * v  (definitional)
- F_g   [C,N]      — body force:               m * g * e_z
- dPdt  [C,N]      — momentum balance:
        reduceSum(F_conv * (fmom + fP), A_conv) + F_g

Units order: [t, L, n, M, I, T, N, J].  Index order [C,N] matches the
fold's component-first convention (v[C,N], r[C,N]).
"""
import json
import sys
import urllib.parse
import urllib.request

BASE = "http://localhost:8000/api/equation"
LIB = "https://w3id.org/promo/library"
ONT = "https://w3id.org/promo/ontology"

IDX_C = f"{ONT}#idx_component"
IDX_N = f"{ONT}#idx_node"
IDX_AC = f"{ONT}#idx_arc_convection"
TOK_MOM = f"{ONT}#token_momentum"
TOK_MASS = f"{ONT}#token_mass"
AX_DET = f"{ONT}#axis_determination_physical"
AX_EXT = f"{ONT}#axis_extensity"
AX_FUN = f"{ONT}#axis_function_physical"
T_DET_VAR = f"{ONT}#term_determination_variable"
T_EXT_EXT = f"{ONT}#term_extensity_extensive"
T_FUN_STATE = f"{ONT}#term_function_state"
T_FUN_FLOW = f"{ONT}#term_function_flow"
EQ_GENERIC = f"{ONT}#eqclass_generic"

U_FORCE = [-2, 1, 0, 1, 0, 0, 0, 0]   # momentum rate / force
U_MOM = [-1, 1, 0, 1, 0, 0, 0, 0]     # momentum content

CLS_FLOW = {AX_DET: T_DET_VAR, AX_EXT: T_EXT_EXT, AX_FUN: T_FUN_FLOW}
CLS_STATE = {AX_DET: T_DET_VAR, AX_EXT: T_EXT_EXT, AX_FUN: T_FUN_STATE}


def req(method, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def eq(frag, internal_id, lhs_iri, rhs, doc=""):
    return {
        "iri": f"{LIB}#{frag}",
        "internal_id": internal_id,
        "lhs": lhs_iri,
        "rhs": rhs,
        "equation_class": EQ_GENERIC,
        "network": "macroscopic",
        "doc": doc,
    }


def var(frag, label, rhs_doc, *, port, cls, units, equations,
        latex=None, tokens=None, index_structures=None):
    iri = f"{LIB}#{frag}"
    return {
        "iri": iri,
        "label": label,
        "network": "macroscopic",
        "domain_iri": None,
        "type": None,                       # derive from classifications
        "units": units,
        "index_structures": (index_structures
                             if index_structures is not None
                             else [IDX_C, IDX_N]),
        "internal_id": frag,
        "aliases": ({"latex": latex, "global_ID": iri}
                    if latex else {"global_ID": iri}),
        "doc": rhs_doc,
        "port_variable": port,
        "frozen": False,
        "tokens": [TOK_MOM] if tokens is None else tokens,
        "token_vector": None,
        "value": None,
        "equations": equations,
        "classifications": cls,
    }


NEW_VARS = [
    var("V_117", "fP",
        "contact pressure force — e_align·(σ·p_mech)·A per contact; the "
        "X↔C placement lands the transport's axial force on its aligned "
        "C component.  Port export gathered [A_conv,C] by the peer.",
        port=True, cls=CLS_FLOW, units=U_FORCE, latex="{f}^{p}",
        index_structures=[IDX_AC, IDX_C, IDX_N],
        equations={
            "E_fP": eq("E_fP", "E_fP", f"{LIB}#V_117",
                       "( physical!e_align * ( ( physical!sigma * "
                       "physical!p_mech ) * geometry!Ayz ) )"),
        }),
    var("V_118", "fmom",
        "convected momentum flow — fmc·v_str per contact; the transport "
        "exports the momentum its stream carries.  Port export gathered "
        "[A_conv,C] by the peer.",
        port=True, cls=CLS_FLOW, units=U_FORCE, latex="{\\hat{P}}^{c}",
        index_structures=[IDX_AC, IDX_C, IDX_N],
        equations={
            "E_fmom": eq("E_fmom", "E_fmom", f"{LIB}#V_118",
                         "( macroscopic!fmc * macroscopic!v_str )"),
        }),
    var("V_122", "v_str",
        "stream velocity on a transport — u = kConvX·Δp/ρ "
        "(= fmc/(ρ·A) via the flow law) projected onto C via e_align.  "
        "Port so its node index gathers on the peer; on the transport "
        "scope it binds {A_conv,C,N} like fmc.",
        port=True, cls={AX_DET: T_DET_VAR,
                        AX_EXT: T_EXT_EXT,
                        AX_FUN: f"{ONT}#term_function_frame"},
        units=[-1, 1, 0, 0, 0, 0, 0, 0], latex="{v}^{s}",
        # momentum only — a mass token here makes v_str a second
        # candidate for the capacity's mass-flow port (ambiguous-port)
        tokens=[TOK_MOM],
        index_structures=[IDX_AC, IDX_C, IDX_N],
        equations={
            "E_v_str": eq("E_v_str", "E_v_str", f"{LIB}#V_122",
                          "( physical!e_align * ( ( kConvX * "
                          "inv( properties!rho ) ) * reduceSum( "
                          "( physical!sigma * physical!p_mech ), X ) ) )"),
        }),
    var("V_119", "P",
        "momentum content vector [C,N] — bulk momentum of the lumped "
        "body.  Definitional P = m·v; the dPdt balance is the dynamic "
        "regime (assignment picks).",
        port=False, cls=CLS_STATE, units=U_MOM, latex="{P}",
        equations={
            "E_P_def": eq("E_P_def", "E_P_def", f"{LIB}#V_119",
                          "( macroscopic!m * macroscopic!v )"),
        }),
    var("V_120", "F_g",
        "body force — gravity m·g projected on z via the e_z basis "
        "vector (§41 selection).",
        port=False, cls=CLS_FLOW, units=U_FORCE, latex="{F}_{g}",
        equations={
            "E_F_g": eq("E_F_g", "E_F_g", f"{LIB}#V_120",
                        "( ( macroscopic!m * g ) * physical!e_z )"),
        }),
    var("V_121", "dPdt",
        "momentum balance — per-component conservation: convected "
        "momentum + contact pressure force via the convection incidence "
        "row, plus body force.",
        port=False, cls=CLS_STATE, units=U_FORCE, latex="\\dot{P}",
        equations={
            "E_dPdt": eq("E_dPdt", "E_dPdt", f"{LIB}#V_121",
                         "( reduceSum( ( physical!F_conv * "
                         "( macroscopic!fmom + macroscopic!fP ) ), "
                         "A_conv ) + macroscopic!F_g )"),
        }),
]


def main():
    st, ctx = req("GET", f"{BASE}/context?graph={LIB}")
    assert st == 200, ctx
    existing = {v["iri"] for v in ctx["variables"]}
    v116 = next(v for v in ctx["variables"]
                if v["iri"].endswith("#V_116"))

    # -- new vars (POST; PUT if already present — idempotent re-run) --
    failures = []
    for rec in NEW_VARS:
        iri = rec["iri"]
        enc = urllib.parse.quote(iri, safe="")
        g = urllib.parse.quote(LIB, safe="")
        if iri in existing:
            st, out = req("PUT", f"{BASE}/variables/{enc}?graph={g}", rec)
        else:
            st, out = req("POST", f"{BASE}/variables?graph={g}", rec)
        if st != 200:
            failures.append((iri, f"write {st}: {str(out)[:300]}"))
        else:
            print(f"{iri.split('#')[-1]} {rec['label']}: {'PUT' if iri in existing else 'POST'} {st}")

    # -- v: mechanics-side equation only (port_variable is §18-locked)
    v_rec = v116
    v_rec["doc"] = (v_rec.get("doc", "")
                    + "  Stream-velocity role on transports lives on "
                      "v_str (port); v stays the lump's bulk velocity.")
    v_rec["equations"]["E_v_fromP"] = eq(
        "E_v_fromP", "E_v_fromP", v116["iri"],
        "( macroscopic!P * inv( macroscopic!m ) )",
        doc="mechanics-side velocity — v = P/m when P is the state")
    enc = urllib.parse.quote(v116["iri"], safe="")
    st, out = req("PUT", f"{BASE}/variables/{enc}"
                         f"?graph={urllib.parse.quote(LIB, safe='')}",
                  v_rec)
    if st != 200:
        failures.append((v116["iri"], f"PUT v {st}: {str(out)[:300]}"))
    else:
        print(f"V_116 v: PUT {st} port={out.get('port_variable')} "
              f"eqs={sorted(out['equations'])}")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" ", f)
        sys.exit(1)
    print("\nall records authored")


if __name__ == "__main__":
    main()
