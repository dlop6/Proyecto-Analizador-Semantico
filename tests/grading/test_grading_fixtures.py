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


def test_fixture_tac_integral_genera_codigo_intermedio_de_todos_los_rubros():
    result = compile_source(_source("valid_tac_complete.cps"))
    assert result.success is True
    assert result.diagnostics == []
    text = result.tac_text
    for fragment in (
        "NEW_OBJ Perro", "CALL fn::Perro.constructor", "CALL_METHOD", "hablar[0]",  # clases y herencia
        "NEW_ARR 4", "ARR_GET", "ARR_SET", "LEN",                                    # arreglos y foreach
        "L_foreach_cond", "L_while_cond", "L_switch_case", "L_if_end",               # control de flujo
        "L_or_end", "L_and_end",                                                     # logica con cortocircuito
        "CALL t1, fn::factorial, argc=1",                                            # recursion
        "TRY_BEGIN", "TRY_END", "CATCH error@global",                                # try/catch
        "FUNC_END fn::factorial, temps=",                                            # pico de temporales
    ):
        assert fragment in text, fragment


def test_los_fixtures_con_errores_no_generan_tac():
    for name in ("semantic_errors.cps", "lexical_recovery.cps", "syntax_recovery.cps"):
        result = compile_source(_source(name))
        assert result.success is False
        assert result.tac_text is None
