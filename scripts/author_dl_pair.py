#!/usr/bin/env python3
"""Author the electrode double-layer pair (§57 — ruled 2026-11-26:
two phase-boundary nodes, continuity *by identity*).

The interface decomposes into a ``DL-metal`` and a ``DL-elyte``
volume — both children of ``etype_distributed`` (dynamic +
distributed + reaction_host, all seeded).  The two token-flow
networks (charge / species) each terminate on their DL node; the
pair is knit by *access arcs* (carrier=reference).  Continuity is
algebraic: ``phi`` (surface potential, metal→elyte) and ``i``
(Faradaic current, elyte→metal) are single library variables —
computed on one node, bound by identity on the peer.  No
``i_e = i_ion`` consistency equation exists; the shared var *is*
the condition.

Token design (load-bearing):
  ``phi``/``i`` carry ONLY ``token_signal`` — a conserved-token
  claim would let their ports see token-comparable candidates on
  the flow arcs (peer ``Ue``) and bind the wrong contact.
  ``token_vector={}`` keeps them algebraically neutral (§35
  licensed-member rule), so ``fe - i`` and ``phi - Ue`` still
  signature-check.  ``i`` is ``function:reaction`` — NOT flow:
  §44 would treat a missing access arc as "absent" rather than
  reporting ``unbound``; the missing-wiring problem must surface.

  ``etype_dl_metal``  state ``dqeldt`` (E_dqel_dl = fe − i, the
    electronic balance with Faradaic sink); ``qel := Integral``,
    ``phi := qel/Cel`` (compact capacitance).  Ports fe + i;
    exports phi.
  ``etype_dl_elyte``  state ``dndt`` (E_50 species balance incl.
    the reaction term); chain n→qel→Ue→mu_el (E_92/E_84/E_90),
    then ``eta := phi − Ue``, USER-RULED ``r := k_ct*eta``
    (E_r_ct), ``i := z·F·r`` (E_iF); E_dqel_ion is the ionic-side
    charge-rate reading (dqeldt alternative).  Ports fnd/fnc/phi;
    exports i/mu_el/Ue/dqeldt; k_ct instanced.

Rate law is the user-ruled linearised charge-transfer form
(``r := k_ct*eta``, 2026-11-26); B–V is the recorded alternative
for later.

Idempotent — safe to re-run.
"""
import json
import sys
import urllib.parse
import urllib.request

HOST = "http://localhost:8000"
API = f"{HOST}/api"
EQ = f"{API}/equation"
LIB = "https://w3id.org/promo/library"
ONT = "https://w3id.org/promo/ontology"
ASG = "https://w3id.org/promo/library/assignments"

# --- etype bits -------------------------------------------------------
TT_DYN = "dynamic"
ST_DIST = "distributed"
SS_FIN = "finite"
SVAL_TDYN = f"{ONT}#sval_time_macro_dynamic"
SVAL_LDIST = f"{ONT}#sval_length_macroscopic_distributed"
ET_DIST = f"{ONT}#etype_distributed"
ET_METAL = f"{ONT}#etype_dl_metal"
ET_ELYTE = f"{ONT}#etype_dl_elyte"

# --- existing vars ----------------------------------------------------
V_T = f"{ONT}#V_11"          # t        [] universe
V_N = f"{ONT}#V_6"           # n        [N,S] physical
V_MU = f"{LIB}#V_35"         # mu       [N,S] physical
V_FNC = f"{LIB}#V_77"        # fnc      [A_conv,N,S]
V_FND = f"{LIB}#V_79"        # fnd      [A_diff,N,S]
V_R = f"{LIB}#V_93"          # r        [N,S] reactions
V_DNDT = f"{LIB}#V_94"       # dndt     [N,S] reactions
V_NO = f"{LIB}#V_95"         # no       [N,S] macroscopic
V_QEL = f"{LIB}#V_130"       # qel      [N]
V_DQELDT = f"{LIB}#V_131"    # dqeldt   [N]
V_FE = f"{LIB}#V_132"        # fe       [A_el,N]
V_UE = f"{LIB}#V_133"        # Ue       [N]
V_CEL = f"{LIB}#V_134"       # Cel      [N]
V_MUEL = f"{LIB}#V_139"      # mu_el    [N,S]

# --- new vars ---------------------------------------------------------
V_PHI = f"{LIB}#V_146"       # phi      [N] surface potential
V_ETA = f"{LIB}#V_147"       # eta      [N] overpotential
V_I = f"{LIB}#V_148"         # i        [N] Faradaic current
V_KCT = f"{LIB}#V_149"       # k_ct     [S] charge-transfer coeff.

