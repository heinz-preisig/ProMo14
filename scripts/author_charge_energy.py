#!/usr/bin/env python3
"""Wire ``Pel`` into the charged-lump energy balance (§57, §50/51
pattern).

The electric transfer term ``Ue*fe`` must enter the charged
lump's energy balance (§57 — "mandatory bookkeeping, not a
diagnostic").  This script lands the §50/§51 shape on the charge
side:

  ``apel``  electric power aggregate — ``reduceSum(F_el*(Ue*fe),
            A_el)`` — the per-contact effort×flow folded into the
            gather; algebraically ``Ue·dqeldt`` = the capacitor
            input power.  Macroscopic (``E_dqeldt``'s qualifier
            shape), [N], class/token cloned from ``aw``.
  ``dUdt``  charged-lump energy rate — ``dUdt := apel`` — mirrors
            ``dHdt``'s diagnostic-output role (a reading, no new
            state); macroscopic, [N], class cloned from ``dHdt``.

BOUND-SCOPE FINDING (2026-11-26): the transport-side ``Pel :=
Ue*fe`` cannot emit — in the conduction transport's bound scope
``Ue`` binds ``[X]`` (per-contact effort) while ``fe`` binds
``[A_el,N]``, so the elementwise product produces ``[X,A_el,N]``
against the declared ``[A_el,N]``.  The X↔A_el per-contact join is
the §32/§45 bound-scope contract gap — same family as the §40
implicit-contraction break.  ``Pel`` therefore stays
authored-but-unwired (no sequence/output marks); the lump-side
``Ue*fe`` lands the §57 term faithfully.  A transport-side Pel
would want either the join machinery or the Joule spelling
``fe * reduceSum(sigma*Ue, X)`` (leg dissipation — a different
reading).

Assignment wiring (assignments artefact):

  ``etype_conduction_transport`` — unchanged from stage 1
            (``E_Pel`` left unsequenced).
  ``etype_lumped_conductor``     — ``E_apel``+``E_dUdt`` appended
            to sequence, ``dUdt`` joins ``outputs``.  ``F_el`` needs
            no instantiated mark — constant-class, an implicit
            instantiation endpoint (same as in ``E_dqeldt``).

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

IDX_N = f"{ONT}#idx_node"
IDX_AEL = f"{ONT}#idx_arc_charge"
EQ_GENERIC = f"{ONT}#eqclass_generic"

U_WATT = [-3, 2, 0, 1, 0, 0, 0, 0]   # W = J/s

V_APEL = f"{LIB}#V_144"
V_DUDT = f"{LIB}#V_145"
V_PEL = f"{LIB}#V_140"
V_FE = f"{LIB}#V_132"
V_UE = f"{LIB}#V_133"

E_APEL = f"{LIB}#E_apel"
E_DUDT = f"{LIB}#E_dUdt"
E_PEL = f"{LIB}#E_Pel"
E_DQELDT = f"{LIB}#E_dqeldt"
E_QEL_DEF = f"{LIB}#E_qel_def"
E_UE_CAP = f"{LIB}#E_Ue_cap"
E_FE_OHM = f"{LIB}#E_fe_ohm"


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


def var(frag, label, doc, *, network, latex, cls, tokens, equations):
    iri = f"{LIB}#{frag}"
    return {
        "iri": iri,
        "label": label,
        "network": network,
        "domain_iri": f"{ONT}#domain_{network}",
        "type": None,
        "units": U_WATT,
        "index_structures": [IDX_N],
        "internal_id": frag,
        "aliases": {"latex": latex, "global_ID": iri},
        "doc": doc,
        "port_variable": False,
        "frozen": False,
        "tokens": tokens,
        "token_vector": None,
        "value": None,
        "equations": equations,
        "classifications": cls,
    }


def eq(frag, lhs_iri, rhs, doc, network):
    return {
        "iri": f"{LIB}#{frag}",
        "internal_id": frag,
        "lhs": lhs_iri,
        "rhs": rhs,
        "equation_class": EQ_GENERIC,
        "network": network,
        "doc": doc,
    }


def main():
    g = urllib.parse.quote(LIB, safe="")
    st, ctx = req("GET", f"{EQ}/context?graph={g}")
    if st != 200:
        print(f"FATAL context: {st} {str(ctx)[:200]}")
        sys.exit(1)
    by_iri = {v["iri"]: v for v in ctx["variables"]}
    existing = set(by_iri)

    # Clone classification + token membership from the §50/§51
    # counterparts so the new vars sit in the same regime.
    aw = by_iri[f"{LIB}#V_105"]            # aw — work gather
    dhdt = by_iri[f"{LIB}#V_103"]         # dHdt — energy rate
    aw_cls = aw.get("classifications") or {}
    dh_cls = dhdt.get("classifications") or {}
    aw_tok = aw.get("tokens") or []
    dh_tok = dhdt.get("tokens") or []

    new_vars = [
        var("V_144", "apel",
            "electric power aggregate — signed sum of Pel over the "
            "charge contacts of a lump (F_el gather); mirrors aw's "
            "F_work*fWs gather (§57 energy bookkeeping).",
            network="macroscopic", latex="{a}^{el}",
            cls=aw_cls, tokens=aw_tok,
            equations={
                "E_apel": eq("E_apel", V_APEL,
                             "reduceSum( ( physical!F_el * "
                             "( Ue * fe ) ), A_el )",
                             "electric input power — the lump's "
                             "own Ue × net current per contact "
                             "(= Ue·dqeldt) (§57)",
                             network="macroscopic"),
            }),
        var("V_145", "dUdt",
            "charged-lump energy rate — net electric power in; a "
            "diagnostic balance reading on the capacitive "
            "conductor (§57 mandatory bookkeeping).",
            network="macroscopic", latex="\\dot{U}",
            cls=dh_cls, tokens=dh_tok,
            equations={
                "E_dUdt": eq("E_dUdt", V_DUDT,
                             "( apel )",
                             "energy rate of the charged lump — "
                             "electric leg only (§57)",
                             network="macroscopic"),
            }),
    ]

    for rec in new_vars:
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

    # Refresh pass — canonicalise incidence (stage-1/2 pattern).
    for rec in new_vars:
        st, out = req("PUT",
                      f"{EQ}/variables/{urllib.parse.quote(rec['iri'], safe='')}?graph={g}",
                      rec)
        if st != 200:
            print(f"FAIL {rec['label']} refresh: {st} "
                  f"{str(out)[:300]}", file=sys.stderr)
            sys.exit(1)
        print(f"{rec['label']} refresh: PUT {st}")

    # Assignment wiring -------------------------------------------------
    ga = urllib.parse.quote(ASG, safe="")
    conduction = {
        "entity_type": f"{ONT}#etype_conduction_transport",
        "sequence": [E_FE_OHM, E_DQELDT],
        "base_equation": E_DQELDT,
        "state_variables": [],
        "instantiated": [f"{LIB}#V_131", f"{LIB}#V_135",
                         f"{LIB}#V_136", f"{ONT}#F_el"],
        "ports": [V_UE],
        "outputs": [V_FE],
    }
    st, out = req("PUT", f"{API}/behaviour/assignment?graph={ga}",
                  conduction)
    if st != 200:
        print(f"FAIL conduction assignment: {st} {str(out)[:400]}",
              file=sys.stderr)
        sys.exit(1)
    print(f"assignment conduction: closed={out.get('closed')} "
          f"seq={[s.rsplit('#', 1)[-1] for s in out.get('sequence', [])]}")

    conductor = {
        "entity_type": f"{ONT}#etype_lumped_conductor",
        "sequence": [E_QEL_DEF, E_UE_CAP, E_DQELDT, E_APEL, E_DUDT],
        "base_equation": E_DQELDT,
        "state_variables": [f"{LIB}#V_131"],
        "instantiated": [f"{LIB}#V_134", f"{ONT}#V_11"],
        "ports": [V_FE],
        "outputs": [V_UE, V_DUDT],
    }
    st, out = req("PUT", f"{API}/behaviour/assignment?graph={ga}",
                  conductor)
    if st != 200:
        print(f"FAIL conductor assignment: {st} {str(out)[:400]}",
              file=sys.stderr)
        sys.exit(1)
    print(f"assignment conductor: closed={out.get('closed')} "
          f"seq={[s.rsplit('#', 1)[-1] for s in out.get('sequence', [])]}")

    print("charge energy wiring (apel + dUdt + Pel port/output) authored")


if __name__ == "__main__":
    main()
