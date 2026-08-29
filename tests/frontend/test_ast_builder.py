"""
tests de compiler/ast_builder.py: literales, las 4 rutas de asignacion, el fold de
leftHandSide, precedencia/asociatividad, y cobertura de que ningun visitor caiga
al default de antlr (visitChildren).
"""
from pathlib import Path

import pytest
from antlr4 import CommonTokenStream, InputStream

from compiler.ast_builder import AstBuilder
from compiler.ast_nodes import (
    ArrayLiteral, Assignment, BinaryOp, Block, BooleanLiteral, Call, ClassDecl,
    ExprStatement, ForStatement, Identifier, IndexAccess, IntegerLiteral, NewExpr,
    NullLiteral, Program, PropertyAccess, StringLiteral, Ternary, ThisExpr, UnaryOp,
)
from compiler.diagnostics import DiagnosticBag
from compiler.generated import CompiscriptLexer, CompiscriptParser

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def build(source: str, rule: str = "program"):
    lexer = CompiscriptLexer(InputStream(source))
    parser = CompiscriptParser(CommonTokenStream(lexer))
    tree = getattr(parser, rule)()
    diag = DiagnosticBag()
    ast = AstBuilder(diag).visit(tree)
    return ast, diag


def build_expr(source: str):
    """atajo: parsea 'source;' como expressionStatement y devuelve solo la expresion."""
    stmt, diag = build(f"{source};", "expressionStatement")
    return stmt.expression, diag


# ---------- literales (problema A) ----------

def test_literal_entero():
    node, _ = build_expr("123")
    assert isinstance(node, IntegerLiteral) and node.value == 123


def test_literal_string_sin_comillas():
    node, _ = build_expr('"hola"')
    assert isinstance(node, StringLiteral) and node.value == "hola"


def test_literal_string_vacio():
    node, _ = build_expr('""')
    assert isinstance(node, StringLiteral) and node.value == ""


def test_literal_entero_grande_da_warning():
    node, diag = build_expr("99999999999999999999999")
    assert isinstance(node, IntegerLiteral)
    codes = [d.code for d in diag]
    assert "CPS-002" in codes


def test_null_true_false():
    n, _ = build_expr("null")
    assert isinstance(n, NullLiteral)
    t, _ = build_expr("true")
    assert isinstance(t, BooleanLiteral) and t.value is True
    f, _ = build_expr("false")
    assert isinstance(f, BooleanLiteral) and f.value is False


# ---------- las 4 rutas de asignacion (problema B) ----------

def test_asignacion_statement_identifier():
    stmt, _ = build("x = 1;", "expressionStatement")
    assert isinstance(stmt, ExprStatement)
    assign = stmt.expression
    assert isinstance(assign, Assignment)
    assert isinstance(assign.target, Identifier) and assign.target.name == "x"


def test_asignacion_statement_propiedad():
    stmt, _ = build("obj.p = 1;", "expressionStatement")
    assign = stmt.expression
    assert isinstance(assign.target, PropertyAccess) and assign.target.name == "p"


def test_asignacion_expresion_assign_expr():
    node, _ = build_expr("(x = 1)")
    assert isinstance(node, Assignment)
    assert isinstance(node.target, Identifier) and node.target.name == "x"


def test_asignacion_encadenada_anida_a_la_derecha():
    stmt, _ = build("a = b = 1;", "expressionStatement")
    outer = stmt.expression
    assert outer.target.name == "a"
    inner = outer.value
    assert isinstance(inner, Assignment) and inner.target.name == "b"


def test_asignacion_a_index_access():
    stmt, _ = build("a[0] = 1;", "expressionStatement")
    assign = stmt.expression
    assert isinstance(assign.target, IndexAccess)


def test_asignacion_target_invalido_reporta_cps010():
    stmt, diag = build("f() = 1;", "expressionStatement")
    codes = [d.code for d in diag]
    assert "CPS-010" in codes


# ---------- fold de leftHandSide (problema C) ----------

