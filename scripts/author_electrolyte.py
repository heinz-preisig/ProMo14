#!/usr/bin/env python3
"""Author the electrolyte lump + electrochemical diffusion leg
(§57 — consumers for ``E_qel_species`` and ``E_fnd_el``).

The electrolyte is the charge+species sibling of ``etype_lumped``
(alongside ``etype_lumped_conductor``/``etype_lumped_qss``): it
holds species content ``n[N,S]`` and carries charge by
electroneutral bookkeeping — ``qel := z_el*F*n`` (the
``E_qel_species`` alternative, no independent charge state).  It
exports ``mu_el``/``Ue`` for ionic legs.

  ``etype_lumped_electrolyte``  sibling of ``etype_lumped``;
    state = ``dndt`` (species rate, E_50 = anc+and+r), derived
    chain n → qel → Ue → mu_el; ``dqeldt`` sequenced as a KCL
    reading (electroneutral bulk = no charge state); mu/r/no
    instantiated as EOS/reaction/IC data.

  ``etype_diffusion_transport``  base assignment (was missing —
    the seeded mechanism leaf had none): ``E_41`` chemical-
    potential law, port ``mu``, output ``fnd``.

  ``etype_diffusion_ionic``     sibling of the above (§47 regime-
    per-sibling): ``E_fnd_el`` electrochemical law, port
    ``mu_el``, output ``fnd``.  The ``E_fnd_el`` consumer.

Idempotent — safe to re-run.
"""
import json
import sys
import urllib.parse
import urllib.request

HOST = "http://localhost:8000"
API = f"{HOST}/api"
LIB = "https://w3id.org/promo/library"
ONT = "https://w3id.org/promo/ontology"
ASG = "https://w3id.org/promo/library/assignments"

# etype bits
TT_DYN = "dynamic"
TT_EVT = "event-dynamic"
ST_UNI = "uniform"
ST_DIST = "distributed"
SS_FIN = "finite"
SVAL_LUM = f"{ONT}#sval_length_macroscopic_uniform"
SVAL_TDYN = f"{ONT}#sval_time_macro_dynamic"
SVAL_LDIS = f"{ONT}#sval_length_microscopic_distributed"
SVAL_TEVT = f"{ONT}#sval_time_macro_event_dynamic"

# vars
V_T = f"{ONT}#V_11"
V_N = f"{ONT}#V_6"          # n — physical
V_DNDT = f"{LIB}#V_94"
V_QEL = f"{LIB}#V_130"
V_UE = f"{LIB}#V_133"
V_CEL = f"{LIB}#V_134"
V_MU = f"{LIB}#V_35"
V_MUEL = f"{LIB}#V_139"
V_R = f"{LIB}#V_93"          # reaction rate (reactions net)
V_NO = f"{LIB}#V_95"         # initial moles
V_FND = f"{LIB}#V_79"
V_FNC = f"{LIB}#V_77"
V_FE = f"{LIB}#V_132"
V_KDIFFX = f"{LIB}#V_42"
V_AYZ = f"{LIB}#V_54"
V_DQELDT = f"{LIB}#V_131"
F_DIFF = f"{ONT}#F_diff"

# equations
E_50 = f"{LIB}#E_50"          # dndt := anc+and+r
E_51 = f"{LIB}#E_51"          # n := Integral(dndt)+no
E_40 = f"{LIB}#E_40"          # anc gather
E_42 = f"{LIB}#E_42"          # and gather
E_41 = f"{LIB}#E_41"          # fnd := kDiffX*Ayz*Σσ·mu
E_FND_EL = f"{LIB}#E_fnd_el"  # fnd := kDiffX*Ayz*Σσ·mu_el
E_QEL_SP = f"{LIB}#E_qel_species"
E_UE_CAP = f"{LIB}#E_Ue_cap"
E_MU_EL = f"{LIB}#E_mu_el"
E_DQELDT = f"{LIB}#E_dqeldt"

ET_ELYTE = f"{ONT}#etype_lumped_electrolyte"
ET_DIFF = f"{ONT}#etype_diffusion_transport"
ET_DIFF_ION = f"{ONT}#etype_diffusion_ionic"


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


def put_assignment(ga, rec):
    st, out = req("PUT", f"{API}/behaviour/assignment?graph={ga}", rec)
    if st != 200:
        print(f"FAIL assignment {rec['entity_type'].split('#')[-1]}: "
              f"{st} {str(out)[:400]}", file=sys.stderr)
        sys.exit(1)
    print(f"assignment {rec['entity_type'].split('#')[-1]}: "
          f"closed={out.get('closed')} "
          f"seq={[s.rsplit('#', 1)[-1] for s in out.get('sequence', [])]}")
    return out


