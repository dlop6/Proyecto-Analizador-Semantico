"""
tests de integracion (frontend + semantica core) para declaraciones de let/var/const y
asignaciones: regla 6 (variables) y "prohibir reasignacion de const".
"""
from .conftest import analyze_full, codes_of


def test_variable_con_tipo_e_inicializador_compatible_no_reporta_nada():
    assert codes_of(analyze_full("let x: integer = 1;")) == set()


def test_variable_con_tipo_e_inicializador_incompatible_reporta_cps100():
    assert "CPS-100" in codes_of(analyze_full("let x: integer = \"a\";"))


def test_variable_sin_anotacion_infiere_del_inicializador():
    result = analyze_full("let x = 5; let y: integer = x;")
    assert codes_of(result) == set()


def test_variable_sin_tipo_y_sin_inicializador_reporta_cps101():
    assert "CPS-101" in codes_of(analyze_full("let x;"))


def test_constante_respeta_su_tipo():
    assert "CPS-100" in codes_of(analyze_full("const x: string = 1;"))


def test_reasignar_una_constante_reporta_cps102():
    assert "CPS-102" in codes_of(analyze_full("const x: integer = 1;\nx = 2;"))


def test_reasignar_una_variable_es_valido():
    assert codes_of(analyze_full("let x: integer = 1;\nx = 2;")) == set()


def test_asignar_tipo_incompatible_a_variable_ya_tipada_reporta_cps100():
    assert "CPS-100" in codes_of(analyze_full("let x: integer = 1;\nx = \"a\";"))


def test_asignar_a_identificador_no_declarado_reporta_cps103():
    assert "CPS-103" in codes_of(analyze_full("x = 1;"))


def test_atributo_de_clase_sin_tipo_y_sin_inicializador_reporta_cps101():
    assert "CPS-101" in codes_of(analyze_full("class A { let x; }"))


def test_atributo_de_clase_con_inicializador_incompatible_reporta_cps100():
    assert "CPS-100" in codes_of(analyze_full("class A { let x: integer = \"a\"; }"))
