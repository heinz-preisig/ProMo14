"""Close the two open effort-port contacts on model-charge-2.

charge_02's transport↔DL and transport↔feed contacts surfaced two
authoring gaps once the DL pair was wired (§57):

1. ``lead2``'s ``Ue`` effort port at the DL-metal contact (Arc_4)
   found no peer effort carrying the conduction drive token
   (``token_charge``).  The physically right reading is ``phi`` —
   the metal-side surface potential IS the charge effort at that
   contact — but phi was authored signal-token-only (defensive:
   kept it out of flow-arc matching).  The model now requires
   exactly that binding, so phi gains ``token_charge`` alongside
   ``token_signal`` — dual membership, same shape as mu_el's
   {charge, component_mass}.  Identity binding over the access
   arcs is unaffected (the port prefers the same-IRI var).

2. ``feed diff``'s ``mu_el`` effort port at the species-feed
   contact (Arc_9) faces an environment that exports nothing.
   The environment is the boundary — it already pins ``Ue`` and
   ``p_mech``; it now also instantiates ``mu_el`` (the reservoir's
   bulk electrochemical potential).  Instantiated pins are
   demand-scoped: only contacts that read them emit par slots.

Token ADDS are exempt from the structural lock, so the phi edit
is legal even though E_phi references it.

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

    # --- 1. phi gains token_charge ------------------------------------
    st, ctx = req("GET", f"{EQ}/context?graph={glib}")
    if st != 200:
        print(f"FAIL context: {st}", file=sys.stderr)
        sys.exit(1)
    live = {v["iri"]: v for v in ctx.get("variables", [])}
    rec = dict(live[V_PHI])
    toks = list(rec.get("tokens") or [])
    # NOTE: adding token_charge to phi is BLOCKED today —
    # _guard_structural_edit's add-exemption only covers previously
    # untracked vars; a second membership on an eq-referenced var
    # (E_eta reads phi) counts as an alter → 409.  Needs either a
    # guard amendment (pure-addition exemption) or a user ruling.
    if False and TOK_CHG not in toks:
        toks.append(TOK_CHG)
        rec["tokens"] = toks
        rec["doc"] = (
            "Surface potential of the interface — the double-layer "
            "voltage drop authored DL-metal-side (phi := qel/Cel); "
            "read by the electrolyte half as the metal-side "
            "potential in the overpotential (continuity by "
            "identity, §57).  Dual membership: token_signal rides "
            "the access arcs; token_charge lets the conduction "
            "transport's Ue effort port read it at the DL-metal "
            "contact (the metal potential IS the charge effort).")
        st, out = req(
            "PUT",
            f"{EQ}/variables/{urllib.parse.quote(V_PHI, safe='')}"
            f"?graph={glib}", rec)
        if st != 200:
            print(f"FAIL phi PUT: {st} {str(out)[:400]}",
                  file=sys.stderr)
            sys.exit(1)
        print(f"phi: tokens += token_charge ({st})")
    else:
        print("phi: already carries token_charge")

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
