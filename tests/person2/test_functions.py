"""
tests de integracion para funciones: llamadas, return, recursion y funciones anidadas
(reglas 10 y 11).
"""
from .conftest import analyze_full, codes_of


def test_llamada_valida_no_reporta_nada():
    assert codes_of(analyze_full(
        "function suma(a: integer, b: integer): integer { return a + b; }\n"
        "let r = suma(1, 2);"
    )) == set()


def test_llamada_con_aridad_incorrecta_reporta_cps111():
    assert "CPS-111" in codes_of(analyze_full(
        "function f(a: integer): integer { return a; }\nlet r = f(1, 2);"
    ))


def test_llamada_con_tipo_de_argumento_incompatible_reporta_cps112():
    assert "CPS-112" in codes_of(analyze_full(
        "function f(a: integer): integer { return a; }\nlet r = f(\"x\");"
    ))


def test_llamar_algo_que_no_es_funcion_reporta_cps110():
    assert "CPS-110" in codes_of(analyze_full("let x: integer = 1;\nlet r = x();"))


def test_llamar_identificador_no_declarado_reporta_cps103():
    assert "CPS-103" in codes_of(analyze_full("let r = f(1);"))


def test_return_incompatible_con_tipo_declarado_reporta_cps113():
    assert "CPS-113" in codes_of(analyze_full(
        "function f(): integer { return \"x\"; }"
    ))


def test_return_sin_valor_en_funcion_con_tipo_declarado_reporta_cps113():
    assert "CPS-113" in codes_of(analyze_full(
        "function f(): integer { return; }"
    ))


def test_returns_sin_anotacion_infieren_tipo_comun():
    assert codes_of(analyze_full(
        "function f(x: integer) { if (x > 0) { return 1; } return 2; }"
    )) == set()


def test_returns_sin_anotacion_sin_tipo_comun_reporta_cps114():
    assert "CPS-114" in codes_of(analyze_full(
        "function f(x: integer) { if (x > 0) { return 1; } return \"a\"; }"
    ))


def test_recursion_directa_es_valida():
    assert codes_of(analyze_full(
        "function fact(n: integer): integer {\n"
        "    if (n <= 1) { return 1; }\n"
        "    return n * fact(n - 1);\n"
        "}\n"
        "let r: integer = fact(5);"
    )) == set()


def test_referencia_adelantada_entre_funciones_top_level_es_valida():
    assert codes_of(analyze_full(
        "function par(n: integer): boolean { if (n == 0) { return true; } return impar(n - 1); }\n"
        "function impar(n: integer): boolean { if (n == 0) { return false; } return par(n - 1); }\n"
    )) == set()


def test_metodo_de_clase_se_valida_igual_que_una_funcion():
    assert "CPS-113" in codes_of(analyze_full(
        "class A { function m(): integer { return \"x\"; } }"
    ))
