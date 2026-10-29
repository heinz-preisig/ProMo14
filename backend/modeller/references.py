"""§22 reference resolution — the referenced-model DAG.

Walks ``promo:usesModel`` pins (the derived index written on each
model save) transitively across artefact graphs.  References nest
recursively; a transitive self-reference is a ``reference-cycle``
problem — resolution reports the offending loops instead of
recursing forever.
"""

from __future__ import annotations

from typing import Dict, List

from rdflib import URIRef

from backend.core.graph_store import PROMO


def reference_dag(store, root_iri: str) -> Dict[str, List[str]]:
    """``{artefact IRI: [referenced model IRIs]}`` for ``root_iri`` and
    everything reachable through ``usesModel``.  Cycles do not block
    the walk — each graph is visited once."""
    dag: Dict[str, List[str]] = {}
    stack = [root_iri]
    while stack:
        iri = stack.pop()
        if iri in dag:
            continue
        g = store.dataset.graph(URIRef(iri))
        refs = sorted(str(o) for o in
                      g.objects(g.identifier, PROMO["usesModel"]))
        dag[iri] = refs
        stack.extend(r for r in refs if r not in dag)
    return dag


def reference_cycles(dag: Dict[str, List[str]], root_iri: str) -> List[List[str]]:
    """``reference-cycle`` loops: paths from ``root_iri`` that return to
    an ancestor on the path (a transitive self-reference)."""
    cycles: List[List[str]] = []

    def walk(iri: str, path: List[str]):
        for ref in dag.get(iri, []):
            if ref in path:
                cycles.append(path[path.index(ref):] + [ref])
            else:
                walk(ref, path + [ref])

    walk(root_iri, [root_iri])
    return cycles
