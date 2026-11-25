#!/usr/bin/env python3
"""§56 charge stage 1 — capacitive conductor + electrical conduction.

Ruling (2026-11-25): resistance + charge balance first (the old-ProMo
starting point), electrochemistry staged.  The seed machinery already
carries the transport side (``etype_charge_transport`` /
``etype_conduction_transport``, ``idx_arc_charge``/``A_el``, derived
``F_el``); this script authors the rest through the live API:

- POST /api/ontology/entity-types — ``etype_lumped_conductor``,
  sibling of ``etype_lumped``: the capacitive lump that stores charge
  (``qel`` a real state, ``Ue := inv(Cel)·qel``).
- POST/PUT /api/equation/variables — the charge family on the
  library graph: ``qel``/``dqeldt`` (content + rate, [N]),
  ``fe`` (arc-bound current, [A_el,N], port), ``Ue`` (voltage
  effort, [N], port), ``Cel``/``kEl``/``Rel`` (neutral params).
  Equations: ``E_dqeldt`` (KCL falls out), ``E_qel_def`` (§48
  integral), ``E_fe_ohm`` + ``E_fe_res`` (§54-style alternatives on
  one lhs), ``E_Ue_cap``.
- PUT /api/behaviour/assignment — closed assignments for both new
  entity types, mirroring the convection/lumped shapes.

Idempotent: PUT semantics throughout.
"""
import json
import sys
import urllib.parse
import urllib.request

API = "http://localhost:8000/api"
EQ = f"{API}/equation"
ONT = "https://w3id.org/promo/ontology"
LIB = "https://w3id.org/promo/library"
ASG = "https://w3id.org/promo/library/assignments"

IDX_N = f"{ONT}#idx_node"
IDX_AEL = f"{ONT}#idx_arc_charge"
IDX_X = f"{ONT}#idx_x"
TOK_CHARGE = f"{ONT}#token_charge"
AX_DET = f"{ONT}#axis_determination_physical"
AX_EXT = f"{ONT}#axis_extensity"
AX_FUN = f"{ONT}#axis_function_physical"
AX_ROLE = f"{ONT}#axis_role_information"
T_DET_VAR = f"{ONT}#term_determination_variable"
T_DET_CONST = f"{ONT}#term_determination_constant"
T_EXT_EXT = f"{ONT}#term_extensity_extensive"
T_FUN_STATE = f"{ONT}#term_function_state"
T_FUN_FLOW = f"{ONT}#term_function_flow"
T_FUN_EFFORT = f"{ONT}#term_function_effort"
T_FUN_COEF = f"{ONT}#term_function_coefficient"
T_ROLE_PAR = f"{ONT}#term_info_role_parameter"
EQ_GENERIC = f"{ONT}#eqclass_generic"
F_EL = f"{ONT}#F_el"
V_T = f"{ONT}#V_11"          # time — instantiated for the Integral

# units: (time, length, amount, mass, temperature, current, light, nil)
U_CHARGE = [1, 0, 0, 0, 0, 1, 0, 0]      # C  = A·s
U_CURRENT = [0, 0, 0, 0, 0, 1, 0, 0]     # A
U_VOLT = [-3, 2, 0, 1, 0, -1, 0, 0]      # V  = kg·m²·s⁻³·A⁻¹
U_FARAD = [4, -2, 0, -1, 0, 2, 0, 0]     # F  = A²·s⁴·kg⁻¹·m⁻²
U_SIEMENS = [3, -2, 0, -1, 0, 2, 0, 0]   # S  = A/V
U_OHM = [-3, 2, 0, 1, 0, -2, 0, 0]       # Ω  = V/A

CLS_STATE = {AX_DET: T_DET_VAR, AX_EXT: T_EXT_EXT, AX_FUN: T_FUN_STATE}
CLS_FLOW = {AX_DET: T_DET_VAR, AX_EXT: T_EXT_EXT, AX_FUN: T_FUN_FLOW}
CLS_EFFORT = {AX_DET: T_DET_VAR, AX_FUN: T_FUN_EFFORT}
CLS_PARAM = {AX_DET: T_DET_CONST, AX_FUN: T_FUN_COEF, AX_ROLE: T_ROLE_PAR}


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


def eq(frag, lhs_iri, rhs, doc=""):
    return {
        "iri": f"{LIB}#{frag}",
        "internal_id": frag,
        "lhs": lhs_iri,
        "rhs": rhs,
        "equation_class": EQ_GENERIC,
        "network": "macroscopic",
        "doc": doc,
    }


