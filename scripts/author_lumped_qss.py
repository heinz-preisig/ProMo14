#!/usr/bin/env python3
"""§47 quasi-steady lumped capacity — sibling entity type + assignment.

Ruling (2026-11-24): both momentum regimes live side by side.  The
dynamic lump (`etype_lumped`) integrates dPdt; the quasi-steady sibling
(`etype_lumped_qss`) drops it from `state_variables` — the mechanical
DOF is event-dynamic, the balance E_dPdt stays in the sequence as an
algebraic net-force output (= support reaction).  Stiff integration of
the fast pressure/momentum mode is avoided on large models; the choice
is per-node via entity type.

- POST /api/ontology/entity-types — etype_lumped_qss, child of
  etype_lumped (capability inheritance: cap_reaction_host), same scale
  composition (uniform/finite, macro dynamic — mass/energy still
  integrate).
- PUT /api/behaviour/assignment — same sequence/ports/instantiated/
  outputs as the dynamic assignment; state_variables=[V_57 dmdt]
  only (V_121 dPdt removed).

2026-11-24 PM repair: the original authoring was lost to the
uvicorn-reload wipe before it ever reached .trig (the §47 commit's
data diff contains no lumped_qss triples).  Re-running this script
restored it — and exposed a second gap: §48's E_m_def integral
binds universe!t (V_11), which no assignment instantiated, so BOTH
lumped assignments now evaluate unclosed.  `t` is the solver's
integration variable — runtime-supplied like p_mech — so it joins
`instantiated` here and on the dynamic assignment.

Idempotent: PUT semantics on both endpoints.
"""
import json
import sys
import urllib.parse
import urllib.request

API = "http://localhost:8000/api"
ONT = "https://w3id.org/promo/ontology"
LIB = "https://w3id.org/promo/library"
ASG = "https://w3id.org/promo/library/assignments"


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
    failures = []

    # -- 1. sibling entity type ----------------------------------------
    etype = {
        "iri": f"{ONT}#etype_lumped_qss",
        "label": "Lumped QSS",
        "temporal_type": "dynamic",
        "spatial_type": "uniform",
        "spatial_size": "finite",
        "branch": "physical",
        "scale_values": [
            f"{ONT}#sval_length_macroscopic_uniform",
            f"{ONT}#sval_time_macro_dynamic",
        ],
        "description": (
            "Quasi-steady-momentum lumped capacity — same uniform/finite "
            "macro-dynamic lump as etype_lumped, but the mechanical DOF "
            "is event-dynamic: dPdt is not integrated, the momentum "
            "balance is algebraic (net force = support reaction).  "
            "Per-node regime choice; use on large models where "
            "integrating the fast momentum mode forces a stiff solver."),
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
        print(f"etype_lumped_qss: POST {st} "
              f"capabilities={out.get('capabilities')}")

    # -- 2. quasi-steady assignment -------------------------------------
    selection = {
        "entity_type": f"{ONT}#etype_lumped_qss",
        "sequence": [f"{LIB}#E_m_def", f"{LIB}#E_F_g",
                     f"{LIB}#E_dPdt", f"{LIB}#E_29"],
        "base_equation": f"{LIB}#E_29",
        "state_variables": [f"{LIB}#V_57"],          # dmdt only
        "instantiated": [f"{ONT}#V_34", f"{ONT}#V_11"],  # p_mech + t
        "ports": [f"{LIB}#V_117", f"{LIB}#V_118", f"{LIB}#V_56"],
        "outputs": [f"{LIB}#V_121"],                 # dPdt: algebraic
    }
    st, out = req("PUT",
                  f"{API}/behaviour/assignment"
                  f"?graph={urllib.parse.quote(ASG, safe='')}",
                  selection)
    if st != 200:
        failures.append(("assignment", f"{st}: {str(out)[:400]}"))
    else:
        print(f"assignment etype_lumped_qss: PUT {st} "
              f"closed={out.get('closed')} "
              f"states={[s.rsplit('#', 1)[-1] for s in out.get('state_variables', [])]} "
              f"seq={[s.rsplit('#', 1)[-1] for s in out.get('sequence', [])]}")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" ", f)
        sys.exit(1)
    print("\nsibling etype + qss assignment authored")


if __name__ == "__main__":
    main()
