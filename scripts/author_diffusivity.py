#!/usr/bin/env python3
"""Author ``D_s`` + the ionic-conductivity layer (§57).

Follows the stage-1/2 author-script pattern (PUT/POST against the
live API; library graph).

  ``D_s``   species diffusivity [N,S] — the §57 irreducible
            kinetic datum (the v/tau slot of the coefficient
            skeleton): species data, physical network, parameter
            class, token-neutral like every coefficient.
  ``kel``   ionic conductivity [N] — node-bound material property
            (S/m), the kappa-side of the leg conductance.  Carries
            ``E_kEl_ionic`` verbatim:
            ``kel := F^2/(R*T) * sum_S z_s^2 * D_s * c_s``
            (Nernst-Einstein).  ``kEl`` keeps its stage-1 primitive
            leg-conductance status [A_el] in S — the ``G = kappa*A/L``
            conversion waits on arc-geometry params (Ae/Le), the
            recorded open fold (§57).

Idempotent — safe to re-run; refresh PUT re-canonicalises
incidence.
"""
import json
import sys
import urllib.parse
import urllib.request

HOST = "http://localhost:8000"
EQ = f"{HOST}/api/equation"
LIB = "https://w3id.org/promo/library"
ONT = "https://w3id.org/promo/ontology"

IDX_N = f"{ONT}#idx_node"
IDX_S = f"{ONT}#idx_species"

AX_DET = f"{ONT}#axis_determination_physical"
AX_FUN = f"{ONT}#axis_function_physical"
AX_ROLE = f"{ONT}#axis_role_information"
T_DET_CONST = f"{ONT}#term_determination_constant"
T_FUN_PARAM = f"{ONT}#term_function_parameter"
T_ROLE_PAR = f"{ONT}#term_info_role_parameter"

# units: (time, length, amount, mass, temperature, current, light, nil)
U_DIFFUSIVITY = [-1, 2, 0, 0, 0, 0, 0, 0]   # m^2/s

V_DS = f"{LIB}#V_142"
V_KEL = f"{LIB}#V_143"

D_S = {
    "iri": V_DS,
    "label": "D_s",
    "network": "physical",
    "domain_iri": f"{ONT}#domain_physical",
    "type": None,
    "units": U_DIFFUSIVITY,
    "index_structures": [IDX_N, IDX_S],
    "internal_id": "V_142",
    "aliases": {"latex": "{D}_{s}", "global_ID": V_DS},
    "doc": (
        "species diffusivity — the §57 irreducible kinetic datum "
        "(the v/tau slot of the coefficient skeleton): mobility of "
        "species s in the medium of lump n.  Species data, "
        "value-cell bound on the S axis like z_el/nu.  Drives the "
        "Nernst-Einstein conductivity in E_kEl_ionic."
    ),
    "port_variable": False,
    "frozen": False,
    "tokens": [],
    "token_vector": None,
    "value": None,
    "equations": {},
    "classifications": {
        AX_DET: T_DET_CONST,
        AX_FUN: T_FUN_PARAM,
        AX_ROLE: T_ROLE_PAR,
    },
}


# units: (time, length, amount, mass, temperature, current, light, nil)
U_CONDUCTIVITY = [3, -3, 0, -1, 0, 2, 0, 0]  # S/m

KEL = {
    "iri": V_KEL,
    "label": "kel",
    "network": "macroscopic",
    "domain_iri": f"{ONT}#domain_macroscopic",
    "type": None,
    "units": U_CONDUCTIVITY,
    "index_structures": [IDX_N],
    "internal_id": "V_143",
    "aliases": {"latex": "{\\kappa}^{el}", "global_ID": V_KEL},
    "doc": (
        "ionic conductivity — electrolyte material property [N], "
        "derived not primitive: Nernst-Einstein mobility sum of the "
        "charged species in the lump (§57).  The content-density x "
        "drift-speed skeleton of §19.  Leg conductance kEl stays "
        "primitive until the kappa*A/L geometry fold lands (Ae/Le "
        "arc params)."
    ),
    "port_variable": False,
    "frozen": False,
    "tokens": [],
    "token_vector": None,
    "value": None,
    "equations": {
        "E_kEl_ionic": {
            "iri": f"{LIB}#E_kEl_ionic",
            "internal_id": "E_kEl_ionic",
            "lhs": V_KEL,
            "rhs": "( ( physical!const_F * physical!const_F ) * "
                   "inv( ( physical!R * physical!T ) ) * "
                   "reduceSum( ( physical!z_el * physical!z_el * "
                   "physical!D_s * c ), S ) )",
            "equation_class": f"{ONT}#eqclass_generic",
            "network": "macroscopic",
            "doc": "ionic conductivity — Nernst-Einstein "
                   "F^2/(RT)*sum_S z^2*D_s*c_s; kappa-side of the "
                   "leg conductance (§57)",
        },
    },
    "classifications": {
        AX_DET: T_DET_CONST,
        AX_FUN: f"{ONT}#term_function_coefficient",
        AX_ROLE: T_ROLE_PAR,
    },
}

VARS = [D_S, KEL]


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
    g = urllib.parse.quote(LIB, safe="")
    st, ctx = req("GET", f"{EQ}/context?graph={g}")
    if st != 200:
        print(f"FATAL context: {st} {str(ctx)[:200]}")
        sys.exit(1)
    existing = {v["iri"] for v in ctx["variables"]}

    for rec in VARS:
        iri = rec["iri"]
        put = iri in existing
        st, out = req("PUT" if put else "POST",
                      (f"{EQ}/variables/{urllib.parse.quote(iri, safe='')}?graph={g}"
                       if put else f"{EQ}/variables?graph={g}"),
                      rec)
        if st not in (200, 201):
            print(f"FAIL {rec['label']}: {st} {str(out)[:400]}",
                  file=sys.stderr)
            sys.exit(1)
        print(f"{rec['label']}: {'PUT' if put else 'POST'} {st}")

    # Refresh pass — lets _canonicalise_equations derive incidence
    # cleanly once every referenced var exists (stage-1/2 pattern).
    for rec in VARS:
        if not rec["equations"]:
            continue
        iri = rec["iri"]
        st, out = req("PUT",
                      f"{EQ}/variables/{urllib.parse.quote(iri, safe='')}?graph={g}",
                      rec)
        if st != 200:
            print(f"FAIL {rec['label']} refresh: {st} {str(out)[:300]}",
                  file=sys.stderr)
            sys.exit(1)
        print(f"{rec['label']} refresh: PUT {st}")

    # Read-only confirmation of the landed equation's derived type.
    st, ctx = req("GET", f"{EQ}/context?graph={g}")
    payload = {
        "variables": ctx["variables"],
        "indices": ctx["indices"],
        "network_tree": ctx["network_tree"],
        "variable_definition_network": "macroscopic",
        "expression_definition_network": "macroscopic",
        "lhs": "kel",
        "text": KEL["equations"]["E_kEl_ionic"]["rhs"],
    }
    st, out = req("POST", f"{EQ}/check", payload)
    print("--- check E_kEl_ionic on kel:", json.dumps(
        {k: out.get(k) for k in
         ("ok", "units_pretty", "indices", "error", "error_kind")}))

    print("D_s + kel (ionic conductivity) authored")


if __name__ == "__main__":
    main()
