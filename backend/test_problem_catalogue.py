"""Guard: every ``Problem`` kind emitted by the backend has a catalogue
section.

``docs/problem-catalogue.md`` is the Track 2 teaching surface — its
charter is one ``### `kind``` section per emitted ``Problem.kind``,
kept character-identical to the code.  This test fails when code
starts emitting a kind the catalogue doesn't document.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
CATALOGUE = ROOT / "docs" / "problem-catalogue.md"


def _emitted_kinds():
    """Collect ``kind=`` args from ``Problem(...)`` calls.

    Returns ``(constants, patterns)``: plain string literals, plus
    regexes derived from f-string kinds such as
    ``f"{pb.status}-port"`` → ``.*-port``.
    """
    constants = set()
    patterns = []
    for py in sorted(BACKEND.rglob("*.py")):
        if py.name.startswith("test_"):
            continue
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.id if isinstance(func, ast.Name)
                else func.attr if isinstance(func, ast.Attribute)
                else None
            )
            if name != "Problem":
                continue
            for kw in node.keywords:
                if kw.arg != "kind":
                    continue
                if isinstance(kw.value, ast.Constant):
                    constants.add(str(kw.value.value))
                elif isinstance(kw.value, ast.JoinedStr):
                    parts = [
                        re.escape(v.value)
                        if isinstance(v, ast.Constant) else ".*"
                        for v in kw.value.values
                    ]
                    patterns.append(re.compile("^" + "".join(parts) + "$"))
    return constants, patterns


def _documented_kinds() -> set:
    text = CATALOGUE.read_text()
    return set(re.findall(r"^###\s+`([a-z][a-z0-9-]*)`", text, re.M))


def _is_emitted(kind: str, constants: set, patterns: list) -> bool:
    return kind in constants or any(p.match(kind) for p in patterns)


def test_problem_catalogue_coverage():
    constants, _patterns = _emitted_kinds()
    missing = sorted(k for k in constants if k not in _documented_kinds())
    assert not missing, (
        "backend emits Problem kinds with no catalogue section "
        "(add a ### `kind` entry to docs/problem-catalogue.md): "
        + ", ".join(missing)
    )


def test_problem_catalogue_no_ghost_kinds():
    """Every catalogued `### kind` is still emittable — stale sections
    teach users about problems that can't happen.  A documented kind
    matches if it's a literal kind= or fits an emitted f-string
    pattern (e.g. ``{status}-port``)."""
    constants, patterns = _emitted_kinds()
    ghost = sorted(
        k for k in _documented_kinds()
        if not _is_emitted(k, constants, patterns)
    )
    assert not ghost, (
        "catalogue documents kinds no longer emitted by the backend: "
        + ", ".join(ghost)
    )