# --- tokens / classes / indices ---------------------------------------
TOK_CHG = f"{ONT}#token_charge"
TOK_SIG = f"{ONT}#token_signal"
IDX_N = f"{ONT}#idx_node"
IDX_S = f"{ONT}#idx_species"
AX_DET = f"{ONT}#axis_determination_physical"
AX_EXT = f"{ONT}#axis_extensity"
AX_FUN = f"{ONT}#axis_function_physical"
AX_ROLE = f"{ONT}#axis_role_information"
T_DET_VAR = f"{ONT}#term_determination_variable"
T_DET_CONST = f"{ONT}#term_determination_constant"
T_EXT_INT = f"{ONT}#term_extensity_intensive"
T_EXT_EXT = f"{ONT}#term_extensity_extensive"
T_FUN_EFFORT = f"{ONT}#term_function_effort"
T_FUN_REACTION = f"{ONT}#term_function_reaction"
T_FUN_COEFF = f"{ONT}#term_function_coefficient"
T_ROLE_PAR = f"{ONT}#term_info_role_parameter"
T_ROLE_OUT = f"{ONT}#term_info_role_output"
EQ_GENERIC = f"{ONT}#eqclass_generic"

# units: (time, length, amount, mass, temperature, current, light, nil)
U_VOLT = [-3, 2, 0, 1, 0, -1, 0, 0]          # Ue
U_AMP = [0, 0, 0, 0, 0, 1, 0, 0]             # dqeldt = A
U_KCT = [2, -2, 1, -1, 0, 1, 0, 0]           # r/eta

CLS_EFFORT = {AX_DET: T_DET_VAR, AX_FUN: T_FUN_EFFORT}
CLS_RXNOUT = {AX_DET: T_DET_VAR, AX_EXT: T_EXT_EXT,
              AX_FUN: T_FUN_REACTION, AX_ROLE: T_ROLE_OUT}
CLS_PARAM = {AX_DET: T_DET_CONST, AX_FUN: T_FUN_COEFF,
             AX_ROLE: T_ROLE_PAR}


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
        latex=None, tokens=None, token_vector=None,
        index_structures=None, network="macroscopic", value=None):
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
        "tokens": tokens or [],
        "token_vector": token_vector,
        "value": value,
        "equations": equations,
        "classifications": cls,
    }


NEW_VARS = [
    var("V_146", "phi",
        "Surface potential of the interface — the double-layer "
        "voltage drop authored DL-metal-side (phi := qel/Cel); read "
        "by the electrolyte half as the metal-side potential in the "
        "overpotential (continuity by identity, §57).  Signal-token "
        "only: rides access arcs, invisible to flow-arc matching.",
        port=True, cls=CLS_EFFORT, units=U_VOLT,
        tokens=[TOK_SIG], token_vector={},
        latex="{\\phi}",
        equations={
            "E_phi": eq("E_phi", V_PHI,
                        "( inv( Cel ) * qel )",
                        "compact-layer surface potential — "
                        "phi = qel/Cel (§57)"),
        }),
    var("V_147", "eta",
        "Overpotential — interfacial driving force "
        "eta := phi − Ue (metal surface potential minus the "
        "electrolyte-side diffuse-layer potential, §57).",
        port=False, cls=CLS_EFFORT, units=U_VOLT,
        tokens=[TOK_CHG],
        latex="{\\eta}",
        equations={
            "E_eta": eq("E_eta", V_ETA,
                        "( phi - Ue )",
                        "overpotential = surface − diffuse "
                        "potential (§57)"),
        }),
    var("V_148", "i",
        "Faradaic current — the charge-transfer current across the "
        "interface; computed DL-elyte-side (i := z·F·r) and "
        "consumed DL-metal-side as the balance sink (continuity by "
        "identity, §57).  Signal-token only — rides access arcs.  "
        "function:reaction (not flow): a missing access arc must "
        "report unbound, not §44-absent.",
        port=True, cls=CLS_RXNOUT, units=U_AMP,
        tokens=[TOK_SIG], token_vector={},
        latex="{i}",
        equations={
            "E_iF": eq("E_iF", V_I,
                       "reduceSum( ( ( physical!z_el * "
                       "physical!const_F ) * reactions!r ), S )",
                       "Faradaic current = z·F·r summed over "
                       "species (§57)"),
        }),
    var("V_149", "k_ct",
        "Charge-transfer coefficient — per-species linearised "
        "rate coefficient for the user-ruled law r := k_ct*eta "
        "(§57, 2026-11-26); absorbs stoichiometry + rate constant "
        "per species.",
        port=False, cls=CLS_PARAM, units=U_KCT, tokens=[],
        index_structures=[IDX_S], network="physical",
        latex="{k}^{ct}", equations={}),
]

