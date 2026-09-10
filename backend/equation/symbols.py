"""Language symbol table for the ProMo expression parser.

The symbol table is the bridge between the published language vocabulary
(`promolg:`) and the parser. In the long run it is loaded from the RDF
language graph; for bootstrapping we keep a default Python definition here.

Adding a new operator or function:

- **New unary function** (`sin`, `myFn`): add its surface name to ``ufuncs``.
  It is parsed as ``UFunc(name, arg)``.
- **New multi-argument / user function** (`myFn(a, b)`): add its surface name
  to ``functions``. It is parsed as ``Call(Var(name), (args...))``.
- **New keyword-driven construct** (e.g. a new aggregate): add to ``keywords``
  and extend ``_factor`` in ``parser.py`` with its grammar rule.
- **New infix operator at an existing precedence level** (``+``, ``-`` level 1;
  ``*``, ``:``, ``.`` level 2; ``^`` level 3): add it to ``infix`` with the
  matching ``precedence`` and ``right_assoc`` flag and add the corresponding
  AST factory in ``_make_infix`` in ``parser.py``.
- **New infix precedence level**: add the precedence to ``infix`` and add a
  new grammar rule / Pratt-style loop. At that point the recursive-descent
  parser should probably be replaced by a precedence-climbing (Pratt) parser.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Set


@dataclass(frozen=True)
class InfixEntry:
    """One infix operator entry."""
    symbol: str
    precedence: int  # higher = tighter binding; 1=sum, 2=product, 3=power
    right_assoc: bool = False
    # The factory key is used by parser._make_infix to build the right node.
    factory: str = ""


@dataclass
class SymbolTable:
    """A set of language symbols used by the lexer and parser."""

    # Keywords that introduce special syntax constructs.
    keywords: Set[str] = field(default_factory=set)

    # Unary functions: f(x)
    ufuncs: Set[str] = field(default_factory=set)

    # Two-argument min/max — kept distinct because they map to a dedicated
    # AST node with its own semantics.
    maxmin: Set[str] = field(default_factory=set)

    # Multi-argument / user-defined functions: f(a, b, ...)
    functions: Set[str] = field(default_factory=set)

    # Infix operators by surface symbol.
    infix: Dict[str, InfixEntry] = field(default_factory=dict)

    # Unit behaviour per ufunc: "retain" | "none" | "inverse" | "loose".
    # Semantic property of the symbol — used by the checker, not the parser.
    ufunc_units: Dict[str, str] = field(default_factory=dict)

    def ufunc_unit_rule(self, name: str) -> Optional[str]:
        return self.ufunc_units.get(name)

    def classify_word(self, word: str) -> str:
        """Return the token kind for a word."""
        if word in self.ufuncs:
            return "ufunc"
        if word in self.maxmin:
            return "maxmin"
        if word in self.functions:
            return "function"
        if word == "in":
            return "in"
        if word in self.keywords:
            return "kw"
        return "var"

    def is_function(self, word: str) -> bool:
        return word in self.ufuncs or word in self.functions

    def infix_info(self, symbol: str) -> Optional[InfixEntry]:
        return self.infix.get(symbol)


# -----------------------------------------------------------------------------
# Default language — matches the ProMo13 TPG grammar.
# -----------------------------------------------------------------------------

DEFAULT_TABLE = SymbolTable(
    keywords={
        "Instantiate",
        "Integral",
        "Product",
        "Root",
        "TotalDiff",
        "ParDiff",
        "reduceSum",
    },
    ufuncs={
        # retain
        "abs", "neg", "diffSpace", "left", "right",
        # none
        "exp", "log", "ln", "sqrt", "sin", "cos", "tan",
        "asin", "acos", "atan",
        # inverse
        "inv",
        # loose
        "sign",
    },
    maxmin={
        "max",
        "min",
    },
    ufunc_units={
        # retain — abs, neg, diffSpace, left, right
        **{f: "retain" for f in
           ("abs", "neg", "diffSpace", "left", "right")},
        # none — dimensionless argument required
        **{f: "none" for f in
           ("exp", "log", "ln", "sqrt", "sin", "cos", "tan",
            "asin", "acos", "atan")},
        # inverse
        "inv": "inverse",
        # loose
        "sign": "loose",
    },
    functions=set(),
    infix={
        "+": InfixEntry("+", precedence=1, right_assoc=False, factory="add"),
        "-": InfixEntry("-", precedence=1, right_assoc=False, factory="add"),
        ":": InfixEntry(":", precedence=2, right_assoc=False, factory="expand"),
        ".": InfixEntry(".", precedence=2, right_assoc=False, factory="hadamard"),
        "*": InfixEntry("*", precedence=2, right_assoc=False, factory="reduce"),
        "^": InfixEntry("^", precedence=3, right_assoc=True, factory="power"),
    },
)
