"""
catalogo del ast propio de compiscript, parte del frontend. cobertura total: incluye
try/catch, foreach y print aunque el pdf no se los asigne a nadie explicitamente.

decisiones clave (ver plan):
- slots=True: si alguien escribe mal un atributo (typo tipo "infered_type") explota
  en vez de fallar callado. importa mucho en un proyecto con varias etapas.
- kw_only=True: evita el problema clasico de dataclasses con herencia + defaults
  (un campo sin default no puede ir despues de uno con default). construyendo todo
  por keyword se elimina ese problema de raiz.
- los nodos NO son frozen (la semantica core rellena inferred_type in-place). los
  tipos de types.py si son frozen. son cosas distintas a proposito.
- line/column viven en la base Node, siempre 1-based (normalizado en ast_builder).
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Callable

from compiler.types import Type


@dataclass(slots=True, kw_only=True)
class Node:
    line: int
    column: int


@dataclass(slots=True, kw_only=True)
class Expr(Node):
    # contrato con la semantica core: aca siempre queda en None, el frontend nunca lo escribe
    inferred_type: Type | None = None


@dataclass(slots=True, kw_only=True)
class Stmt(Node):
    pass


# ============================================================
# programa y declaraciones
# ============================================================

@dataclass(slots=True, kw_only=True)
class Program(Node):
    statements: list[Stmt] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class Param(Node):
    name: str
    declared_type: "TypeRef | None" = None


@dataclass(slots=True, kw_only=True)
class VarDecl(Stmt):
    """
    unifica let/var/const (no hay ConstDecl separado, la unica diferencia real es
    is_const y que const exige inicializador, eso se valida en symbol_collector).
    """
    name: str
    keyword: str  # "let" | "var" | "const"
    is_const: bool
    declared_type: "TypeRef | None" = None
    initializer: Expr | None = None


@dataclass(slots=True, kw_only=True)
class FunctionDecl(Stmt):
    name: str
    params: list[Param] = field(default_factory=list)
    return_type: "TypeRef | None" = None
    body: "Block"
    is_constructor: bool = False
    is_method: bool = False


@dataclass(slots=True, kw_only=True)
class ClassDecl(Stmt):
    name: str
    parent_name: str | None = None
    members: list[Stmt] = field(default_factory=list)  # FunctionDecl | VarDecl


# ============================================================
# tipos (referencia sintactica a un tipo, no confundir con types.Type)
# ============================================================

@dataclass(slots=True, kw_only=True)
class TypeRef(Node):
    """como aparece un tipo en el codigo fuente: nombre base + cantidad de [] anidados."""
    base_name: str  # "integer" | "string" | "boolean" | nombre de clase
    array_dimensions: int = 0


# ============================================================
# statements
# ============================================================

@dataclass(slots=True, kw_only=True)
class Block(Stmt):
    statements: list[Stmt] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class ExprStatement(Stmt):
    expression: Expr


@dataclass(slots=True, kw_only=True)
class PrintStatement(Stmt):
    expression: Expr


@dataclass(slots=True, kw_only=True)
class IfStatement(Stmt):
    condition: Expr
    then_block: Block
    else_block: Block | None = None


@dataclass(slots=True, kw_only=True)
class WhileStatement(Stmt):
    condition: Expr
    body: Block


@dataclass(slots=True, kw_only=True)
class DoWhileStatement(Stmt):
    body: Block
    condition: Expr


@dataclass(slots=True, kw_only=True)
class ForStatement(Stmt):
    init: "VarDecl | Assignment | None" = None
    condition: Expr | None = None
    update: Expr | None = None
    body: Block


@dataclass(slots=True, kw_only=True)
class ForeachStatement(Stmt):
    var_name: str
    iterable: Expr
    body: Block


@dataclass(slots=True, kw_only=True)
class BreakStatement(Stmt):
    pass


@dataclass(slots=True, kw_only=True)
class ContinueStatement(Stmt):
    pass


@dataclass(slots=True, kw_only=True)
class ReturnStatement(Stmt):
    value: Expr | None = None


@dataclass(slots=True, kw_only=True)
class TryCatchStatement(Stmt):
    try_block: Block
    exception_name: str
    catch_block: Block


@dataclass(slots=True, kw_only=True)
class SwitchCase(Node):
    value: Expr
    statements: list[Stmt] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class SwitchStatement(Stmt):
    subject: Expr
    cases: list[SwitchCase] = field(default_factory=list)
    default_statements: list[Stmt] | None = None


# ============================================================
# expresiones
# ============================================================

@dataclass(slots=True, kw_only=True)
class Assignment(Expr):
    """
    nodo unico para las 4 rutas gramaticales de asignacion. target es cualquier
    expresion asignable: Identifier, PropertyAccess o IndexAccess.
    """
    target: Expr
    value: Expr


@dataclass(slots=True, kw_only=True)
class Ternary(Expr):
    condition: Expr
    then_expr: Expr
    else_expr: Expr


@dataclass(slots=True, kw_only=True)
class BinaryOp(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass(slots=True, kw_only=True)
class UnaryOp(Expr):
    op: str
    operand: Expr


@dataclass(slots=True, kw_only=True)
class Identifier(Expr):
    name: str


@dataclass(slots=True, kw_only=True)
class IntegerLiteral(Expr):
    value: int


@dataclass(slots=True, kw_only=True)
class StringLiteral(Expr):
    value: str


@dataclass(slots=True, kw_only=True)
class BooleanLiteral(Expr):
    value: bool


@dataclass(slots=True, kw_only=True)
class NullLiteral(Expr):
    pass


@dataclass(slots=True, kw_only=True)
class ArrayLiteral(Expr):
    elements: list[Expr] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class Call(Expr):
    """callee es una Expr arbitraria: no hay MethodCall vs FunctionCall separados."""
    callee: Expr
    args: list[Expr] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class IndexAccess(Expr):
    collection: Expr
    index: Expr


@dataclass(slots=True, kw_only=True)
class PropertyAccess(Expr):
    obj: Expr
    name: str


@dataclass(slots=True, kw_only=True)
class NewExpr(Expr):
    class_name: str
    args: list[Expr] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class ThisExpr(Expr):
    pass


@dataclass(slots=True, kw_only=True)
class ErrorExpr(Expr):
    """nodo de guardia para huecos legitimos de la gramatica que no logramos construir bien."""
    pass


# ============================================================
# visitor generico
# ============================================================

class AstVisitor:
    """
    visitor base para recorrer el ast propio. usa un diccionario tipo->callable en vez
    de singledispatchmethod (mas explicito, sin sorpresas con slots). las etapas siguientes
    solo sobreescriben lo que les importa, generic_visit se encarga del resto (ocp).
    """

    def __init__(self) -> None:
        self._dispatch: dict[type, Callable] = {}

    def visit(self, node: Node):
        handler = self._dispatch.get(type(node))
        if handler is not None:
            return handler(node)
        method = getattr(self, f"visit_{type(node).__name__}", None)
        if method is not None:
            return method(node)
        return self.generic_visit(node)

    def generic_visit(self, node: Node):
        """recorre los campos del nodo por introspeccion, sin necesitar un visitor especifico."""
        for f in fields(node):
            value = getattr(node, f.name)
            self._visit_value(value)
        return None

    def _visit_value(self, value) -> None:
        if isinstance(value, Node):
            self.visit(value)
        elif isinstance(value, list):
            for item in value:
                self._visit_value(item)
