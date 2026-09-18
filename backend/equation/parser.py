"""Table-driven parser for the ProMo expression language.

Replaces the TPG-based parser from ProMo13. Produces a plain ``syntax.Node``
tree. Semantic checks (units, index structures, variable resolution) are a
separate graph-dependent pass.

The symbol set (keywords, functions, infix operators with precedence and
associativity) comes from a ``symbols.SymbolTable`` — in the long run loaded
from the published ``promolg:`` language graph. Infix parsing uses
precedence climbing, so new infix operators at existing precedence levels
need only a table entry plus a factory case in ``_make_infix``.

Grammar (revised with the POWER precedence fix):

    Expression -> 'Instantiate' '(' Expression ',' Expression ')'
                | Factor ( INFIX Factor )*        # precedence-climbed
    Factor     -> '(' Expression ')'
                | 'Integral' '(' Expression '::' Identifier 'in'
                      '[' Identifier ',' Identifier ']' ')'
                | 'Product'  '(' Expression ',' Index ')'
                | 'Root'     '(' Expression ')'
                | MaxMin     '(' Expression ',' Expression ')'
                | 'TotalDiff' '(' Expression ',' Expression ')'
                | 'ParDiff'  '(' Expression ',' Expression ')'
                | 'reduceSum' '(' Expression ',' Index ')'
                | UFunc      '(' Expression ')'
                | Function   '(' Expression (',' Expression)* ')'
                | Identifier
    Index      -> Variable
    Identifier -> Variable

``Instantiate(expr, shape)`` is only valid where a full Expression starts
(top level, inside brackets, function arguments) — not as an infix right
operand.  ``expr`` is the equation's right-hand side; ``shape`` supplies
units and index structure; the left-hand side is the declared variable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from .symbols import DEFAULT_TABLE, SymbolTable
from .syntax import (
    Add, Call, Expand, Group, Hadamard, Instantiate, Integral, MaxMin, Node,
    ParDiff, Power, Product, Reduce, ReduceSum, Root, TotalDiff, UFunc, Var,
)


# -----------------------------------------------------------------------------
# Lexer
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    pos: int  # character offset in the original source
    line: int
    col: int


@dataclass(frozen=True)
class _EOF:
    kind: str = "eof"
    value: str = ""
    pos: int = -1
    line: int = -1
    col: int = -1


EOF = _EOF()


def _tokenize(text: str, table: SymbolTable) -> List[Token]:
    """Tokenize a ProMo expression string using ``table`` for word/op lookup."""
    tokens: List[Token] = []
    pos = 0
    line = 1
    col = 1

    # infix symbols, longest first for greedy matching; empty symbols must not
    # be matched because text.startswith("", pos) is always true and would
    # leave pos unchanged, producing an infinite loop.
    infix_symbols = sorted([s for s in table.infix if s], key=len, reverse=True)

    while pos < len(text):
        # skip whitespace
        if text[pos].isspace():
            if text[pos] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            pos += 1
            continue

        # comments: '#' to end of line
        if text[pos] == "#":
            while pos < len(text) and text[pos] != "\n":
                pos += 1
            continue

        # double-colon must come before single colon
        if text.startswith("::", pos):
            tokens.append(Token("dcolon", "::", pos, line, col))
            pos += 2
            col += 2
            continue

        # infix operators from the symbol table (greedy, longest first)
        matched = False
        for sym in infix_symbols:
            if text.startswith(sym, pos):
                tokens.append(Token("op", sym, pos, line, col))
                pos += len(sym)
                col += len(sym)
                matched = True
                break
        if matched:
            continue

        # punctuation
        ch = text[pos]
        if ch in "()[]":
            kind = {"(": "lparen", ")": "rparen",
                    "[": "lbracket", "]": "rbracket"}[ch]
            tokens.append(Token(kind, ch, pos, line, col))
            pos += 1
            col += 1
            continue

        if ch == ",":
            tokens.append(Token("comma", ",", pos, line, col))
            pos += 1
            col += 1
            continue

        # word: keyword, ufunc, maxmin, function, or variable
        # Labels may contain and start with underscores (interface variables),
        # and the qualifier after '!' is a network/label label.
        m = re.match(
            r"[a-zA-Z_][a-zA-Z0-9_]*(?:![a-zA-Z_][a-zA-Z0-9_]*)?",
            text[pos:],
        )
        if m:
            word = m.group(0)
            kind = table.classify_word(word)
            tokens.append(Token(kind, word, pos, line, col))
            pos += len(word)
            col += len(word)
            continue

        raise ParseError(f"Unexpected character {text[pos]!r} at line {line}, column {col}")

    tokens.append(EOF)  # type: ignore[arg-type]
    return tokens


class ParseError(Exception):
    """Raised when the source text does not match the grammar."""

    def __init__(self, message: str, token: Optional[Token] = None):
        self.token = token
        self.message = message
        super().__init__(message)


# -----------------------------------------------------------------------------
# Recursive-descent parser
# -----------------------------------------------------------------------------

class Parser:
    """Precedence-climbing parser producing a ``syntax.Node`` AST."""

    def __init__(self, tokens: List[Token], table: SymbolTable):
        self.tokens = tokens
        self.table = table
        self.pos = 0

    @property
    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else EOF

    def _advance(self) -> Token:
        tok = self._current
        self.pos += 1
        return tok

    def _expect(self, kind: str, value: Optional[str] = None) -> Token:
        tok = self._current
        if tok.kind != kind:
            raise ParseError(
                f"Expected {kind}{(' ' + value) if value else ''}, got {tok.kind} {tok.value!r} "
                f"at line {tok.line}, col {tok.col}",
                tok,
            )
        if value is not None and tok.value != value:
            raise ParseError(
                f"Expected {value!r}, got {tok.value!r} at line {tok.line}, col {tok.col}",
                tok,
            )
        return self._advance()

    def _accept(self, kind: str, value: Optional[str] = None) -> Optional[Token]:
        tok = self._current
        if tok.kind == kind and (value is None or tok.value == value):
            return self._advance()
        return None

    def _at_factor_start(self, tok: Token) -> bool:
        """Return True if ``tok`` can start a Factor."""
        if tok.kind in ("lparen", "ufunc", "maxmin", "function", "var"):
            return True
        if tok.kind == "kw" and tok.value in {
            "Integral", "Product", "Root", "TotalDiff", "ParDiff", "reduceSum",
        }:
            return True
        return False

    def parse(self) -> Node:
        """Parse the entire token stream and return the AST."""
        node = self._expression()
        self._expect("eof")
        return node

    # Grammar entry points ----------------------------------------------------

    def _expression(self, min_prec: int = 1) -> Node:
        # 'Instantiate' '(' Expression ',' Expression ')' — only where a full
        # Expression starts (top level, brackets, function args), not as an
        # infix right operand.
        if min_prec == 1 and self._accept("kw", "Instantiate"):
            self._expect("lparen")
            expr = self._expression()
            self._expect("comma")
            shape = self._expression()
            self._expect("rparen")
            return Instantiate(expr, shape)

        left = self._factor()
        while True:
            tok = self._current
            if tok.kind != "op":
                return left
            info = self.table.infix_info(tok.value)
            if info is None or info.precedence < min_prec:
                return left
            self._advance()

            # REDUCE may carry an optional index:  a * N b
            index: Optional[Var] = None
            if info.factory == "reduce":
                if (
                    self._current.kind == "var"
                    and self._at_factor_start(self._peek(1))
                ):
                    index = Var(self._advance().value)

            next_min = info.precedence if info.right_assoc else info.precedence + 1
            right = self._expression(next_min)
            left = self._make_infix(info, left, right, index)

    def _make_infix(
        self, info, left: Node, right: Node, index: Optional[Var] = None
    ) -> Node:
        """Build the AST node for an infix operator.

        New infix operators at existing precedence levels need a table entry
        in ``symbols.py`` plus a case here.
        """
        f = info.factory
        if f == "add":
            return Add(info.symbol, left, right)
        if f == "expand":
            return Expand(left, right)
        if f == "hadamard":
            return Hadamard(left, right)
        if f == "reduce":
            return Reduce(left, right, index)
        if f == "power":
            return Power(left, right)
        raise ParseError(f"No AST factory for infix operator {info.symbol!r}")

    def _factor(self) -> Node:
        tok = self._current

        if tok.kind == "lparen":
            self._advance()
            body = self._expression()
            self._expect("rparen")
            return Group(body)

        if tok.kind == "ufunc":
            name = self._advance().value
            self._expect("lparen")
            arg = self._expression()
            self._expect("rparen")
            return UFunc(name, arg)

        if tok.kind == "maxmin":
            which = self._advance().value
            self._expect("lparen")
            a = self._expression()
            self._expect("comma")
            b = self._expression()
            self._expect("rparen")
            return MaxMin(which, a, b)

        if tok.kind == "function":
            name = Var(self._advance().value)
            self._expect("lparen")
            args = [self._expression()]
            while self._accept("comma"):
                args.append(self._expression())
            self._expect("rparen")
            return Call(name, tuple(args))

        if tok.kind == "kw":
            if tok.value == "Integral":
                return self._parse_integral()
            if tok.value == "Product":
                return self._parse_product()
            if tok.value == "Root":
                return self._parse_root()
            if tok.value == "TotalDiff":
                return self._parse_totaldiff()
            if tok.value == "ParDiff":
                return self._parse_pardiff()
            if tok.value == "reduceSum":
                return self._parse_reduce_sum()

        if tok.kind == "var":
            return Var(self._advance().value)

        raise ParseError(
            f"Unexpected token {tok.value!r} ({tok.kind}) at line {tok.line}, col {tok.col}",
            tok,
        )

    # Keyword-driven factors --------------------------------------------------

    def _parse_integral(self) -> Integral:
        self._expect("kw", "Integral")
        self._expect("lparen")
        body = self._expression()
        self._expect("dcolon")
        var = self._var()
        self._expect("in")
        self._expect("lbracket")
        lower = self._var()
        self._expect("comma")
        upper = self._var()
        self._expect("rbracket")
        self._expect("rparen")
        return Integral(body, var, lower, upper)

    def _parse_product(self) -> Product:
        self._expect("kw", "Product")
        self._expect("lparen")
        body = self._expression()
        self._expect("comma")
        index = self._var()
        self._expect("rparen")
        return Product(body, index)

    def _parse_root(self) -> Root:
        self._expect("kw", "Root")
        self._expect("lparen")
        body = self._expression()
        self._expect("rparen")
        return Root(body)

    def _parse_totaldiff(self) -> TotalDiff:
        self._expect("kw", "TotalDiff")
        self._expect("lparen")
        x = self._expression()
        self._expect("comma")
        y = self._expression()
        self._expect("rparen")
        return TotalDiff(x, y)

    def _parse_pardiff(self) -> ParDiff:
        self._expect("kw", "ParDiff")
        self._expect("lparen")
        x = self._expression()
        self._expect("comma")
        y = self._expression()
        self._expect("rparen")
        return ParDiff(x, y)

    def _parse_reduce_sum(self) -> ReduceSum:
        self._expect("kw", "reduceSum")
        self._expect("lparen")
        body = self._expression()
        self._expect("comma")
        index = self._var()
        self._expect("rparen")
        return ReduceSum(body, index)

    def _var(self) -> Var:
        tok = self._current
        if tok.kind != "var":
            raise ParseError(
                f"Expected variable, got {tok.value!r} at line {tok.line}, col {tok.col}",
                tok,
            )
        return Var(self._advance().value)


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def parse(text: str, table: SymbolTable = DEFAULT_TABLE) -> Node:
    """Parse ``text`` and return the AST.

    ``table`` supplies the language symbols — keywords, functions, and infix
    operators. Defaults to the built-in ProMo language; pass a table loaded
    from the ``promolg:`` graph once the RDF vocabulary is wired up.
    """
    tokens = _tokenize(text, table)
    parser = Parser(tokens, table)
    return parser.parse()
