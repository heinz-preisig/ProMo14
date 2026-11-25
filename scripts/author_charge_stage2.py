#!/usr/bin/env python3
"""Author the §57 electrochemistry var/expr layer via the API.

Derivation-driven stage 2 (design record in
docs/behaviour-linker-design-discussion.md §57).  No new entity
types or assignments — the electrode remains the §32 pairing
consumer.  Lands:

  ``z_el``     species valence [S]          — physical param (cells)
               (not ``z`` — that label is the spatial coordinate)
  ``const_F``  Faraday constant []          — physical constant, bound
  ``mu_el``    electrochemical potential [N,S] — macroscopic effort,
               ``E_mu_el: mu_el := mu + z*const_F*Ue``
  ``Pel``      electric transfer [A_el,N]    — macroscopic port,
               ``E_Pel: Pel := Ue*fe``
  ``E_qel_species``  alternative on ``qel``: qel := Σ_S z·F·n
  ``E_fnd_el``       alternative on ``fnd``: σ·mu_el driven flux

Idempotent — safe to re-run.  A second PUT pass refreshes
incidence for equations whose rhs references vars created earlier
in the same run.
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
IDX_AEL = f"{ONT}#idx_arc_charge"
IDX_ADIFF = f"{ONT}#idx_arc_diffusion"
TOK_CHARGE = f"{ONT}#token_charge"
TOK_CM = f"{ONT}#token_component_mass"
TOK_ENERGY = f"{ONT}#token_energy"

AX_DET = f"{ONT}#axis_determination_physical"
AX_EXT = f"{ONT}#axis_extensity"
AX_FUN = f"{ONT}#axis_function_physical"
AX_ROLE = f"{ONT}#axis_role_information"
T_DET_VAR = f"{ONT}#term_determination_variable"
T_DET_CONST = f"{ONT}#term_determination_constant"
T_EXT_EXT = f"{ONT}#term_extensity_extensive"
T_EXT_INT = f"{ONT}#term_extensity_intensive"
T_FUN_FLOW = f"{ONT}#term_function_flow"
T_FUN_EFFORT = f"{ONT}#term_function_effort"
T_FUN_PARAM = f"{ONT}#term_function_parameter"
T_ROLE_PAR = f"{ONT}#term_info_role_parameter"
T_ROLE_OUT = f"{ONT}#term_info_role_output"
EQ_GENERIC = f"{ONT}#eqclass_generic"

# units: (time, length, amount, mass, temperature, current, light, nil)
U_NONE = [0] * 8
U_MOL_CHG = [1, 0, -1, 0, 0, 1, 0, 0]        # C/mol
U_J_MOL = [-2, 2, -1, 1, 0, 0, 0, 0]          # J/mol  (same as mu)
U_WATT = [-3, 2, 0, 1, 0, 0, 0, 0]            # W = J/s
U_MOL_S = [-1, 0, 1, 0, 0, 0, 0, 0]           # mol/s  (fnd's units)

CLS_EFFORT = {AX_DET: T_DET_VAR, AX_EXT: T_EXT_INT, AX_FUN: T_FUN_EFFORT}
CLS_FLOW = {AX_DET: T_DET_VAR, AX_EXT: T_EXT_EXT, AX_FUN: T_FUN_FLOW,
            AX_ROLE: T_ROLE_OUT}
CLS_PARAM = {AX_DET: T_DET_CONST, AX_FUN: T_FUN_PARAM,
             AX_ROLE: T_ROLE_PAR}

V_N = f"{LIB}#V_6"            # n   [N,S] physical
V_MU = f"{LIB}#V_35"          # mu  [N,S] physical
V_QEL = f"{LIB}#V_130"
V_FE = f"{LIB}#V_132"
V_UE = f"{LIB}#V_133"
V_Z = f"{LIB}#V_137"
V_CF = f"{LIB}#V_138"
V_MUEL = f"{LIB}#V_139"
V_PEL = f"{LIB}#V_140"
V_FND = f"{LIB}#V_79"


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


def eq(frag, lhs_iri, rhs, doc="", network="macroscopic"):
    return {
        "iri": f"{LIB}#{frag}",
        "internal_id": frag,
        "lhs": lhs_iri,
        "rhs": rhs,
        "equation_class": EQ_GENERIC,
        "network": network,
        "doc": doc,
    }


def var(frag, label, doc, *, port, cls, units, equations,
        latex=None, tokens=None, index_structures=None,
        network="macroscopic", value=None):
    iri = f"{LIB}#{frag}"
    return {
        "iri": iri,
        "label": label,
        "network": network,
        "domain_iri": f"{ONT}#domain_{network}",
        "type": None,
        "units": units,
        "index_structures": index_structures if index_structures is not None else [IDX_N],
        "internal_id": frag,
        "aliases": ({"latex": latex, "global_ID": iri}
                    if latex else {"global_ID": iri}),
        "doc": doc,
        "port_variable": port,
        "frozen": False,
        "tokens": [TOK_CHARGE] if tokens is None else tokens,
        "token_vector": None,
        "value": value,
        "equations": equations,
        "classifications": cls,
    }


NEW_VARS = [
    var("V_137", "z_el",
        "species valence — charge carried per mole of species s. "
        "Species data, value-cell bound on the S axis like nu.  "
        "The species↔charge coupling coefficient of U(S,V,n,qel) "
        "(§57): appears both in qel := z·F·n and in mu_el := "
        "mu + z·F·Ue.",
        port=False, cls=CLS_PARAM, units=U_NONE, latex="{z}_{s}^{el}",
        tokens=[], index_structures=[IDX_S],
        network="physical", equations={}),
    var("V_138", "const_F",
        "Faraday constant F — C per mol of charge; universal "
        "constant, bound here.  Bridges the charge and "
        "component_mass content families (§57).",
        port=False, cls=CLS_PARAM, units=U_MOL_CHG, latex="\\mathcal{F}",
        tokens=[], index_structures=[],
        network="physical", value="96485.33212",
        equations={}),
    var("V_139", "mu_el",
        "electrochemical potential — derived effort "
        "(mu + z·F·Ue), NOT a declared primitive: the "
        "species-coupled conjugate when qel = z·F·n is imposed "
        "on U(S,V,n,qel) (§57).  The driving effort for "
        "electrochemical species transport.",
        port=True, cls=CLS_EFFORT, units=U_J_MOL,
        latex="{\\tilde{\\mu}}",
        tokens=[TOK_CM, TOK_CHARGE],
        index_structures=[IDX_N, IDX_S],
        equations={
            "E_mu_el": eq("E_mu_el", V_MUEL,
                          "( physical!mu + ( physical!z_el * "
                          "physical!const_F * Ue ) )",
                          "electrochemical potential — chain rule "
                          "of the species-charge coupling (§57)"),
        }),
    var("V_140", "Pel",
        "electric power transfer on a charge contact — the "
        "work term Ue·fe entering the charged lump's energy "
        "balance; mandatory bookkeeping, not a diagnostic (§57).",
        port=True, cls=CLS_FLOW, units=U_WATT, latex="{P}^{el}",
        tokens=[TOK_ENERGY],
        index_structures=[IDX_AEL, IDX_N],
        equations={
            "E_Pel": eq("E_Pel", V_PEL,
                        "( Ue * fe )",
                        "electric transfer term — effort × flow on "
                        "the contact (§57)"),
        }),
]

# Reconstructed records carrying additional alternative equations.
MERGE_VARS = [
    var("V_130", "qel",
        "charge content of a capacitive lump — the conserved charge "
        "state; slot bound through the running Integral (§48).",
        port=False,
        cls={AX_DET: T_DET_VAR, AX_EXT: T_EXT_EXT,
             AX_FUN: f"{ONT}#term_function_state"},
        units=[1, 0, 0, 0, 0, 1, 0, 0], latex="{q}^{el}",
        equations={
            "E_qel_def": eq("E_qel_def", V_QEL,
                            "Integral( macroscopic!dqeldt :: t in "
                            "[ to, t ] )",
                            "content-of-state integral — qel slot "
                            "carries dqeldt (§48)"),
            "E_qel_species": eq("E_qel_species", V_QEL,
                                "reduceSum( ( physical!z_el * "
                                "physical!const_F * physical!n ), S )",
                                "charge content from species — "
                                "electroneutral bookkeeping "
                                "qel = z·F·n for charged lumps (§57)"),
        }),
    var("V_79", "fnd",
        "diffusive species flow on a diffusion contact "
        "(chemical-potential driven)",
        port=True, cls=CLS_FLOW, units=U_MOL_S, latex="{\\hat{n}^d}",
        tokens=[TOK_CM],
        index_structures=[IDX_ADIFF, IDX_N, IDX_S],
        equations={
            "E_41": eq("E_41", V_FND,
                       "( ( kDiffX * geometry!Ayz ) * reduceSum( "
                       "( physical!sigma * physical!mu ), X ) )",
                       "diffusive species flow — chemical-potential "
                       "driven (existing)"),
            "E_fnd_el": eq("E_fnd_el", V_FND,
                           "( ( kDiffX * geometry!Ayz ) * reduceSum( "
                           "( physical!sigma * mu_el ), X ) )",
                           "electrochemical diffusion — mu_el "
                           "driven; subsumes ionic conduction "
                           "(§57)"),
        }),
]


def main():
    failures = []
    st, ctx = req("GET", f"{EQ}/context?graph={urllib.parse.quote(LIB, safe='')}")
    if st != 200:
        print(f"FATAL context: {st} {str(ctx)[:200]}")
        sys.exit(1)
    existing = {v["iri"] for v in ctx["variables"]}
    g = urllib.parse.quote(LIB, safe="")

    for rec in NEW_VARS + MERGE_VARS:
        iri = rec["iri"]
        put = iri in existing
        st, out = req("PUT" if put else "POST",
                      (f"{EQ}/variables/{urllib.parse.quote(iri, safe='')}?graph={g}"
                       if put else f"{EQ}/variables?graph={g}"),
                      rec)
        tag = "PUT" if put else "POST"
        if st not in (200, 201):
            failures.append((rec["label"], f"{tag} {st}: {str(out)[:400]}"))
        else:
            print(f"{rec['iri'].split('#')[-1]} {rec['label']}: {tag} {st}")

    # Refresh pass — same incidence-derivation safeguard as stage 1.
    for rec in NEW_VARS + MERGE_VARS:
        if not rec["equations"]:
            continue
        iri = rec["iri"]
        st, out = req("PUT", f"{EQ}/variables/{urllib.parse.quote(iri, safe='')}?graph={g}", rec)
        if st != 200:
            failures.append((f"{rec['label']} refresh", f"PUT {st}: {str(out)[:300]}"))
        else:
            print(f"{rec['iri'].split('#')[-1]} refresh: PUT {st}")

    for name, msg in failures:
        print(f"FAIL {name}: {msg}", file=sys.stderr)
    if failures:
        sys.exit(1)
    print("charge stage-2 (electrochemistry var/expr) authored")


if __name__ == "__main__":
    main()