# Alternative equations appended to existing vars (PUT = full
# replacement — merge against the live record, dedupe by iri).
MERGE_EQS = {
    V_DQELDT: [
        eq("E_dqel_dl", V_DQELDT,
           "( reduceSum( ( physical!F_el * fe ), A_el ) - i )",
           "DL-metal charge balance — electronic inflow minus "
           "Faradaic current (§57)"),
        eq("E_dqel_ion", V_DQELDT,
           "reduceSum( ( ( physical!z_el * physical!const_F ) * "
           "reactions!dndt ), S )",
           "ionic-side charge-rate reading — z·F·(species rate); "
           "the diffuse layer's KCL mirror (§57)"),
    ],
    V_R: [
        eq("E_r_ct", V_R,
           "( physical!k_ct * macroscopic!eta )",
           "linearised charge-transfer rate — user-ruled "
           "r := k_ct*eta (§57, 2026-11-26)",
           network="reactions"),
    ],
}


def put_var(rec, existing):
    iri = rec["iri"]
    g = urllib.parse.quote(LIB, safe="")
    if iri in existing:
        st, out = req("PUT",
                      f"{EQ}/variables/{urllib.parse.quote(iri, safe='')}?"
                      f"graph={g}", rec)
        tag = "PUT"
    else:
        st, out = req("POST", f"{EQ}/variables?graph={g}", rec)
        tag = "POST"
    if st not in (200, 201):
        print(f"FAIL {tag} {rec['label']}: {st} {str(out)[:400]}",
              file=sys.stderr)
        sys.exit(1)
    print(f"{rec['iri'].split('#')[-1]} {rec['label']}: {tag} {st}")


def merge_eqs(var_iri, new_eqs, live):
    """Append equations to an existing var, dedupe by iri."""
    rec = dict(live[var_iri])
    have = {e.get("iri") for e in rec.get("equations", {}).values()}
    added = []
    for e in new_eqs:
        if e["iri"] in have:
            continue
        rec.setdefault("equations", {})[e["internal_id"]] = e
        added.append(e["iri"].split("#")[-1])
    return rec, added


def eq_iri(live, internal_id, fallback_frag=None):
    """Resolve an equation's live iri by internal_id (server mints
    numeric ids; the authored iri is the durable handle)."""
    for rec in live.values():
        for e in (rec.get("equations") or {}).values():
            if e.get("internal_id") == internal_id or \
                    e.get("iri", "").endswith(f"#{internal_id}"):
                return e["iri"]
    if fallback_frag:
        return f"{LIB}#{fallback_frag}"
    raise KeyError(internal_id)


def put_assignment(rec):
    ga = urllib.parse.quote(ASG, safe="")
    st, out = req("PUT", f"{API}/behaviour/assignment?graph={ga}", rec)
    if st != 200:
        print(f"FAIL assignment {rec['entity_type'].split('#')[-1]}: "
              f"{st} {str(out)[:400]}", file=sys.stderr)
        sys.exit(1)
    print(f"assignment {rec['entity_type'].split('#')[-1]}: "
          f"closed={out.get('closed')} "
          f"problems={len(out.get('problems') or [])}")
    for p in (out.get("problems") or []):
        print(f"   problem: {p}")
    return out


