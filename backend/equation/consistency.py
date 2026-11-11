from __future__ import annotations

import hashlib
import json
from typing import Callable

from .canonical import from_checked, to_source
from .checker import _leaf_tokens, check
from .compile_space import CompileSpace
from .errors import VarError
from .parser import ParseError, parse
from .syntax import Add, MaxMin, Var
from .tokens import TokenVec


def build_report(ctx, graph_iri: str | None, owners: Callable, advisories: Callable) -> dict:
    variables = ctx.variables()
    rows = []
    for v in sorted(variables.values(), key=lambda v: v.iri):
        for key, eq in sorted(getattr(v, "equations", {}).items()):
            graphs = owners(eq["iri"], False)
            row = {
                "variable": v.iri, "label": v.label, "equation": eq["iri"],
                "equation_id": key, "network": v.network, "graphs": graphs,
                "rhs": eq.get("rhs", ""), "status": "consistent",
                "declared": {"units": v.units.as_list(),
                             "indices": v.index_structures,
                             "tokens": None if v.token_vector is None else
                             TokenVec.from_dict(v.token_vector).as_dict()},
                "derived": None, "operands": [], "conflicts": [], "findings": [],
            }
            space = CompileSpace(
                variables, ctx.indices(), v.network,
                eq.get("network") or v.network,
                accessible_networks=ctx.accessible_networks(eq.get("network") or v.network),
                network_tree=ctx.tree(),
            )
            try:
                checked = check(parse(row["rhs"]), space, Var(v.iri))
            except (ParseError, VarError) as exc:
                row["status"] = "error"
                row["findings"].append({"code": type(exc).__name__,
                                        "message": str(exc), "fixes": []})
                rows.append(row)
                continue
            row["derived"] = {
                "units": checked.units.as_list(), "indices": checked.indices,
                "tokens": None if checked.tokens is None else checked.tokens.as_dict(),
            }
            def conflicts(node):
                if isinstance(node.node, (Add, MaxMin)):
                    left, right = node.children
                    if left.tokens is not None and right.tokens is not None and left.tokens != right.tokens:
                        row["conflicts"].append([
                            {"expression": to_source(from_checked(child, space), space),
                             "tokens": child.tokens.as_dict()}
                            for child in (left, right)
                        ])
                for child in node.children:
                    conflicts(child)

            conflicts(checked)
            for iri in sorted(checked.incidence):
                operand = variables.get(iri)
                if operand is None:
                    continue
                effective = _leaf_tokens(operand)
                row["operands"].append({
                    "iri": iri, "label": operand.label,
                    "tokens": None if effective is None else effective.as_dict(),
                    "graphs": owners(iri, True),
                })
            for field in ("units", "indices"):
                declared, derived = row["declared"][field], row["derived"][field]
                differs = declared != derived if field == "units" else set(declared) != set(derived)
                if differs:
                    row["findings"].append({
                        "code": field + "_mismatch",
                        "message": "Declared %s differ from the expression result" % field,
                        "fixes": [],
                    })
            _, _, _, items = advisories(checked, space, v.iri)
            for item in items:
                item["message"] = item["message"].replace(v.iri, v.label)
                for fix in item.get("fixes", []):
                    fix["label"] = fix["label"].replace(v.iri, v.label)
            row["findings"].extend(items)
            if (checked.tokens is not None and v.token_vector is not None
                    and checked.tokens != TokenVec.from_dict(v.token_vector)
                    and not any(a["code"] == "token_signature_mismatch" for a in items)):
                row["findings"].append({
                    "code": "token_signature_mismatch",
                    "message": "Derived token signature differs from the declared signature",
                    "fixes": [{"action": "adopt_derived", "variable": v.iri,
                               "token_vector": checked.tokens.as_dict(),
                               "label": "Adopt derived signature for '%s'" % v.label}],
                })
            if checked.tokens is not None and _leaf_tokens(v) is None:
                row["findings"].append({
                    "code": "missing_signature",
                    "message": "The expression is tracked but the LHS declaration is untracked",
                    "fixes": [{"action": "adopt_derived", "variable": v.iri,
                               "token_vector": checked.tokens.as_dict(),
                               "label": "Declare the derived signature for '%s'" % v.label}],
                })
            for item in row["findings"]:
                for fix in item.get("fixes", []):
                    target = variables.get(fix.get("variable"))
                    target_graphs = owners(fix.get("variable"), True) if target else []
                    reason = None
                    if not target or not target.tokens:
                        reason = "Declare membership explicitly in the variable editor first"
                    elif graph_iri not in target_graphs:
                        reason = "Open the owning artefact to edit this declaration"
                    elif getattr(target, "frozen", False):
                        reason = "Unfreeze the variable before editing"
                    elif any(owners(e["iri"], False, frozen=True)
                             for e in getattr(target, "equations", {}).values()):
                        reason = "A defining equation is frozen"
                    if owners(graph_iri, False, frozen=True):
                        reason = "This artefact is frozen"
                    fix["blocked"] = reason
            structural = any(f["code"] in ("units_mismatch", "indices_mismatch")
                             for f in row["findings"])
            row["status"] = ("error" if structural else "advisory" if row["findings"]
                             else "untracked" if checked.tokens is None else "consistent")
            if checked.tokens is None:
                row["findings"].append({
                    "code": "tokens_untracked",
                    "message": "Token consistency is not established. Inspect untracked operands or unsupported operations.",
                    "fixes": [],
                })
            rows.append(row)
    for row in rows:
        for finding in row["findings"]:
            for fix in finding.get("fixes", []):
                if fix.get("blocked"):
                    continue
                replacement = {} if fix["action"] == "clear_signature" else fix.get("token_vector")
                alternatives = [r for r in rows if r["variable"] == fix.get("variable")]
                if len(alternatives) > 1 and any(
                        r["derived"] is None or r["derived"]["tokens"] != replacement
                        for r in alternatives):
                    fix["blocked"] = "Alternative definitions do not agree on this signature — review them first"
    report = {"graph": graph_iri, "equations": rows,
              "summary": {s: sum(r["status"] == s for r in rows)
                          for s in ("error", "advisory", "untracked", "consistent")}}
    report["revision"] = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    return report
