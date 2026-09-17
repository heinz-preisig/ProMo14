#!/usr/bin/env python3
"""Export the ProMo ontology graph to Turtle for publishing.

Serialises the editable ontology named graph
(``https://w3id.org/promo/ontology``) to a Turtle file suitable for
hosting on GitHub Pages.  If ``PROMO_DATA_DIR`` (or ``--data-dir``)
contains an ``ontology.trig``, that content is exported; otherwise the
default seed ontology is generated and exported.

Usage::

    uv run python scripts/export_ontology.py --out ontology.ttl
    uv run python scripts/export_ontology.py --data-dir /path/to/data --out ontology.ttl
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.graph_store import PROMO, PROMOLG, QUDT, RdfStore  # noqa: E402
from rdflib import URIRef  # noqa: E402
from rdflib.namespace import RDF, RDFS  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=None,
        help="ProMo data directory (default: PROMO_DATA_DIR or ./data)",
    )
    parser.add_argument(
        "--out",
        default="ontology.ttl",
        help="Output Turtle file (default: ontology.ttl)",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Freeze the working ontology as this version (e.g. 1.0) "
             "and export the frozen graph.  Re-running with an existing "
             "version re-exports it (frozen graphs are immutable).",
    )
    args = parser.parse_args()

    store = RdfStore(args.data_dir)
    store.load()

    if args.version:
        version_iri = URIRef(
            f"{store.ONTOLOGY_GRAPH_IRI}/{args.version}")
        if not len(store.dataset.graph(version_iri)):
            store.freeze_version(args.version)
            store.save()
            print(f"Froze ontology as {version_iri}")
        graph = store.dataset.graph(version_iri)
    else:
        graph = store.ontology_graph
    # Bind prefixes on the graph itself so the Turtle is readable.
    graph.bind("promo", PROMO)
    graph.bind("promolg", PROMOLG)
    graph.bind("qudt", QUDT)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)

    out = Path(args.out)
    graph.serialize(str(out), format="turtle")
    print(f"Wrote {len(graph)} triples to {out}")


if __name__ == "__main__":
    main()
