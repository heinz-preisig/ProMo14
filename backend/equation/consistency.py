from __future__ import annotations

import hashlib
import json
from typing import Callable

from .checker import check
from .compile_space import CompileSpace
from .errors import VarError
from .parser import ParseError, parse
from .syntax import Var


def build_report(ctx, graph_iri: str | None, owners: Callable) -> dict:
    variables = ctx.variables()
    rows = []
    for v in sorted(variables.values(), key=lambda v: v.iri):
        for key, eq in sorted(getattr(v, "equations", {}).items()):
            row = {
                "variable": v.iri, "label": v.label, "equation": eq["iri"],
                "equation_id": key, "network": v.network,
                "graphs": owners(eq["iri"], False),
                "rhs": eq.get("rhs", ""), "status": "consistent",
                "declared": {"units": v.units.as_list(), "indices": v.index_structures},
                "derived": None, "operands": [], "findings": [],
            }
            space = CompileSpace(
                variables, ctx.indices(), v.network, eq.get("network") or v.network,
                accessible_networks=ctx.accessible_networks(eq.get("network") or v.network),
                network_tree=ctx.tree(),
            )
            try:
                checked = check(parse(row["rhs"]), space, Var(v.iri))
            except (ParseError, VarError) as exc:
                row["status"] = "error"
                row["findings"].append({"code": type(exc).__name__, "message": str(exc)})
                rows.append(row)
                continue
            row["derived"] = {"units": checked.units.as_list(), "indices": checked.indices}
            for iri in sorted(checked.incidence):
                operand = variables.get(iri)
                if operand is not None:
                    row["operands"].append({
                        "iri": iri, "label": operand.label,
                        "units": operand.units.as_list(), "indices": operand.index_structures,
                        "graphs": owners(iri, True),
                    })
            for field in ("units", "indices"):
                declared, derived = row["declared"][field], row["derived"][field]
                differs = declared != derived if field == "units" else set(declared) != set(derived)
                if differs:
                    row["findings"].append({
                        "code": field + "_mismatch",
                        "message": "Declared %s differ from the expression result" % field,
                    })
            if row["findings"]:
                row["status"] = "error"
            rows.append(row)
    report = {"graph": graph_iri, "equations": rows,
              "summary": {s: sum(r["status"] == s for r in rows)
                          for s in ("error", "consistent")}}
    report["revision"] = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    return report
