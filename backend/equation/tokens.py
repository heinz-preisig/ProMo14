"""Token algebra for the ProMo expression checker (§23/§24).

A token vector is a sparse exponent map ``{token IRI: exponent}`` over the
ontology's token basis — the same algebra as ``units.py`` but on the
*network* basis (mass, component_mass, energy, entropy, momentum, time, …)
instead of SI dimensions.  It propagates through expressions exactly like
units:

- ``a + b`` is a *compatibility check*: equal vectors pass, unequal are a
  semantic warning (the result is untracked downstream).
- ``a * b`` adds exponents (token of a product).
- ``a - b`` subtracts exponents (differentials / quotients).
- ``a.inverse()`` negates exponents (``inv`` ufunc).
- ``a.scale(k)`` multiplies every exponent by ``k``.

Two levels of declaration on a variable:

- ``promo:carriesToken`` — *network membership*; definitional, used for
  port licensing (``instantiate/satisfy.py``).  Never derived.
- ``promo:tokenVector`` — *algebraic signature*; the checker's leaf value.
  The consistency rule linking them: every declared ``carriesToken`` must
  appear with a **nonzero exponent** in the ``tokenVector``.  Extensive
  ports carry their token at ``+1``; intensive ports (e.g. concentration
  ``c = n/V``) carry it at ``−1`` — the sign marks the conjugate-density
  side.  For an effort/flow port pair the conjugacy invariant is
  ``effort * flow = energy·time⁻¹`` (power).

``None`` means *untracked* — the variable has no algebraic signature (flags,
times, non-physical vars).  Any operation on an untracked operand yields
untracked; the algebra never blocks checking.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


def token_frag(iri: str) -> str:
    """Surface name of a token IRI (``…#token_energy`` → ``energy``)."""
    frag = iri.split("#")[-1].split("/")[-1]
    return frag[len("token_"):] if frag.startswith("token_") else frag


@dataclass(frozen=True)
class TokenVec:
    """Immutable sparse exponent vector over token IRIs.

    ``entries`` is a sorted tuple of ``(token_iri, exponent)`` pairs with
    non-zero exponents only — canonical form, so ``==`` is semantic equality.
    """

    entries: Tuple[Tuple[str, int], ...] = ()

    @classmethod
    def from_dict(cls, exponents: Dict[str, int]) -> "TokenVec":
        entries = tuple(sorted(
            (k, v) for k, v in exponents.items() if v != 0
        ))
        return cls(entries)

    @classmethod
    def single(cls, token_iri: str) -> "TokenVec":
        return cls(((token_iri, 1),))

    @classmethod
    def from_json(cls, text: str) -> Optional["TokenVec"]:
        """Parse a ``promo:tokenVector`` literal.

        Accepted forms: ``{"<token-iri-or-fragment>": exponent, …}``.
        Fragment keys are tolerated — they are stored as given; consumers
        compare against ``carriesToken`` IRIs via :func:`token_frag`.
        """
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("tokenVector must be a JSON object")
        return cls.from_dict({str(k): int(v) for k, v in parsed.items()})

    def as_dict(self) -> Dict[str, int]:
        return dict(self.entries)

    def is_empty(self) -> bool:
        return not self.entries

    # -- arithmetic ---------------------------------------------------------

    def _combine(self, other: "TokenVec", sign: int) -> "TokenVec":
        out: Dict[str, int] = dict(self.entries)
        for k, v in other.entries:
            out[k] = out.get(k, 0) + sign * v
        return TokenVec.from_dict(out)

    def __mul__(self, other: "TokenVec") -> "TokenVec":
        """Token of a product: exponent-wise addition."""
        return self._combine(other, +1)

    def __sub__(self, other: "TokenVec") -> "TokenVec":
        """Token of a quotient / differential: exponent-wise subtraction."""
        return self._combine(other, -1)

    def compatible(self, other: "TokenVec") -> bool:
        """Addition-compatibility: tokens must be identical (like units)."""
        return self == other

    def inverse(self) -> "TokenVec":
        return TokenVec.from_dict({k: -v for k, v in self.entries})

    def scale(self, factor: int) -> "TokenVec":
        return TokenVec.from_dict({k: factor * v for k, v in self.entries})

    def square_root(self) -> Optional["TokenVec"]:
        """Halved exponents; ``None`` when any exponent is odd."""
        if any(v % 2 for _, v in self.entries):
            return None
        return self.scale(0) if not self.entries else TokenVec.from_dict(
            {k: v // 2 for k, v in self.entries}
        )

    # -- semantics ----------------------------------------------------------

    def carries(self, token_iri: str) -> bool:
        """True when ``token_iri`` has a nonzero exponent in the vector —
        the membership rule linking ``carriesToken`` to ``tokenVector``.
        Extensive quantities carry their token at ``+1``; intensive ones
        (conjugate densities like concentration) at ``−1``.  Comparison is
        by fragment, so IRI- and fragment-keyed vectors interoperate."""
        frag = token_frag(token_iri)
        return any(
            v != 0 and token_frag(k) == frag for k, v in self.entries
        )

    def pretty(self) -> str:
        parts = [
            token_frag(k) if v == 1 else "%s^%s" % (token_frag(k), v)
            for k, v in self.entries
        ]
        return " ".join(parts) if parts else "1"

    def __str__(self) -> str:
        return self.pretty()


#: Combinators over ``Optional[TokenVec]`` — ``None`` (untracked) absorbs.
def tmul(a: Optional[TokenVec], b: Optional[TokenVec]) -> Optional[TokenVec]:
    return a * b if (a is not None and b is not None) else None


def tsub(a: Optional[TokenVec], b: Optional[TokenVec]) -> Optional[TokenVec]:
    return a - b if (a is not None and b is not None) else None


def tadd(a: Optional[TokenVec], b: Optional[TokenVec],
         warn=None) -> Optional[TokenVec]:
    """Addition-compatibility: both tracked → must be equal (else ``warn``
    is called and the result is untracked); either untracked → untracked."""
    if a is None or b is None:
        return None
    if a.compatible(b):
        return a
    if warn:
        warn("token mismatch in sum: %s vs %s" % (a.pretty(), b.pretty()))
    return None
