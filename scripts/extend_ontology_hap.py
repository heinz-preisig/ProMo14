#!/usr/bin/env python3
"""Extend the seed ontology with what the HAP example needs.

Adds (idempotent — safe to re-run):

- domains: ``macroscopic`` and ``reactions`` under ``physical``;
  ``control`` under ``information``.  Tokens are inherited additively
  from the parent, so no explicit token bindings are needed.
- role terms on the physical role axis: ``property``, ``conversion``,
  ``observation``, ``network-structure`` (top level);
  ``secondary-state`` and ``differential-state`` as children of
  ``state``.
- index ``q``: reaction index with ``conversion`` source kind,
  belonging to the ``reactions`` domain.

Saves the ontology graph to ``PROMO_DATA_DIR/ontology.trig`` (or
``./data``).  Restart the backend afterwards so the running store picks
up the file.

Usage::

    uv run python scripts/extend_ontology_hap.py
    uv run python scripts/extend_ontology_hap.py --data-dir /path/to/data
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.graph_store import PROMO, RdfStore  # noqa: E402
from rdflib import URIRef  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=None,
        help="ProMo data directory (default: PROMO_DATA_DIR or ./data)",
    )
    args = parser.parse_args()

    store = RdfStore(args.data_dir)
    store.load()
    g = store.ontology_graph
    base = str(PROMO).rstrip("#")

    phys = URIRef(f"{base}#domain_physical")
    info = URIRef(f"{base}#domain_information")
    role_phys = URIRef(f"{base}#axis_role_physical")
    state_term = URIRef(f"{base}#term_role_state")

    # --- Domains -------------------------------------------------------
    for name, parent, branch in [
        ("macroscopic", phys, "physical"),
        ("reactions", phys, "physical"),
        ("control", info, "information"),
    ]:
        iri = store.mint_iri(base, f"domain_{name}")
        store.add_domain(g, name, iri=iri, parent=parent, branch=branch)
        print(f"domain  {name:<12} parent={parent.split('#')[-1]}")

    # --- Role terms (physical axis) ------------------------------------
    for frag, label, parent in [
        ("property", "property", None),
        ("conversion", "conversion", None),
        ("observation", "observation", None),
        ("network_structure", "network-structure", None),
        ("secondary_state", "secondary-state", state_term),
        ("differential_state", "differential-state", state_term),
    ]:
        iri = store.mint_iri(base, f"term_role_{frag}")
        store.add_axis_term(g, iri, role_phys, label, parent=parent)
        p = f" < {parent.split('#')[-1]}" if parent else ""
        print(f"term    {label:<20}{p}")

    # --- Index q (reaction index, conversion source) -------------------
    q_iri = store.mint_iri(base, "idx_reaction_q")
    if (q_iri, None, None) in g:
        print("index   q                    (already present, skipped)")
    else:
        internal_id = store.next_internal_id("I")
        store.add_index_dict(g, {
            "iri": str(q_iri),
            "label": "reaction",
            "short_name": "q",
            "network": "reactions",
            "index_class": "conversion",
            "internal_id": internal_id,
            "aliases": {"global_ID": internal_id, "internal_code": "q"},
            "doc": "Reaction index (conversion source), reactions domain",
        })
        print(f"index   q                    {internal_id}")

    out = store.save()
    print(f"\nSaved {len(g)} triples to {out}")
    print("Restart the backend (./dev.sh restart) to pick up the file.")


if __name__ == "__main__":
    main()
