#!/usr/bin/env python3
"""ONE-TIMER — applied 2026-11-24.  Safe to delete on cleanup.

§41 component fold — rewrote the v[C]/r[C] consumers via the equation
API (the editor write path, not data migration — §41 ruling 6).  Kept
in the repo only so the mechanical edit list is on record; the patterns
no longer match post-fold, so re-running fails loudly by design.

Requires a live backend (``./dev.sh start``).  What it did:

- GET ``/api/equation/context`` for ``library`` + ``ontology`` —
  fetched each variable's full record (same payload the editor loads).
- String-swapped ``rhs`` in each equation below.
- ``PUT /api/equation/variables/{iri}?graph=…`` — replace semantics;
  the write path re-checked, re-canonicalised the expression tree and
  refreshed ``incidence_list``/``rhs_latex``.

Gotchas recorded in ``docs/session-handoff-2026-11-24.md``: path IRIs
must be URL-encoded (an unencoded ``#`` swallows ``?graph=``), and
``record.equations`` is not keyed by IRI fragment.
"""
import json
import sys
import urllib.parse
import urllib.request

BASE = "http://localhost:8000/api/equation"
LIB = "https://w3id.org/promo/library"
ONT = "https://w3id.org/promo/ontology"

# (graph, var fragment, eq key, old substring, new substring)
REWRITES = [
    # kConv{i} := (...) * v_i  ->  (...) * reduceSum(e_i*v, C)
    (LIB, "V_39", "E_12", "* vx )", "* reduceSum( ( physical!e_x * v ), C ) )"),
    (LIB, "V_40", "E_13", "* vy )", "* reduceSum( ( physical!e_y * v ), C ) )"),
    (LIB, "V_41", "E_14", "* vz )", "* reduceSum( ( physical!e_z * v ), C ) )"),
    # kDiff{i} := inv(mu) * ( v_i * (... ) )
    (LIB, "V_42", "E_15", "( vx *", "( reduceSum( ( physical!e_x * v ), C ) *"),
    (LIB, "V_43", "E_16", "( vy *", "( reduceSum( ( physical!e_y * v ), C ) *"),
    (LIB, "V_44", "E_17", "( vz *", "( reduceSum( ( physical!e_z * v ), C ) *"),
    # kQ{i} := ( inv(V)*Cp ) * v_i
    (LIB, "V_50", "E_23", "* vx )", "* reduceSum( ( physical!e_x * v ), C ) )"),
    (LIB, "V_51", "E_24", "* vy )", "* reduceSum( ( physical!e_y * v ), C ) )"),
    (LIB, "V_52", "E_25", "* vz )", "* reduceSum( ( physical!e_z * v ), C ) )"),
    # A_{ij} := r_i * r_j
    (LIB, "V_53", "E_26", "( physical!r_x * physical!r_z )",
     "( reduceSum( ( physical!e_x * physical!r ), C ) * reduceSum( ( physical!e_z * physical!r ), C ) )"),
    (LIB, "V_54", "E_27", "( physical!r_y * physical!r_z )",
     "( reduceSum( ( physical!e_y * physical!r ), C ) * reduceSum( ( physical!e_z * physical!r ), C ) )"),
    # fKin := fmc*half*|v|^2
    (LIB, "V_106", "E_fKin",
     "( ( macroscopic!fmc * half ) * ( ( ( macroscopic!vx * macroscopic!vx ) + ( macroscopic!vy * macroscopic!vy ) ) + ( macroscopic!vz * macroscopic!vz ) ) )",
     "( ( macroscopic!fmc * half ) * reduceSum( ( macroscopic!v * macroscopic!v ), C ) )"),
    # fPot := fmc*g*r_z
    (LIB, "V_107", "E_fPot", "* physical!r_z )",
     "* reduceSum( ( physical!e_z * physical!r ), C ) )"),
    # Axy := r_x * r_y  (ontology graph — owns E_3)
    (ONT, "V_17", "E_3", "( physical!r_x * physical!r_y )",
     "( reduceSum( ( physical!e_x * physical!r ), C ) * reduceSum( ( physical!e_y * physical!r ), C ) )"),
]


def req(method, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    contexts = {}
    for graph in (LIB, ONT):
        st, ctx = req("GET", f"{BASE}/context?graph={graph}")
        assert st == 200, ctx
        contexts[graph] = {v["iri"]: v for v in ctx["variables"]}

    failures = []
    for graph, frag, eqkey, old, new in REWRITES:
        iri = f"{graph}#{frag}"
        rec = contexts[graph].get(iri)
        if rec is None:
            failures.append((iri, "variable not in context"))
            continue
        eq = next((e for e in rec["equations"].values()
                   if e["iri"].endswith(f"#{eqkey}")), None)
        if eq is None:
            failures.append((iri, f"equation {eqkey} not found"))
            continue
        if old not in eq["rhs"]:
            failures.append((iri, f"pattern not found in {eqkey}: {old!r}"))
            continue
        eq["rhs"] = eq["rhs"].replace(old, new)
        url = (f"{BASE}/variables/{urllib.parse.quote(iri, safe='')}"
               f"?graph={urllib.parse.quote(graph, safe='')}")
        st, out = req("PUT", url, rec)
        if st != 200:
            failures.append((iri, f"PUT {st}: {out}"))
            continue
        new_eq = next((e for e in out["equations"].values()
                       if e["iri"].endswith(f"#{eqkey}")), None)
        if new_eq is None:
            failures.append((iri, "equation missing in PUT response"))
            continue
        ok = (new_eq["rhs"] == eq["rhs"]
              and new_eq.get("rhs_latex"))
        print(f"{frag}/{eqkey}: PUT {st} rhs-ok={ok}")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" ", f)
        sys.exit(1)
    print("\nall rewrites applied")


if __name__ == "__main__":
    main()