def var(frag, label, doc, *, port, cls, units, equations,
        latex=None, tokens=None, index_structures=None):
    iri = f"{LIB}#{frag}"
    return {
        "iri": iri,
        "label": label,
        "network": "macroscopic",
        "domain_iri": f"{ONT}#domain_macroscopic",
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
        "token_vector": None,        # write path derives the signature
        "value": None,
        "equations": equations,
        "classifications": cls,
    }


V_QEL = f"{LIB}#V_130"
V_DQELDT = f"{LIB}#V_131"
V_FE = f"{LIB}#V_132"
V_UE = f"{LIB}#V_133"
V_CEL = f"{LIB}#V_134"
V_KEL = f"{LIB}#V_135"
V_REL = f"{LIB}#V_136"

NEW_VARS = [
    var("V_130", "qel",
        "charge content of a capacitive lump — the conserved charge "
        "state; slot bound through the running Integral (§48).",
        port=False, cls=CLS_STATE, units=U_CHARGE, latex="{q}^{el}",
        equations={
            "E_qel_def": eq("E_qel_def", V_QEL,
                            "Integral( macroscopic!dqeldt :: t in "
                            "[ to, t ] )",
                            "content-of-state integral — qel slot "
                            "carries dqeldt (§48)"),
        }),
    var("V_131", "dqeldt",
        "charge balance rate — net current over charge-arc contacts; "
        "KCL falls out of this balance, it is not a separate law.",
        port=False, cls=CLS_STATE, units=U_CURRENT, latex="\\dot{q}^{el}",
        equations={
            "E_dqeldt": eq("E_dqeldt", V_DQELDT,
                           "reduceSum( ( physical!F_el * fe ), A_el )",
                           "charge balance of the conductor lump"),
        }),
    var("V_132", "fe",
        "electric current on a conduction contact — arc-bound charge "
        "flow (the structural upgrade over old-ProMo Ie, which was "
        "node-internal dC/dt).  Port export gathered [A_el,N] by the "
        "peer lump; driven by the voltage through-drop.",
        port=True, cls=CLS_FLOW, units=U_CURRENT, latex="{I}^{e}",
        index_structures=[IDX_AEL, IDX_N],
        equations={
            "E_fe_ohm": eq("E_fe_ohm", V_FE,
                           "( kEl * reduceSum( ( physical!sigma * Ue ), "
                           "X ) )",
                           "Ohmic constitutive — conductance × "
                           "through-drop of voltage"),
            "E_fe_res": eq("E_fe_res", V_FE,
                           "( inv( Rel ) * reduceSum( ( physical!sigma "
                           "* Ue ), X ) )",
                           "resistance parameterisation — §54-style "
                           "alternative on the same lhs"),
        }),
    var("V_133", "Ue",
        "voltage — effort conjugate to charge (energy per charge).  "
        "On the conductor lump: state-driven via the capacitance law; "
        "exported at contacts for the transport's σ gather.",
        port=True, cls=CLS_EFFORT, units=U_VOLT, latex="{U}^{e}",
        equations={
            "E_Ue_cap": eq("E_Ue_cap", V_UE,
                           "( inv( Cel ) * macroscopic!qel )",
                           "capacitance effort — Ue = qel/Cel"),
        }),
    var("V_134", "Cel",
        "capacitance — lumped charge-storage parameter [N]; the pure "
        "KCL resistor is Cel→small, never exactly zero (§56).",
        port=False, cls=CLS_PARAM, units=U_FARAD, latex="{C}^{el}",
        tokens=[], equations={}),
    var("V_135", "kEl",
        "electrical conductance of a conduction leg — lumped "
        "coefficient [A_el]; geometry folded in for stage 1.",
        port=False, cls=CLS_PARAM, units=U_SIEMENS, latex="{k}^{el}",
        tokens=[], index_structures=[IDX_AEL], equations={}),
    var("V_136", "Rel",
        "electrical resistance of a conduction leg — alternative "
        "parameterisation for E_fe_res (inv(Rel) × through-drop).",
        port=False, cls=CLS_PARAM, units=U_OHM, latex="{R}^{el}",
        tokens=[], index_structures=[IDX_AEL], equations={}),
]


