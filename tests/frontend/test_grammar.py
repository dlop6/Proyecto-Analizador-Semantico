"""
tests de la gramatica generada por antlr: que compile, que importe, y que los .cps
de fixtures/valid parseen limpio y los de fixtures/invalid fallen como se espera.

si antlr no fue regenerado (falta compiler/generated/*.py), este import falla y el
test truena -- a proposito, no hay pytest.skip aca porque es criterio de Gate A.
"""
from pathlib import Path

import pytest
from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from compiler.generated import CompiscriptLexer, CompiscriptParser

FIXTURES_DIR = Path(__file__).parent / "fixtures"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"


class _CollectErrors(ErrorListener):
    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append((line, column, msg))


def _parse(source: str):
    lexer = CompiscriptLexer(InputStream(source))
    lexer.removeErrorListeners()
    lexer_errors = _CollectErrors()
    lexer.addErrorListener(lexer_errors)

    parser = CompiscriptParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser_errors = _CollectErrors()
    parser.addErrorListener(parser_errors)

    tree = parser.program()
    return tree, lexer_errors.errors + parser_errors.errors


@pytest.mark.parametrize("cps_file", sorted(VALID_DIR.glob("*.cps")), ids=lambda p: p.name)
def test_fixtures_validas_parsean_sin_errores(cps_file):
    source = cps_file.read_text(encoding="utf-8")
    _, errors = _parse(source)
    assert errors == [], f"{cps_file.name} deberia parsear limpio, errores: {errors}"


def test_syntax_error_fixture_falla():
    source = (INVALID_DIR / "syntax_error.cps").read_text(encoding="utf-8")
    _, errors = _parse(source)
    assert len(errors) >= 1


def test_if_sin_bloque_es_invalido():
    # la gramatica exige block obligatorio en ifStatement, "if (x) print(1);" no parsea
    _, errors = _parse("function f() { if (1 < 2) print(1); }")
    assert len(errors) >= 1


def test_llave_sin_cerrar_es_invalida():
    _, errors = _parse("function f() { let x: integer = 1;")
    assert len(errors) >= 1


def test_declaracion_sin_valor_es_invalida():
    _, errors = _parse("let x: integer = ;")
    assert len(errors) >= 1


def test_literal_token_unificado_documentado():
    """
    documenta el hallazgo clave: 123 y "hola" comparten el mismo tipo de token
    (Literal), antlr no los distingue. por eso ast_builder tiene que mirar el texto.
    """
    lexer_int = CompiscriptLexer(InputStream("123"))
    token_int = lexer_int.nextToken()
    lexer_str = CompiscriptLexer(InputStream('"hola"'))
    token_str = lexer_str.nextToken()
    assert token_int.type == token_str.type == CompiscriptParser.Literal
