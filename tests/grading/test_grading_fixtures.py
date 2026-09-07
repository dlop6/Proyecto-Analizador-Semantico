"""Pruebas ejecutables de los casos preparados para la evaluacion."""
from pathlib import Path

from compiler.compiler_service import compile_source
from compiler.frontend import analyze_source


FIXTURES = Path(__file__).parent / "fixtures"


def _source(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_fixture_valido_integral_compila_y_genera_ast():
    result = compile_source(_source("valid_complete.cps"))
    assert result.success is True
    assert result.diagnostics == []
    assert result.ast_svg is not None


def test_fixture_semantico_acumula_los_diagnosticos_documentados():
    result = compile_source(_source("semantic_errors.cps"))
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert result.success is False
    assert {"CPS-103", "CPS-119", "CPS-120", "CPS-215"} <= codes


def test_fixture_lexico_recupera_y_reporta_dos_caracteres():
    result = analyze_source(_source("lexical_recovery.cps"))
    assert [diagnostic.code for diagnostic in result.diagnostics].count("CPS-000") >= 2


def test_fixture_sintactico_recupera_y_reporta_dos_errores():
    result = analyze_source(_source("syntax_recovery.cps"))
    assert [diagnostic.code for diagnostic in result.diagnostics].count("CPS-001") >= 2
