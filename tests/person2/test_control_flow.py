"""
tests de integracion para control de flujo: condiciones booleanas de if/while/do-while/for,
switch y codigo muerto (reglas 8 y 13). break/continue/return fuera de contexto ya los
prueba tests/frontend (los reporta symbol_collector.py), no se repiten aca.
"""
from .conftest import analyze_full, codes_of


# ---------- condiciones booleanas ----------

def test_if_con_condicion_booleana_es_valido():
    assert codes_of(analyze_full("if (true) { print(1); }")) == set()


def test_if_con_condicion_no_booleana_reporta_cps109():
    assert "CPS-109" in codes_of(analyze_full("if (1) { print(1); }"))


def test_while_con_condicion_no_booleana_reporta_cps109():
    assert "CPS-109" in codes_of(analyze_full("while (1) { print(1); }"))


def test_do_while_con_condicion_no_booleana_reporta_cps109():
    assert "CPS-109" in codes_of(analyze_full("do { print(1); } while (1);"))


def test_for_con_condicion_no_booleana_reporta_cps109():
    assert "CPS-109" in codes_of(analyze_full("for (let i: integer = 0; i; i = i + 1) { print(i); }"))


def test_for_valido_no_reporta_nada():
    assert codes_of(analyze_full("for (let i: integer = 0; i < 10; i = i + 1) { print(i); }")) == set()


def test_variable_de_cabecera_for_no_se_filtra_fuera():
    assert "CPS-103" in codes_of(analyze_full(
        "for (let i: integer = 0; i < 10; i = i + 1) { print(i); }\nprint(i);"
    ))


# ---------- switch ----------

def test_switch_con_discriminante_valido_y_cases_compatibles():
    assert codes_of(analyze_full(
        "let x: integer = 1;\nswitch (x) { case 1: print(1); case 2: print(2); default: print(0); }"
    )) == set()


def test_switch_con_discriminante_de_tipo_invalido_reporta_cps115():
    assert "CPS-115" in codes_of(analyze_full("class A {} let a: A = new A();\nswitch (a) { default: print(0); }"))


def test_switch_con_case_incompatible_con_el_discriminante_reporta_cps116():
    assert "CPS-116" in codes_of(analyze_full(
        "let x: integer = 1;\nswitch (x) { case \"a\": print(1); }"
    ))


# ---------- codigo muerto ----------

def test_codigo_despues_de_return_reporta_cps117():
    assert "CPS-117" in codes_of(analyze_full(
        "function f(): integer { return 1; print(\"inalcanzable\"); }"
    ))


def test_codigo_despues_de_break_dentro_de_un_bucle_reporta_cps117():
    assert "CPS-117" in codes_of(analyze_full(
        "while (true) { break; print(\"inalcanzable\"); }"
    ))


def test_codigo_muerto_no_es_error_bloqueante():
    result = analyze_full("function f(): integer { return 1; print(1); }")
    assert result.ok is True  # es warning, no error


def test_codigo_en_otro_bloque_despues_del_if_no_es_codigo_muerto():
    # el 'if' termina con return solo en una rama; el codigo despues del if entero es alcanzable
    assert codes_of(analyze_full(
        "function f(x: integer): integer {\n"
        "    if (x > 0) { return 1; }\n"
        "    return 2;\n"
        "}"
    )) == set()
