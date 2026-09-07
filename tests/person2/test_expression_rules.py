"""tests de compiler/expression_rules.py: funciones puras de tipos, sin ast ni scopes."""
from compiler.expression_rules import check_binary_op, check_condition, check_ternary, check_unary_op
from compiler.types import BOOLEAN, ClassType, ERROR, INTEGER, NULL, STRING


# ---------- operadores aritmeticos y '+' ----------

def test_suma_entera_da_integer():
    result, code, detail = check_binary_op("+", INTEGER, INTEGER)
    assert result is INTEGER
    assert code is None


def test_concatenacion_string_da_string():
    result, code, detail = check_binary_op("+", STRING, STRING)
    assert result == STRING
    assert code is None


def test_suma_entero_mas_string_es_invalida():
    result, code, detail = check_binary_op("+", INTEGER, STRING)
    assert code == "CPS-104"
    assert result == ERROR


def test_resta_entre_strings_es_invalida():
    result, code, detail = check_binary_op("-", STRING, STRING)
    assert code == "CPS-104"


def test_error_en_operando_no_cascadea_diagnostico():
    result, code, detail = check_binary_op("+", ERROR, INTEGER)
    assert code is None
    assert result == ERROR


# ---------- relacionales ----------

def test_relacional_entre_enteros_da_boolean():
    result, code, detail = check_binary_op("<", INTEGER, INTEGER)
    assert result == BOOLEAN
    assert code is None


def test_relacional_entre_strings_es_invalida():
    result, code, detail = check_binary_op("<=", STRING, STRING)
    assert code == "CPS-105"


# ---------- igualdad ----------

def test_igualdad_mismo_tipo_da_boolean():
    result, code, detail = check_binary_op("==", STRING, STRING)
    assert result == BOOLEAN
    assert code is None


def test_igualdad_null_contra_clase_es_valida():
    result, code, detail = check_binary_op("==", NULL, ClassType("Animal"))
    assert code is None


def test_igualdad_entre_tipos_no_comparables_es_invalida():
    result, code, detail = check_binary_op("!=", INTEGER, STRING)
    assert code == "CPS-106"


# ---------- logicos ----------

def test_and_entre_booleanos_da_boolean():
    result, code, detail = check_binary_op("&&", BOOLEAN, BOOLEAN)
    assert result == BOOLEAN
    assert code is None


def test_or_con_operando_no_booleano_es_invalido():
    result, code, detail = check_binary_op("||", BOOLEAN, INTEGER)
    assert code == "CPS-107"


# ---------- unarios ----------

def test_negacion_aritmetica_de_integer_da_integer():
    result, code, detail = check_unary_op("-", INTEGER)
    assert result == INTEGER
    assert code is None


def test_negacion_aritmetica_de_string_es_invalida():
    result, code, detail = check_unary_op("-", STRING)
    assert code == "CPS-108"


def test_negacion_logica_de_boolean_da_boolean():
    result, code, detail = check_unary_op("!", BOOLEAN)
    assert result == BOOLEAN
    assert code is None


def test_negacion_logica_de_integer_es_invalida():
    result, code, detail = check_unary_op("!", INTEGER)
    assert code == "CPS-108"


# ---------- condiciones ----------

def test_condicion_booleana_no_reporta_nada():
    assert check_condition(BOOLEAN) is None


def test_condicion_no_booleana_reporta_cps109():
    assert check_condition(INTEGER) == "CPS-109"


def test_condicion_con_error_no_cascadea():
    assert check_condition(ERROR) is None


# ---------- ternario ----------

def test_ternario_mismo_tipo_en_ambas_ramas():
    result, code = check_ternary(INTEGER, INTEGER)
    assert result == INTEGER
    assert code is None


def test_ternario_null_y_clase_unifica_en_la_clase():
    result, code = check_ternary(NULL, ClassType("Animal"))
    assert result == ClassType("Animal")
    assert code is None


def test_ternario_sin_tipo_comun_reporta_cps118():
    result, code = check_ternary(INTEGER, STRING)
    assert code == "CPS-118"
    assert result == ERROR
