"""Tests for ``backend/equation/units.py``."""

from .errors import UnitError
from .units import Units


def test_default_is_dimensionless():
    assert Units().is_dimensionless()


def test_from_list_roundtrip():
    exponents = [1, 2, 3, 4, 5, 6, 7, 8]
    u = Units.from_list(exponents)
    assert u.as_list() == exponents
    assert Units.from_list(u.as_list()) == u


def test_as_dict():
    u = Units(time=1, mass=2)
    assert u.as_dict() == {
        "time": 1,
        "length": 0,
        "amount": 0,
        "mass": 2,
        "temperature": 0,
        "current": 0,
        "light": 0,
        "nil": 0,
    }


def test_temperature_is_not_dimensionless():
    """Regression: the ProMo13 ``isZero`` skipped ``temperature``."""
    u = Units(temperature=1)
    assert not u.is_dimensionless()


def test_nil_is_not_dimensionless():
    """The ``nil`` field must also be checked."""
    u = Units(nil=1)
    assert not u.is_dimensionless()


def test_add_compatible():
    a = Units(mass=1, length=2)
    b = Units(mass=1, length=2)
    assert a + b == a


def test_add_incompatible_raises():
    try:
        Units(mass=1) + Units(length=1)
    except UnitError:
        return
    raise AssertionError("expected UnitError")


def test_mul_adds_exponents():
    a = Units(mass=1, length=1)
    b = Units(mass=1, time=-2)
    assert a * b == Units(mass=2, length=1, time=-2)


def test_sub_subtracts_exponents():
    a = Units(mass=1, length=2)
    b = Units(length=1)
    assert a - b == Units(mass=1, length=1)


def test_inverse_negates_exponents():
    u = Units(mass=1, length=2)
    assert u.inverse() == Units(mass=-1, length=-2)


def test_scale():
    u = Units(mass=1, length=2)
    assert u.scale(3) == Units(mass=3, length=6)


def test_pretty():
    assert Units().pretty() == "1"
    assert Units(mass=1, length=1, time=-2).pretty() == "kg m s^-2"
    assert Units(temperature=2).pretty() == "K^2"


def test_str():
    assert str(Units(mass=1)) == str([0, 0, 0, 1, 0, 0, 0, 0])


if __name__ == "__main__":
    import sys

    for name, fn in globals().items():
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:
                print(f"FAIL {name}: {e}")
                sys.exit(1)
    print("All tests passed")
