"""Load a ProMo project from the legacy v8 JSON/TriG files in PROMO_DATA_DIR.

This is a stepping-stone loader: it reads ``variables_v8.json`` (and an
optional ``fix_variables_v8.json`` overlay), ``ontology.json``, and the legacy
``variableExpression.trig`` var/expr graph.  It converts the legacy records
into the ``EquationContext`` shape the checker and frontend already use.

When a real RDF graph store is implemented, this loader can be replaced by an
``RdfContext`` that reads the same data as TriG/JSON-LD.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import rdflib
from rdflib import Dataset, Namespace

from .config import get_data_dir

V8_FILES = ["variables_v8.json", "fix_variables_v8.json"]
ONTOLOGY_FILE = "ontology.json"
TRIG_FILES = ["variableExpression.trig", "model.trig"]

PROMO = Namespace("http://example.org#")
INDICES = Namespace("http://example.org/indices#")


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_trig_file(data_dir: Path) -> Optional[Path]:
    for name in TRIG_FILES:
        path = data_dir / name
        if path.exists():
            return path
    return None


def _load_v8_records(data_dir: Path) -> Dict[str, dict]:
    """Merge all available v8 variable files, later files overlay earlier ones."""
    records: Dict[str, dict] = {}
    found = False
    for name in V8_FILES:
        path = data_dir / name
        if path.exists():
            found = True
            raw = _load_json(path)
            records.update(raw.get("variables", {}))
    if not found:
        raise FileNotFoundError(
            f"No v8 variable file ({', '.join(V8_FILES)}) found in {data_dir}"
        )
    return records


def _index_network(record: dict) -> str:
    network = record.get("network", "root")
    if isinstance(network, list):
        return network[0] if network else "root"
    return network


def _short_name(aliases: dict) -> Optional[str]:
    return (
        aliases.get("internal_code")
        or aliases.get("matlab")
        or aliases.get("latex")
        or None
    )


def _token_value(record: dict) -> Optional[str]:
    tokens = record.get("tokens")
    if tokens is None:
        return None
    if isinstance(tokens, str):
        return tokens
    if isinstance(tokens, list) and tokens:
        return str(tokens[0])
    return None


def _as_unit_list(raw: Any) -> List[int]:
    if isinstance(raw, list) and len(raw) == 8:
        return [int(x) for x in raw]
    if isinstance(raw, list) and len(raw) > 8:
        return [int(x) for x in raw[:8]]
    return [0] * 8


def _parse_network_literal(value: Any) -> List[str]:
    """The TriG ``promo:network`` value is often a Python list literal string."""
    if value is None:
        return []
    text = str(value)
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except (ValueError, SyntaxError):
        pass
    return [text]


def _index_record_to_dict(key: str, rec: dict) -> dict:
    """Convert a legacy JSON index record to the frontend/backend contract shape."""
    iri = rec.get("IRI") or rec.get("global_ID") or key
    aliases = rec.get("aliases", {}) or {}
    return {
        "iri": iri,
        "label": rec.get("label", key),
        "network": _index_network(rec),
        "index_class": rec.get("type", "index"),
        "aliases": aliases,
        "token": _token_value(rec),
        "short_name": _short_name(aliases),
    }


def _trig_indices(trig_path: Path) -> Dict[str, dict]:
    """Read index definitions from the TriG var/expr file."""
    indices: Dict[str, dict] = {}
    try:
        ds = Dataset()
        ds.parse(str(trig_path), format="trig")
    except Exception:
        return indices

    for ctx in ds.graphs():
        for s in ctx.subjects(rdflib.RDF.type, PROMO["index"]):
            iri = str(s)
            internal_id = iri.split("#")[-1].split("/")[-1]
            label = str(ctx.value(s, PROMO["label"], default=""))
            if not label:
                label = internal_id
            networks = _parse_network_literal(
                ctx.value(s, PROMO["network"], default=None)
            )
            network = networks[0] if networks else "root"

            token_ref = ctx.value(s, PROMO["token"], default=None)
            token = str(token_ref) if token_ref else None

            indices[iri] = {
                "iri": iri,
                "label": label,
                "network": network,
                "index_class": "index",
                "aliases": {
                    "global_ID": internal_id,
                    "internal_code": label,
                    "matlab": label,
                    "latex": label,
                },
                "token": token,
                "short_name": label,
            }

    return indices


def load_index_records(data_dir: Optional[Path] = None) -> Dict[str, dict]:
    """Load index records from TriG (primary) and JSON (overlay)."""
    data_dir = data_dir or get_data_dir()

    # TriG is the authoritative source for index *definitions* in the old repo
    # because the JSON files in some projects omit them.
    indices: Dict[str, dict] = {}
    trig_path = _find_trig_file(data_dir)
    if trig_path:
        indices.update(_trig_indices(trig_path))

    # JSON overlays may carry more descriptive labels/aliases.  They are keyed
    # by internal ID (``I_3``) rather than IRI, so merge carefully.
    records = _load_v8_records(data_dir)
    for key, rec in records.items():
        if not isinstance(rec, dict):
            continue
        rec_type = rec.get("type", "")
        if rec_type not in ("index", "block_index"):
            continue
        idx = _index_record_to_dict(key, rec)
        # Prefer the JSON record unless the TriG record already has a rich IRI
        # but keep the JSON IRI/label/aliases.
        existing = indices.get(idx["iri"])
        if existing:
            existing.update(idx)
        else:
            indices[idx["iri"]] = idx

    return indices


def _variable_record_to_dict(
    key: str,
    rec: dict,
    index_by_internal_id: Dict[str, str],
) -> dict:
    """Convert a legacy variable record to the frontend/backend contract shape."""
    iri = rec.get("IRI") or key
    if not iri:
        return {}

    raw_index_structures = rec.get("index_structures", [])
    index_structures = [
        index_by_internal_id.get(idx_id, idx_id) for idx_id in raw_index_structures
    ]

    aliases = rec.get("aliases", {}) or {}
    units_list = _as_unit_list(rec.get("units"))

    return {
        "iri": iri,
        "label": rec.get("label", key),
        "network": rec.get("network", "root"),
        "type": rec.get("type") or "state",
        "units": units_list,
        "index_structures": index_structures,
        "doc": rec.get("doc", ""),
        "port_variable": rec.get("port_variable", False),
        "internal_id": aliases.get("global_ID") or key,
        "aliases": aliases,
        "tokens": rec.get("tokens") or [],
    }


def load_v8_context(data_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Return variables and indices parsed from the v8 JSON/TriG files.

    The returned dict has ``variables`` (dict keyed by IRI), ``indices`` (dict
    keyed by IRI), and ``index_by_internal_id`` (mapping from ``I_3`` style
    keys to index IRI) so callers can resolve index references.
    """
    data_dir = data_dir or get_data_dir()

    records = _load_v8_records(data_dir)
    indices = load_index_records(data_dir)

    # Map legacy I_* keys to the index IRI so variable.index_structures uses IRIs.
    index_by_internal_id: Dict[str, str] = {}
    for iri, idx in indices.items():
        internal_id = idx.get("aliases", {}).get("global_ID")
        if internal_id:
            index_by_internal_id[internal_id] = iri

    variables: Dict[str, dict] = {}
    for key, rec in records.items():
        if not isinstance(rec, dict):
            continue
        rec_type = rec.get("type", "")
        if rec_type in ("index", "block_index"):
            continue

        var = _variable_record_to_dict(key, rec, index_by_internal_id)
        if var:
            variables[var["iri"]] = var

    return {
        "variables": variables,
        "indices": indices,
        "index_by_internal_id": index_by_internal_id,
    }


def load_ontology_tree(data_dir: Optional[Path] = None) -> Dict[str, List[str]]:
    """Build a parent -> children network tree from ontology.json."""
    data_dir = data_dir or get_data_dir()
    path = data_dir / ONTOLOGY_FILE
    if not path.exists():
        return {}

    raw = _load_json(path)
    tree: Dict[str, dict] = raw.get("ontology_tree", {})
    network_tree: Dict[str, List[str]] = {}

    # First pass: add explicit children.
    for name, rec in tree.items():
        children = rec.get("children", [])
        if children:
            network_tree[name] = list(children)

    # Second pass: ensure every network appears, even leafs.
    for rec in tree.values():
        for child in rec.get("children", []):
            if child not in network_tree:
                network_tree[child] = []

    return network_tree


def load_context(data_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Load the full EquationEditor context from PROMO_DATA_DIR.

    Returns a dict with ``variables`` (IRI -> Variable), ``indices``
    (IRI -> Index), and ``network_tree`` (parent -> children).
    """
    ctx = load_v8_context(data_dir)
    ctx["network_tree"] = load_ontology_tree(data_dir)
    return ctx
