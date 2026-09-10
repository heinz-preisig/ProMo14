"""SI unit vector for the ProMo expression checker.

Ported from ProMo13 ``variable_framework.Units``. A unit is an 8-exponent
vector ``(time, length, amount, mass, temperature, current, light, nil)`` —
the same layout as the ``units`` field in ``variables_v8.json`` records, so
stored data round-trips unchanged.

Semantics (unchanged from ProMo13):

- ``a + b`` is a *compatibility check*: equal units return a unit, unequal
  units raise :class:`UnitError`. Used by ``Add``/``MaxMin``.
- ``a * b`` adds exponents (unit of a product). Used by the product
  operators and ``Integral``.
- ``a - b`` subtracts exponents (unit of a quotient). Used by the
  differential operators.
- ``a.inverse()`` negates exponents. Used by the ``inv`` unitary function.
- ``a.scale(k)`` multiplies every exponent by ``k``.

Fixes versus the ProMo13 original:

- ``is_dimensionless`` now checks **all eight** exponents — the old
  ``isZero`` skipped ``temperature`` and ``nil``, so a pure-temperature unit
  was wrongly reported as dimensionless.
- Instances are immutable (``frozen`` dataclass); the old class was a
  mutable bag of attributes.
- LaTeX pretty-printing is dropped — rendering belongs to ``codegen/``.
  ``pretty()`` produces a plain-text form for error messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .errors import UnitError

#: Field order — matches the ``ALL`` vector layout of ProMo13 and the
#: ``units`` field of ``variables_v8.json`` records.
FIELDS = (
    "time", "length", "amount", "mass",
    "temperature", "current", "light", "nil",
)

#: Display order for ``pretty()`` — the conventional SI order used by the
#: ProMo13 ``prettyPrint`` (kg, m, mol, K, A, cd, s, nil).
_DISPLAY_ORDER = (
    "mass", "length", "amount", "temperature",
    "current", "light", "time", "nil",
)

#: SI base-unit symbols per field, for ``pretty()``.
_SYMBOLS = {
    "time": "s",
    "length": "m",
    "amount": "mol",
    "mass": "kg",
    "temperature": "K",
    "current": "A",
    "light": "cd",
    "nil": "nil",
}


@dataclass(frozen=True)
class Units:
    """Immutable 8-exponent SI unit vector."""

    time: int = 0
    length: int = 0
    amount: int = 0
    mass: int = 0
    temperature: int = 0
    current: int = 0
    light: int = 0
    nil: int = 0

    @classmethod
    def from_list(cls, exponents: List[int]) -> "Units":
        """Build from an 8-element exponent list (the old ``ALL=`` form)."""
        if len(exponents) != len(FIELDS):
            raise ValueError(
                "Units vector must have %d exponents, got %d"
                % (len(FIELDS), len(exponents))
            )
        return cls(**dict(zip(FIELDS, exponents)))

    def as_list(self) -> List[int]:
        return [getattr(self, f) for f in FIELDS]

    def as_dict(self) -> Dict[str, int]:
        return {f: getattr(self, f) for f in FIELDS}

    def is_dimensionless(self) -> bool:
        """True iff every exponent is zero.

        Fixes the ProMo13 ``isZero`` bug, which skipped ``temperature`` and
        ``nil``.
        """
        return all(getattr(self, f) == 0 for f in FIELDS)

    # -- arithmetic ---------------------------------------------------------

    def __add__(self, other: "Units") -> "Units":
        """Compatibility check: equal units pass, unequal raise UnitError."""
        if not isinstance(other, Units):
            return NotImplemented
        if self == other:
            return self
        raise UnitError(
            "add - incompatible units", self.pretty(), other.pretty()
        )

    def __mul__(self, other: "Units") -> "Units":
        """Unit of a product: exponent-wise addition."""
        if not isinstance(other, Units):
            return NotImplemented
        return Units.from_list(
            [a + b for a, b in zip(self.as_list(), other.as_list())]
        )

    def __sub__(self, other: "Units") -> "Units":
        """Unit of a quotient: exponent-wise subtraction."""
        if not isinstance(other, Units):
            return NotImplemented
        return Units.from_list(
            [a - b for a, b in zip(self.as_list(), other.as_list())]
        )

    def inverse(self) -> "Units":
        """Unit of the reciprocal: negated exponents (``inv`` ufunc)."""
        return Units.from_list([-e for e in self.as_list()])

    def scale(self, factor: int) -> "Units":
        """Multiply every exponent by ``factor`` (old ``product``)."""
        return Units.from_list([factor * e for e in self.as_list()])

    # -- display ------------------------------------------------------------

    def pretty(self) -> str:
        """Plain-text unit string for error messages, e.g. ``kg m s^-2``."""
        parts = []
        for f in _DISPLAY_ORDER:
            e = getattr(self, f)
            if e == 0:
                continue
            parts.append(_SYMBOLS[f] if e == 1 else "%s^%s" % (_SYMBOLS[f], e))
        return " ".join(parts) if parts else "1"

    def __str__(self) -> str:
        return str(self.as_list())


#: The dimensionless unit — handy constant for checks.
DIMENSIONLESS = Units()
