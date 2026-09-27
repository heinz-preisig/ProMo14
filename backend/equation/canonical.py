from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Union

from backend.core.vocab import PROMOLG

from .checker import Checked
from .compile_space import CompileSpace
from .errors import VarError
from .syntax import (
    Add, Call, Expand, Group, IndexPreservingProduct, Instantiate, Integral,
    MaxMin, ParDiff, Power, Product, Reduce, ReduceSum, Root, TotalDiff, UFunc,
    Var,
)


@dataclass(frozen=True)
class VariableReference:
    iri: str


@dataclass(frozen=True)
class IndexReference:
    iri: str


@dataclass(frozen=True)
class Expression:
    operation_iri: str
    arguments: Tuple["Argument", ...]


Argument = Union[Expression, VariableReference, IndexReference]


def _operation(name: str) -> str:
    return str(PROMOLG[name])


ADD = _operation("Add")
SUBTRACT = _operation("Subtract")
POWER = _operation("Power")
EXPAND_PRODUCT = _operation("ExpandProduct")
INDEX_PRESERVING_PRODUCT = _operation("IndexPreservingProduct")
REDUCE_PRODUCT = _operation("ReduceProduct")
PRODUCT_OVER_INDEX = _operation("ProductOverIndex")
SUM_OVER_INDEX = _operation("SumOverIndex")
DEFINITE_INTEGRAL = _operation("DefiniteIntegral")
TOTAL_DERIVATIVE = _operation("TotalDerivative")
PARTIAL_DERIVATIVE = _operation("PartialDerivative")
SOLVE_ROOT = _operation("SolveRoot")
INSTANTIATE = _operation("Instantiate")


def from_checked(checked: Checked, space: CompileSpace) -> Argument:
    node = checked.node
    children = checked.children

    if isinstance(node, Var):
        return VariableReference(space.resolve(node.name).variable.iri)
    if isinstance(node, Group):
        return from_checked(children[0], space)
    if isinstance(node, Add):
        operation = ADD if node.op == "+" else SUBTRACT
        return Expression(operation, _children(children, space))
    if isinstance(node, Expand):
        return Expression(EXPAND_PRODUCT, _children(children, space))
    if isinstance(node, IndexPreservingProduct):
        return Expression(INDEX_PRESERVING_PRODUCT, _children(children, space))
    if isinstance(node, Reduce):
        return Expression(REDUCE_PRODUCT, _children(children, space))
    if isinstance(node, Power):
        return Expression(POWER, _children(children, space))
    if isinstance(node, Instantiate):
        return Expression(INSTANTIATE, _children(children, space))
    if isinstance(node, Integral):
        return Expression(DEFINITE_INTEGRAL, _children(children, space))
    if isinstance(node, Product):
        return Expression(
            PRODUCT_OVER_INDEX,
            (from_checked(children[0], space), _index(node.index, space)),
        )
    if isinstance(node, ReduceSum):
        return Expression(
            SUM_OVER_INDEX,
            (from_checked(children[0], space), _index(node.index, space)),
        )
    if isinstance(node, Root):
        return Expression(SOLVE_ROOT, _children(children, space))
    if isinstance(node, TotalDiff):
        return Expression(TOTAL_DERIVATIVE, _children(children, space))
    if isinstance(node, ParDiff):
        return Expression(PARTIAL_DERIVATIVE, _children(children, space))
    if isinstance(node, MaxMin):
        return Expression(_operation(node.which), _children(children, space))
    if isinstance(node, UFunc):
        return Expression(_operation(node.name), _children(children, space))
    if isinstance(node, Call):
        raise VarError("canonical expression requires an IRI-bound function")
    raise VarError("canonical expression: unsupported node %s" % type(node).__name__)


def to_source(argument: Argument, space: CompileSpace) -> str:
    if isinstance(argument, VariableReference):
        return _variable_source(argument, space)
    if isinstance(argument, IndexReference):
        return space.index_alias(argument.iri)

    operation = argument.operation_iri
    args = argument.arguments
    if operation in (ADD, SUBTRACT, POWER, EXPAND_PRODUCT,
                     INDEX_PRESERVING_PRODUCT):
        symbols = {
            ADD: "+",
            SUBTRACT: "-",
            POWER: "^",
            EXPAND_PRODUCT: ":",
            INDEX_PRESERVING_PRODUCT: ".",
        }
        _arity(argument, 2)
        return "( %s %s %s )" % (
            to_source(args[0], space), symbols[operation],
            to_source(args[1], space),
        )
    if operation == REDUCE_PRODUCT:
        _arity(argument, 2)
        return "( %s * %s )" % (
            to_source(args[0], space), to_source(args[1], space))
    if operation == PRODUCT_OVER_INDEX:
        _arity(argument, 2)
        return "Product( %s, %s )" % (
            to_source(args[0], space), to_source(args[1], space))
    if operation == SUM_OVER_INDEX:
        _arity(argument, 2)
        return "reduceSum( %s, %s )" % (
            to_source(args[0], space), to_source(args[1], space))
    if operation == DEFINITE_INTEGRAL:
        _arity(argument, 4)
        return "Integral( %s :: %s in [ %s, %s ] )" % tuple(
            to_source(value, space) for value in args)
    if operation in (TOTAL_DERIVATIVE, PARTIAL_DERIVATIVE):
        _arity(argument, 2)
        name = "TotalDiff" if operation == TOTAL_DERIVATIVE else "ParDiff"
        return "%s( %s, %s )" % (
            name, to_source(args[0], space), to_source(args[1], space))
    if operation == SOLVE_ROOT:
        _arity(argument, 1)
        return "Root( %s )" % to_source(args[0], space)
    if operation == INSTANTIATE:
        _arity(argument, 1)
        return "Instantiate( %s )" % to_source(args[0], space)

    name = _operation_name(operation)
    if name in space.table.ufuncs:
        _arity(argument, 1)
        return "%s( %s )" % (name, to_source(args[0], space))
    if name in space.table.maxmin:
        _arity(argument, 2)
        return "%s( %s, %s )" % (
            name, to_source(args[0], space), to_source(args[1], space))
    raise VarError("canonical expression: unknown operation IRI %s" % operation)


def _children(children: list[Checked], space: CompileSpace) -> Tuple[Argument, ...]:
    return tuple(from_checked(child, space) for child in children)


def _index(node: Var, space: CompileSpace) -> IndexReference:
    iri = space.get_index(node.name)
    if iri is None:
        raise VarError("no such index %s defined" % node.name)
    return IndexReference(iri)


def _variable_source(reference: VariableReference, space: CompileSpace) -> str:
    variable = space.variables.get(reference.iri)
    if variable is None:
        raise VarError("canonical expression: unknown variable IRI %s" % reference.iri)
    if variable.network == space.expression_definition_network:
        return variable.label
    return "%s!%s" % (variable.network, variable.label)


def _operation_name(iri: str) -> str:
    prefix = str(PROMOLG)
    if not iri.startswith(prefix):
        raise VarError("canonical expression: operation outside language namespace %s" % iri)
    return iri[len(prefix):]


def _arity(expression: Expression, expected: int) -> None:
    if len(expression.arguments) != expected:
        raise VarError(
            "%s requires %d arguments" % (
                _operation_name(expression.operation_iri), expected,
            )
        )