def main():
    failures = []

    # -- 0. sibling lump entity type ------------------------------------
    etype = {
        "iri": f"{ONT}#etype_lumped_conductor",
        "label": "Lumped Conductor",
        "temporal_type": "dynamic",
        "spatial_type": "uniform",
        "spatial_size": "finite",
        "branch": "physical",
        "scale_values": [
            f"{ONT}#sval_length_macroscopic_uniform",
            f"{ONT}#sval_time_macro_dynamic",
        ],
        "description": (
            "Capacitive lumped conductor — stores charge (qel a real "
            "state, Ue = qel/Cel) and exchanges current over charge-arc "
            "contacts.  §56 stage 1; the pure-KCL resistive lump stays "
            "deferred to the algebraic-loop machinery."),
        "parent": f"{ONT}#etype_lumped",
        "capabilities": [],
        "token": None,
        "drives": [],
    }
    st, out = req("POST",
                  f"{API}/ontology/entity-types"
                  f"?graph={urllib.parse.quote(ONT, safe='')}",
                  etype)
    if st != 200:
        failures.append(("entity-type", f"{st}: {str(out)[:400]}"))
    else:
        print(f"etype_lumped_conductor: POST {st}")

    # -- 1. variables + equations (library graph) ------------------------
    st, ctx = req("GET", f"{EQ}/context?graph={urllib.parse.quote(LIB, safe='')}")
    if st != 200:
        print(f"FATAL context: {st} {str(out)[:200]}")
        sys.exit(1)
    existing = {v["iri"] for v in ctx["variables"]}
    g = urllib.parse.quote(LIB, safe="")
    for rec in NEW_VARS:
        iri = rec["iri"]
        if iri in existing:
            st, out = req("PUT", f"{EQ}/variables/{urllib.parse.quote(iri, safe='')}?graph={g}", rec)
        else:
            st, out = req("POST", f"{EQ}/variables?graph={g}", rec)
        tag = "PUT" if iri in existing else "POST"
        if st not in (200, 201):
            failures.append((rec["label"], f"{tag} {st}: {str(out)[:400]}"))
        else:
            print(f"{rec['iri'].split('#')[-1]} {rec['label']}: {tag} {st}")

    # Refresh pass — the charge equations reference each other's vars
    # (qel→dqeldt→fe→Ue→qel cycles), so a first-pass POST necessarily
    # fails the rhs check for forward references and stores no
    # incidenceList.  Once every var exists a re-PUT lets
    # _canonicalise_equations derive incidence/rhsExpression cleanly.
    # Harmless when the first pass already succeeded.
    for rec in NEW_VARS:
        if not rec["equations"]:
            continue
        iri = rec["iri"]
        st, out = req("PUT", f"{EQ}/variables/{urllib.parse.quote(iri, safe='')}?graph={g}", rec)
        if st != 200:
            failures.append((f"{rec['label']} refresh", f"PUT {st}: {str(out)[:300]}"))
        else:
            print(f"{rec['iri'].split('#')[-1]} refresh: PUT {st}")

    # -- 2. assignments ---------------------------------------------------
    ga = urllib.parse.quote(ASG, safe="")
    conduction = {
        "entity_type": f"{ONT}#etype_conduction_transport",
        "sequence": [f"{LIB}#E_fe_ohm", f"{LIB}#E_dqeldt"],
        "base_equation": f"{LIB}#E_dqeldt",
        "state_variables": [],
        # peer's rate replayed as datum (the E_29/V_57 pattern on
        # convection), plus the leg parameters and the incidence factor
        "instantiated": [V_DQELDT, V_KEL, V_REL, F_EL],
        "ports": [V_UE],                # voltage gathered via σ·Ue
        "outputs": [V_FE],              # current export
    }
    st, out = req("PUT", f"{API}/behaviour/assignment?graph={ga}", conduction)
    if st != 200:
        failures.append(("conduction assignment", f"{st}: {str(out)[:400]}"))
    else:
        print(f"assignment conduction: closed={out.get('closed')} "
              f"seq={[s.rsplit('#', 1)[-1] for s in out.get('sequence', [])]}")

    conductor = {
        "entity_type": f"{ONT}#etype_lumped_conductor",
        "sequence": [f"{LIB}#E_qel_def", f"{LIB}#E_Ue_cap",
                     f"{LIB}#E_dqeldt"],
        "base_equation": f"{LIB}#E_dqeldt",
        "state_variables": [V_DQELDT],
        "instantiated": [V_T, V_CEL],
        "ports": [V_FE],                # current arrives through contacts
        "outputs": [V_UE],              # voltage exported to the arc
    }
    st, out = req("PUT", f"{API}/behaviour/assignment?graph={ga}", conductor)
    if st != 200:
        failures.append(("conductor assignment", f"{st}: {str(out)[:400]}"))
    else:
        print(f"assignment conductor: closed={out.get('closed')} "
              f"seq={[s.rsplit('#', 1)[-1] for s in out.get('sequence', [])]}")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" ", f)
        sys.exit(1)
    print("\ncharge stage-1 authored")


if __name__ == "__main__":
    main()