def test_fold_property_index_call_encadenado():
    node, _ = build_expr("a.b[0].c(1)")
    assert isinstance(node, Call)
    prop_c = node.callee
    assert isinstance(prop_c, PropertyAccess) and prop_c.name == "c"
    idx = prop_c.obj
    assert isinstance(idx, IndexAccess)
    prop_b = idx.collection
    assert isinstance(prop_b, PropertyAccess) and prop_b.name == "b"
    assert isinstance(prop_b.obj, Identifier) and prop_b.obj.name == "a"


def test_fold_call_simple():
    node, _ = build_expr("a()")
    assert isinstance(node, Call) and node.args == []


def test_fold_index_simple():
    node, _ = build_expr("a[0]")
    assert isinstance(node, IndexAccess)


def test_fold_doble_llamada():
    node, _ = build_expr("a()()")
    assert isinstance(node, Call)
    assert isinstance(node.callee, Call)


def test_fold_doble_indice():
    node, _ = build_expr("a[0][1]")
    assert isinstance(node, IndexAccess)
    assert isinstance(node.collection, IndexAccess)


def test_new_seguido_de_metodo():
    node, _ = build_expr("new Foo().m()")
    assert isinstance(node, Call)
    prop = node.callee
    assert isinstance(prop, PropertyAccess) and prop.name == "m"
    assert isinstance(prop.obj, NewExpr) and prop.obj.class_name == "Foo"


def test_this_dot_propiedad():
    node, _ = build_expr("this.x")
    assert isinstance(node, PropertyAccess) and node.name == "x"
    assert isinstance(node.obj, ThisExpr)


def test_posicion_del_property_access_apunta_al_punto():
    # "a.b" -> el '.' esta en la columna 2 (1-based), no en la 'a' (columna 1)
    node, _ = build_expr("a.b")
    assert node.column == 2


# ---------- precedencia y asociatividad ----------

def test_resta_asociativa_izquierda():
    node, _ = build_expr("1 - 2 - 3")
    assert isinstance(node, BinaryOp) and node.op == "-"
    assert node.right.value == 3
    assert node.left.op == "-" and node.left.left.value == 1 and node.left.right.value == 2


def test_or_and_precedencia():
    node, _ = build_expr("a || b && c")
    assert isinstance(node, BinaryOp) and node.op == "||"
    assert isinstance(node.right, BinaryOp) and node.right.op == "&&"


def test_unario_negacion_y_negativo():
    node, _ = build_expr("!-x")
    assert isinstance(node, UnaryOp) and node.op == "!"
    assert isinstance(node.operand, UnaryOp) and node.operand.op == "-"


def test_ternario_anidado():
    node, _ = build_expr("a ? b : c ? d : e")
    assert isinstance(node, Ternary)
    assert isinstance(node.else_expr, Ternary)


def test_array_literal():
    node, _ = build_expr("[1, 2, 3]")
    assert isinstance(node, ArrayLiteral) and len(node.elements) == 3


# ---------- constructor por contexto sintactico (problema E) ----------

def test_constructor_dentro_de_clase():
    ast, _ = build("class A { function constructor(n: string) { this.n = n; } }")
    cls = ast.statements[0]
    ctor = cls.members[0]
    assert ctor.is_constructor is True
    assert ctor.is_method is True


def test_function_constructor_top_level_no_es_constructor():
    ast, _ = build("function constructor() {}")
    fn = ast.statements[0]
    assert fn.is_constructor is False


# ---------- integracion: program.cps oficial ----------

def test_program_oficial_construye_ast_completo():
    source = (FIXTURES_DIR / "valid" / "program_oficial.cps").read_text(encoding="utf-8")
    ast, diag = build(source)
    assert isinstance(ast, Program)
    assert len(ast.statements) > 0
    assert list(diag) == []


@pytest.mark.parametrize(
    "cps_file", sorted((FIXTURES_DIR / "valid").glob("*.cps")), ids=lambda p: p.name
)
def test_todas_las_fixtures_validas_construyen_ast_sin_errores(cps_file):
    source = cps_file.read_text(encoding="utf-8")
    ast, diag = build(source)
    assert isinstance(ast, Program)
    error_codes = [d.code for d in diag if d.severity.value == "error"]
    assert error_codes == [], f"{cps_file.name}: {error_codes}"