def main():
    go = urllib.parse.quote(ONT, safe="")
    ga = urllib.parse.quote(ASG, safe="")

    # --- live context --------------------------------------------------
    st, ctx = req("GET", f"{EQ}/context?graph={urllib.parse.quote(LIB, safe='')}")
    if st != 200:
        print(f"FAIL context: {st}", file=sys.stderr)
        sys.exit(1)
    live = {v["iri"]: v for v in ctx.get("variables", [])}
    existing = set(live)

    # --- new vars -------------------------------------------------------
    for rec in NEW_VARS:
        put_var(rec, existing)

    # --- merge alternative equations ------------------------------------
    for viri, new_eqs in MERGE_EQS.items():
        if viri not in live:
            print(f"FAIL merge target missing: {viri}", file=sys.stderr)
            sys.exit(1)
        rec, added = merge_eqs(viri, new_eqs, live)
        if not added:
            print(f"{viri.split('#')[-1]}: alternatives present")
        st, out = req(
            "PUT",
            f"{EQ}/variables/{urllib.parse.quote(viri, safe='')}?graph="
            f"{urllib.parse.quote(LIB, safe='')}", rec)
        if st != 200:
            print(f"FAIL merge {viri}: {st} {str(out)[:400]}",
                  file=sys.stderr)
            sys.exit(1)
        print(f"{viri.split('#')[-1]}: +{added or 'refresh'}")

    # --- incidence refresh pass -------------------------------------------
    # Re-PUT equation-bearing records so incidence lists derive after
    # all referenced vars exist.
    st, ctx = req("GET", f"{EQ}/context?graph={urllib.parse.quote(LIB, safe='')}")
    live = {v["iri"]: v for v in ctx.get("variables", [])}
    for rec in NEW_VARS + [live[V_DQELDT], live[V_R]]:
        viri = rec["iri"]
        st, out = req(
            "PUT",
            f"{EQ}/variables/{urllib.parse.quote(viri, safe='')}?graph="
            f"{urllib.parse.quote(LIB, safe='')}", rec)
        if st != 200:
            print(f"FAIL refresh {viri}: {st} {str(out)[:300]}",
                  file=sys.stderr)
            sys.exit(1)
    print("incidence refresh done")

    # --- entity types ----------------------------------------------------
    st, ets = req("GET", f"{API}/ontology/entity-types")
    et_existing = {e["iri"] for e in ets} if st == 200 else set()

    dl_metal = {
        "iri": ET_METAL,
        "label": "DL Metal",
        "temporal_type": TT_DYN,
        "spatial_type": ST_DIST,
        "spatial_size": SS_FIN,
        "branch": "physical",
        "scale_values": [SVAL_TDYN, SVAL_LDIST],
        "description": (
            "Double-layer metal half — the compact-layer surface "
            "volume at the phase boundary; child of "
            "etype_distributed (first dynamic+distributed in the "
            "suite).  Holds interfacial electronic charge qel; "
            "balance dqeldt := F·fe − i (Faradaic sink); exports "
            "the surface potential phi := qel/Cel to the "
            "electrolyte half over an access arc.  §57 ruled "
            "2026-11-26."
        ),
        "parent": ET_DIST,
        "capabilities": [],
        "token": None,
        "drives": [],
    }
    dl_elyte = {
        "iri": ET_ELYTE,
        "label": "DL Electrolyte",
        "temporal_type": TT_DYN,
        "spatial_type": ST_DIST,
        "spatial_size": SS_FIN,
        "branch": "physical",
        "scale_values": [SVAL_TDYN, SVAL_LDIST],
        "description": (
            "Double-layer electrolyte half — the diffuse-layer "
            "surface volume; child of etype_distributed, hosts the "
            "interfacial reaction (reaction_host inherited).  "
            "Species balance E_50 with reaction sink; reads phi "
            "over an access arc, computes eta := phi − Ue, "
            "r := k_ct*eta (user-ruled linear law), "
            "i := z·F·r — exported to the metal half.  §57 ruled "
            "2026-11-26."
        ),
        "parent": ET_DIST,
        "capabilities": ["reaction_host"],
        "token": None,
        "drives": [],
    }
    for et in (dl_metal, dl_elyte):
        put = et["iri"] in et_existing
        st, out = req(
            "PUT" if put else "POST",
            (f"{API}/ontology/entity-types/"
             f"{urllib.parse.quote(et['iri'], safe='')}?graph={go}"
             if put else f"{API}/ontology/entity-types?graph={go}"),
            et)
        if st not in (200, 201):
            print(f"FAIL etype {et['iri'].split('#')[-1]}: "
                  f"{st} {str(out)[:400]}", file=sys.stderr)
            sys.exit(1)
        print(f"etype {et['iri'].split('#')[-1]}: "
              f"{'PUT' if put else 'POST'} {st}")

    # --- assignments ------------------------------------------------------
    # Resolve live equation IRIs (server mints numeric internal_ids;
    # the authored iri is the durable handle).
    E = lambda iid: eq_iri(live, iid)

    put_assignment({
        "entity_type": ET_METAL,
        "sequence": [E("E_91"), E("E_phi"), E("E_dqel_dl")],
        "base_equation": E("E_dqel_dl"),
        "state_variables": [V_DQELDT],
        "instantiated": [V_T, V_CEL],
        "ports": [V_FE, V_I],
        "outputs": [V_PHI],
    })

    put_assignment({
        "entity_type": ET_ELYTE,
        "sequence": [E("E_51"), E("E_qel_species"), E("E_Ue_cap"),
                     E("E_mu_el"), E("E_eta"), E("E_r_ct"),
                     E("E_iF"), E("E_40"), E("E_42"), E("E_50"),
                     E("E_dqel_ion")],
        "base_equation": E("E_50"),
        "state_variables": [V_DNDT],
        "instantiated": [V_T, V_CEL, V_MU, V_NO, V_KCT],
        "ports": [V_FND, V_FNC, V_PHI],
        "outputs": [V_I, V_MUEL, V_UE, V_DQELDT],
    })

    print("DL pair authored — build charge_02 in the modeller")


if __name__ == "__main__":
    main()
