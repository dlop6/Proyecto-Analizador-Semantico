"""tests de compiler/control_flow_rules.py: switch y codigo muerto."""
from compiler.ast_nodes import BreakStatement, ContinueStatement, ExprStatement, Identifier, ReturnStatement
from compiler.control_flow_rules import check_switch_case, check_switch_subject, find_dead_code
from compiler.types import BOOLEAN, ClassType, ERROR, INTEGER, NULL, STRING


# ---------- switch ----------

def test_discriminante_integer_es_valido():
    assert check_switch_subject(INTEGER) is None


def test_discriminante_string_es_valido():
    assert check_switch_subject(STRING) is None


def test_discriminante_de_clase_reporta_cps115():
    assert check_switch_subject(ClassType("Animal")) == "CPS-115"


def test_discriminante_error_no_cascadea():
    assert check_switch_subject(ERROR) is None


def test_case_compatible_con_discriminante():
    assert check_switch_case(INTEGER, INTEGER) is None


def test_case_incompatible_con_discriminante_reporta_cps116():
    assert check_switch_case(INTEGER, STRING) == "CPS-116"


def test_case_null_contra_discriminante_de_clase_es_compatible():
    assert check_switch_case(ClassType("Animal"), NULL) is None


# ---------- codigo muerto ----------

def _expr_stmt(line):
    return ExprStatement(line=line, column=1, expression=Identifier(line=line, column=1, name="x"))


def test_sin_terminador_no_hay_codigo_muerto():
    statements = [_expr_stmt(1), _expr_stmt(2)]
    assert find_dead_code(statements) == []


def test_statement_despues_de_return_es_codigo_muerto():
    ret = ReturnStatement(line=1, column=1, value=None)
    dead = _expr_stmt(2)
    assert find_dead_code([ret, dead]) == [dead]


def test_statement_despues_de_break_es_codigo_muerto():
    brk = BreakStatement(line=1, column=1)
    dead = _expr_stmt(2)
    assert find_dead_code([brk, dead]) == [dead]


def test_statement_despues_de_continue_es_codigo_muerto():
    cont = ContinueStatement(line=1, column=1)
    dead = _expr_stmt(2)
    assert find_dead_code([cont, dead]) == [dead]


def test_terminador_al_final_no_deja_codigo_muerto():
    assert find_dead_code([_expr_stmt(1), ReturnStatement(line=2, column=1, value=None)]) == []
