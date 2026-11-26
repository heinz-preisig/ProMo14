"""Correct the charge_02 DL-metal effort closure — identity, not membership.

Supersedes the phi += token_charge step in
``author_dl_port_closures.py``.  That edit bound lead2's ``Ue``
port at Arc_4, but adding charge membership widened phi's OWN
port surface to token-flow arcs — dl_elyte's phi port began
demanding an effort at the ionic-diffusion contact (Arc_5), the
exact side effect §57's signal-only ruling exists to prevent.

Clean closure via the identity channel instead:

1.  phi reverts to ``token_signal`` only.  The PUT is structural-
    locked while E_eta references phi, so E_eta is first written
    with rhs ``( Ue )`` (phi's incidence drops), phi is reverted,
    then E_eta is restored verbatim — the equation survives, same
    IRI, canonical form regenerated.

2.  dl_metal's assignment gains ``E_Ue_cap`` (the existing
    ``Ue := inv(Cel)*qel`` — identical rhs to E_phi) in its
    sequence and ``Ue`` in outputs.  The conduction transport's
    ``Ue`` effort port at Arc_4 then binds dl_metal's ``Ue`` by
    *identity* — ``w_iri == v_iri`` skips every token/effort/drive
    filter — so phi never needed charge membership at all.

phi stays signal-only: its port surface remains the access arcs.

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
V_ETA = f"{LIB}#V_147"
V_UE = f"{LIB}#V_133"
E_ETA = f"{LIB}#E_eta"
E_UE_CAP = f"{LIB}#E_Ue_cap"
TOK_SIG = f"{ONT}#token_signal"
TOK_CHG = f"{ONT}#token_charge"
ET_METAL = f"{ONT}#etype_dl_metal"


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


def fail(msg, st, out):
    print(f"FAIL {msg}: {st} {str(out)[:400]}", file=sys.stderr)
    sys.exit(1)


def put_var(iri, rec, glib, tag):
    st, out = req(
        "PUT",
        f"{EQ}/variables/{urllib.parse.quote(iri, safe='')}"
        f"?graph={glib}", rec)
    if st != 200:
        fail(f"{tag} PUT", st, out)
    return out


def main():
    glib = urllib.parse.quote(LIB, safe="")
    gasg = urllib.parse.quote(ASG, safe="")

    st, ctx = req("GET", f"{EQ}/context?graph={glib}")
    if st != 200:
        fail("context", st, ctx)
    live = {v["iri"]: v for v in ctx.get("variables", [])}
    phi = dict(live[V_PHI])
    eta = dict(live[V_ETA])

    # -- 1. dl_metal defines Ue (E_Ue_cap reuse) -------------------------
    # Done FIRST: while phi still carries charge the Arc_4 port already
    # prefers the identity binding, so the port stays bound through the
    # whole transition — a failed phi revert can't strand it unbound.
    st, asg = req(
        "GET",
        f"{API}/behaviour/assignment?graph={gasg}"
        f"&entity_type={urllib.parse.quote(ET_METAL, safe='')}")
    if st != 200:
        fail("dl_metal assignment GET", st, asg)
    seq = list(asg.get("sequence") or [])
    out_ = list(asg.get("outputs") or [])
    changed = False
    if E_UE_CAP not in seq:
        # after E_phi — needs qel (E_qel_def) and Cel (inst) first
        pos = seq.index(f"{LIB}#E_phi") + 1 if f"{LIB}#E_phi" in seq \
            else len(seq)
        seq.insert(pos, E_UE_CAP)
        changed = True
    if V_UE not in out_:
        out_.append(V_UE)
        changed = True
    if changed:
        body = {
            "entity_type": ET_METAL,
            "sequence": seq,
            "base_equation": asg.get("base_equation"),
            "state_variables": list(asg.get("state_variables") or []),
            "instantiated": list(asg.get("instantiated") or []),
            "ports": list(asg.get("ports") or []),
            "outputs": out_,
        }
        st, o = req("PUT",
                    f"{API}/behaviour/assignment?graph={gasg}", body)
        if st != 200:
            fail("dl_metal assignment PUT", st, o)
        print(f"dl_metal: seq += E_Ue_cap, out += Ue "
              f"(closed={o.get('closed')})")
    else:
        print("dl_metal: already defines Ue")

    toks = set(phi.get("tokens") or [])

    if TOK_CHG in toks:
        # -- 1a. unlock phi: E_eta temporarily drops its phi ref --------
        eta_tmp = dict(eta)
        for e in (eta_tmp.get("equations") or {}).values():
            if e.get("iri") == E_ETA:
                e["rhs"] = "( Ue )"
        put_var(V_ETA, eta_tmp, glib, "eta temp")

        # -- 1b. phi back to signal-only ------------------------------
        phi["tokens"] = [t for t in (phi.get("tokens") or [])
                         if t != TOK_CHG] or [TOK_SIG]
        phi["doc"] = (
            "Surface potential of the interface — the double-layer "
            "voltage drop authored DL-metal-side (phi := qel/Cel); "
            "read by the electrolyte half as the metal-side "
            "potential in the overpotential (continuity by "
            "identity, §57).  Signal-token only: rides access "
            "arcs, invisible to flow-arc matching.")
        try:
            put_var(V_PHI, phi, glib, "phi revert")
        except SystemExit:
            # restore E_eta before aborting so data stays coherent
            put_var(V_ETA, eta, glib, "eta restore")
            raise

        # -- 1c. restore E_eta verbatim --------------------------------
        put_var(V_ETA, eta, glib, "eta restore")
        print("phi: tokens -> [token_signal] (E_eta rewritten + restored)")
    else:
        print("phi: already signal-only")

    # -- save -----------------------------------------------------------
    st, out = req("POST", f"{API}/ontology/save")
    print("save:", st)


if __name__ == "__main__":
    main()
