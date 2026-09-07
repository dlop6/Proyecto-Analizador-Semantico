"""
tests de integracion para expresiones core: operadores, identificadores, ternario y
la escritura de inferred_type en cada nodo (criterio de gate b).
"""
from compiler.frontend import analyze_source
from compiler.core_semantics import analyze
from compiler.types import BOOLEAN, INTEGER, STRING

from .conftest import analyze_full, codes_of


def test_suma_entera_infiere_integer():
    frontend_result = analyze_source("let x = 1 + 2;")
    result = analyze(frontend_result)
    assert codes_of(result) == set()
    assert result.ast.statements[0].initializer.inferred_type == INTEGER


def test_concatenacion_de_strings_infiere_string():
    frontend_result = analyze_source("let x = \"a\" + \"b\";")
    result = analyze(frontend_result)
    assert result.ast.statements[0].initializer.inferred_type == STRING


def test_comparacion_infiere_boolean():
    frontend_result = analyze_source("let x = 1 < 2;")
    result = analyze(frontend_result)
    assert result.ast.statements[0].initializer.inferred_type == BOOLEAN


def test_sumar_entero_y_string_reporta_cps104():
    assert "CPS-104" in codes_of(analyze_full("let x = 1 + \"a\";"))


def test_and_con_operando_entero_reporta_cps107():
    assert "CPS-107" in codes_of(analyze_full("let x = true && 1;"))


def test_identificador_usado_antes_de_declararse_en_su_propia_expresion():
    assert "CPS-103" in codes_of(analyze_full("let x = w + 1;"))


def test_identificador_visible_desde_un_scope_anidado():
    result = analyze_full("let x: integer = 1;\nif (true) { print(x); }")
    assert codes_of(result) == set()


def test_variable_de_un_bloque_no_es_visible_fuera():
    assert "CPS-103" in codes_of(analyze_full("if (true) { let x: integer = 1; }\nprint(x);"))


def test_ternario_con_condicion_no_booleana_reporta_cps109():
    assert "CPS-109" in codes_of(analyze_full("let x = 1 ? 2 : 3;"))


def test_ternario_con_ramas_incompatibles_reporta_cps118():
    assert "CPS-118" in codes_of(analyze_full("let x = true ? 1 : \"a\";"))


def test_ternario_valido_infiere_el_tipo_comun():
    frontend_result = analyze_source("let x = true ? 1 : 2;")
    result = analyze(frontend_result)
    assert codes_of(result) == set()
    assert result.ast.statements[0].initializer.inferred_type == INTEGER


def test_unario_negacion_aritmetica_sobre_string_reporta_cps108():
    assert "CPS-108" in codes_of(analyze_full("let x = -\"a\";"))
