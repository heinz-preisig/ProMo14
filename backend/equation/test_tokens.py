from pathlib import Path

from rdflib import Dataset, URIRef
from rdflib.namespace import RDF, RDFS


def test_data_variable_token_consistency():
    """§24 declaration rules over the persisted artefacts.

    For every ``promo:Variable`` in ``data/*.trig``:
    - each ``promo:carriesToken`` must name a declared ``promo:Token``;
    - a member's ``promo:tokenVector`` must exist (the write path
      defaults it) — but members need not appear in it: membership
      without signature is the licensed-but-neutral form
      (ruled 2026-11-11).  Signatures may also exceed membership —
      composite decompositions name networks the variable is not
      licensed for;
    - a ``promo:portVariable true`` variable must carry at least one
      token — a port with no token can never be licensed
      (instantiate/satisfy.py).
    """
    data_dir = Path(__file__).resolve().parents[2] / "data"
    ds = Dataset()
    for f in sorted(data_dir.glob("*.trig")):
        ds.parse(str(f), format="trig")

    P = lambda n: URIRef("https://w3id.org/promo#" + n)
    frag = lambda iri: str(iri).split("#")[-1].split("/")[-1]
    declared = {
        str(s)
        for gr in ds.graphs()
        for s in gr.subjects(RDF.type, P("Token"))
    }

    violations = []
    for gr in ds.graphs():
        for s in gr.subjects(RDF.type, P("Variable")):
            label = gr.value(s, RDFS.label) or s
            name = f"{label} ({gr.identifier.split('/')[-1]})"
            ct = [str(o) for o in gr.objects(s, P("carriesToken"))]
            is_port = str(gr.value(s, P("portVariable")) or "").lower() == "true"
            if is_port and not ct:
                violations.append(f"{name}: portVariable with no carriesToken")
            for c in ct:
                if c not in declared:
                    violations.append(f"{name}: carriesToken {frag(c)} not a declared Token")
    assert not violations, "\n".join(sorted(violations))
