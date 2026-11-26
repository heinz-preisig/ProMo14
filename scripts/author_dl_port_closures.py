"""Close the two open effort-port contacts on model-charge-2.

charge_02's transport↔DL and transport↔feed contacts surfaced two
authoring gaps once the DL pair was wired (§57):

1. ``lead2``'s ``Ue`` effort port at the DL-metal contact (Arc_4)
   found no peer effort carrying the conduction drive token
   (``token_charge``).  The first attempt added ``token_charge``
   to phi — it bound, but the membership also widened phi's own
   port surface to token-flow arcs (§57's signal-only design
   exists to prevent that).  SUPERSEDED: phi reverted to
   signal-only and dl_metal defines ``Ue`` itself via E_Ue_cap,
   so the port binds by identity — see author_dl_ue_bridge.py.

2. ``feed diff``'s ``mu_el`` effort port at the species-feed
   contact (Arc_9) faces an environment that exports nothing.
   The environment is the boundary — it already pins ``Ue`` and
   ``p_mech``; it now also instantiates ``mu_el`` (the reservoir's
   bulk electrochemical potential).  Instantiated pins are
   demand-scoped: only contacts that read them emit par slots.

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

V_PHI = f"{LIB}#V_146"
V_MUEL = f"{LIB}#V_139"
TOK_CHG = f"{ONT}#token_charge"
ET_ENV = f"{ONT}#etype_environment"


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
    glib = urllib.parse.quote(LIB, safe="")
    gasg = urllib.parse.quote(ASG, safe="")

    # --- 1. DL-metal contact: SUPERSEDED -------------------------------
    # First attempt added token_charge to phi so lead2's Ue effort
    # port could read it.  It bound — but the extra membership also
    # widened phi's own port surface to token-flow arcs (dl_elyte's
    # phi port began demanding an effort at the ionic contact), the
    # exact side effect §57's signal-only ruling prevents.  Reverted:
    # phi carries token_signal only, and dl_metal instead defines Ue
    # itself (E_Ue_cap in its sequence) so the port binds by identity.
    # See author_dl_ue_bridge.py.
    print("phi/dual-membership step: superseded by "
          "author_dl_ue_bridge.py — no-op")

    # --- 2. environment instantiates mu_el ----------------------------
    st, asg = req(
        "GET",
        f"{API}/behaviour/assignment?graph={gasg}"
        f"&entity_type={urllib.parse.quote(ET_ENV, safe='')}")
    if st != 200:
        print(f"FAIL env assignment GET: {st} {str(asg)[:300]}",
              file=sys.stderr)
        sys.exit(1)
    inst = list(asg.get("instantiated") or [])
    if V_MUEL not in inst:
        inst.append(V_MUEL)
        body = {
            "entity_type": ET_ENV,
            "sequence": list(asg.get("sequence") or []),
            "base_equation": asg.get("base_equation"),
            "state_variables": list(asg.get("state_variables") or []),
            "instantiated": inst,
            "ports": list(asg.get("ports") or []),
            "outputs": list(asg.get("outputs") or []),
        }
        st, out = req("PUT",
                      f"{API}/behaviour/assignment?graph={gasg}", body)
        if st != 200:
            print(f"FAIL env assignment PUT: {st} {str(out)[:400]}",
                  file=sys.stderr)
            sys.exit(1)
        print(f"env: instantiated += mu_el "
              f"(closed={out.get('closed')})")
    else:
        print("env: already instantiates mu_el")

    # --- save ----------------------------------------------------------
    st, out = req("POST", f"{API}/ontology/save")
    print("save:", st, "dirty now:", (out or {}).get("dirty"))


if __name__ == "__main__":
    main()
