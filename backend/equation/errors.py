"""Exception hierarchy for the variable/equation framework.

Ported from ProMo13 ``variable_framework.py``. These are semantic-check
errors, distinct from ``parser.ParseError`` which covers syntax only.
"""

from __future__ import annotations

from typing import Any, List


class VarError(Exception):
    """Base error for variable/equation semantic problems."""

    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)

    def __str__(self) -> str:
        return ">>> %s" % self.msg


class AmbiguousVariableError(VarError):
    """An unqualified variable label matched more than one variable.

    Carries the symbol and a list of candidate descriptions so the UI can
    ask the user which one to use.
    """

    def __init__(self, msg: str, symbol: str, candidates: List[Any]):
        super().__init__(msg)
        self.symbol = symbol
        self.candidates = candidates


class TrackingError(VarError):
    """Error while tracking dependencies through the var/expr graph."""


class UnitError(VarError):
    """Incompatible or unexpected units."""

    def __init__(self, msg: str, pre: Any = "", post: Any = ""):
        super().__init__("%s\n -- pre: %s,\n -- post: %s" % (msg, pre, post))


class IndexStructureError(VarError):
    """Incompatible or unexpected index structures."""


class MatrixCompilationError(VarError):
    """Error while compiling an indexed expression to matrix form."""


class EquationDeleteError(VarError):
    """An equation cannot be deleted (e.g. it is the variable's only one)."""
