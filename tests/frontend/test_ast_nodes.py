"""
tests de compiler/ast_nodes.py: catalogo de nodos, garantias de slots/kw_only,
contrato inferred_type, y que el visitor generico recorra todo.
"""
import dataclasses

import pytest

from compiler import ast_nodes as m
from compiler.ast_nodes import (
    AstVisitor, Node, Expr, Block, ExprStatement, Identifier, VarDecl, Program,
)


def _all_node_classes() -> list[type]:
    return [
        getattr(m, name) for name in dir(m)
        if isinstance(getattr(m, name), type)
        and issubclass(getattr(m, name), Node)
        and getattr(m, name) not in (Node, Expr, m.Stmt)
    ]


def test_kw_only_rechaza_construccion_posicional():
    with pytest.raises(TypeError):
        VarDecl(1, 1, "x", "let", False)  # type: ignore[call-arg]


def test_construccion_por_keyword_funciona():
    v = VarDecl(line=1, column=1, name="x", keyword="let", is_const=False)
    assert v.name == "x" and v.is_const is False


def test_slots_bloquea_atributos_no_declarados():
    node = Identifier(line=1, column=1, name="x")
    with pytest.raises(AttributeError):
        node.infered_type = "typo"  # type: ignore[attr-defined]


def test_inferred_type_default_es_none_persona1_no_lo_escribe():
    node = Identifier(line=1, column=1, name="x")
    assert node.inferred_type is None


def test_todos_los_nodos_tienen_line_y_column():
    v = VarDecl(line=5, column=9, name="x", keyword="var", is_const=False)
    assert v.line == 5
    assert v.column == 9


def test_generic_visit_recorre_el_arbol_completo():
    visited = []

    class Collector(AstVisitor):
        def generic_visit(self, node):
            visited.append(type(node).__name__)
            super().generic_visit(node)

    tree = Block(
        line=1, column=1,
        statements=[
            ExprStatement(line=2, column=1, expression=Identifier(line=2, column=1, name="x")),
        ],
    )
    Collector().visit(tree)
    assert visited == ["Block", "ExprStatement", "Identifier"]


# ---------- cobertura de catalogo ----------

@pytest.mark.parametrize("node_cls", _all_node_classes(), ids=lambda c: c.__name__)
def test_catalogo_cada_nodo_es_instanciable(node_cls):
    """
    cada nodo debe poder construirse dandole valores minimos a sus campos requeridos.
    esto no cubre semantica, solo garantiza que el catalogo esta completo y sin
    typos de definicion (campos faltantes, tipos rotos, etc).
    """
    kwargs = {"line": 1, "column": 1}
    for f in dataclasses.fields(node_cls):
        if f.name in ("line", "column"):
            continue
        if f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING:  # type: ignore
            continue
        # campo requerido sin default: le damos un valor generico segun su tipo esperado
        kwargs[f.name] = _dummy_value(f.name)
    instance = node_cls(**kwargs)
    assert isinstance(instance, Node)


def _dummy_value(field_name: str):
    """valores de relleno razonables para campos requeridos comunes del catalogo."""
    dummies = {
        "name": "x",
        "op": "+",
        "value": IntegerDummy(),
        "condition": Identifier(line=1, column=1, name="c"),
        "left": Identifier(line=1, column=1, name="a"),
        "right": Identifier(line=1, column=1, name="b"),
        "operand": Identifier(line=1, column=1, name="a"),
        "target": Identifier(line=1, column=1, name="a"),
        "obj": Identifier(line=1, column=1, name="a"),
        "collection": Identifier(line=1, column=1, name="a"),
        "index": Identifier(line=1, column=1, name="i"),
        "callee": Identifier(line=1, column=1, name="f"),
        "expression": Identifier(line=1, column=1, name="x"),
        "class_name": "Foo",
        "var_name": "i",
        "iterable": Identifier(line=1, column=1, name="a"),
        "exception_name": "e",
        "keyword": "let",
        "is_const": False,
        "base_name": "integer",
        "then_expr": Identifier(line=1, column=1, name="a"),
        "else_expr": Identifier(line=1, column=1, name="b"),
        "then_block": Block(line=1, column=1),
        "body": Block(line=1, column=1),
        "try_block": Block(line=1, column=1),
        "catch_block": Block(line=1, column=1),
        "subject": Identifier(line=1, column=1, name="x"),
    }
    if field_name in dummies:
        return dummies[field_name]
    return None


def IntegerDummy():
    return 0