def main():
    go = urllib.parse.quote(ONT, safe="")
    ga = urllib.parse.quote(ASG, safe="")

    # --- entity types -------------------------------------------------
    st, ets = req("GET", f"{API}/ontology/entity-types")
    existing = {e["iri"] for e in ets} if st == 200 else set()

    electrolyte = {
        "iri": ET_ELYTE,
        "label": "Lumped Electrolyte",
        "temporal_type": TT_DYN,
        "spatial_type": ST_UNI,
        "spatial_size": SS_FIN,
        "branch": "physical",
        "scale_values": [SVAL_LUM, SVAL_TDYN],
        "description": (
            "Lumped electrolyte — species carrier holding n[N,S] "
            "with charge carried by electroneutral bookkeeping "
            "(qel := z*F*n, the E_qel_species alternative); exports "
            "mu_el/Ue driving ionic legs.  §57 consumer; sibling of "
            "etype_lumped alongside the conductor and qss lumps."
        ),
        "parent": f"{ONT}#etype_lumped",
        "capabilities": ["reaction_host"],
        "token": None,
        "drives": [],
    }
    ionic_diff = {
        "iri": ET_DIFF_ION,
        "label": "Ionic Diffusion",
        "temporal_type": TT_EVT,
        "spatial_type": ST_DIST,
        "spatial_size": SS_FIN,
        "branch": "physical",
        "scale_values": [SVAL_LDIS, SVAL_TEVT],
        "description": (
            "Electrochemical diffusion — species legs driven by the "
            "electrochemical potential mu_el (E_fnd_el); sibling of "
            "diffusion transport for charged-species media such as "
            "electrolytes (§57).  Pairing with the electrolyte "
            "lump's mu_el export is the §32 interface."
        ),
        "parent": ET_DIFF,
        "capabilities": ["species_transport", "component_alignment"],
        "token": None,
        "drives": [],
    }
    for et in (electrolyte, ionic_diff):
        put = et["iri"] in existing
        st, out = req(
            "PUT" if put else "POST",
            (f"{API}/ontology/entity-types/{urllib.parse.quote(et['iri'], safe='')}?graph={go}"
             if put else f"{API}/ontology/entity-types?graph={go}"),
            et)
        if st not in (200, 201):
            print(f"FAIL etype {et['iri'].split('#')[-1]}: "
                  f"{st} {str(out)[:400]}", file=sys.stderr)
            sys.exit(1)
        print(f"etype {et['iri'].split('#')[-1]}: "
              f"{'PUT' if put else 'POST'} {st}")

    # --- assignments --------------------------------------------------
    # Electrolyte lump — E_qel_species consumer: qel derives from n
    # (electroneutral), so the species balance is the only state.
    put_assignment(ga, {
        "entity_type": ET_ELYTE,
        "sequence": [E_51, E_QEL_SP, E_UE_CAP, E_MU_EL,
                     E_40, E_42, E_50, E_DQELDT],
        "base_equation": E_50,
        "state_variables": [V_DNDT],
        "instantiated": [V_T, V_CEL, V_MU, V_R, V_NO],
        "ports": [V_FND, V_FNC, V_FE],
        "outputs": [V_MUEL, V_UE, V_DQELDT],
    })

    # Base diffusion transport — the plain mu-driven law (E_41).
    # Stateless event-dynamic form: base=null (§32 — the stateless
    # shape; an anchored peer balance would pull lump-side refs
    # into this cone).
    put_assignment(ga, {
        "entity_type": ET_DIFF,
        "sequence": [E_41],
        "base_equation": None,
        "state_variables": [],
        "instantiated": [V_KDIFFX, V_AYZ, F_DIFF],
        "ports": [V_MU],
        "outputs": [V_FND],
    })

    # Ionic diffusion sibling — E_fnd_el consumer: mu_el-driven.
    put_assignment(ga, {
        "entity_type": ET_DIFF_ION,
        "sequence": [E_FND_EL],
        "base_equation": None,
        "state_variables": [],
        "instantiated": [V_KDIFFX, V_AYZ, F_DIFF],
        "ports": [V_MUEL],
        "outputs": [V_FND],
    })

    print("electrolyte lump + diffusion legs (E_41/E_fnd_el) authored")


if __name__ == "__main__":
    main()
