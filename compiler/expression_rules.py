"""
reglas de tipos para expresiones core: operadores binarios/unarios, condiciones y el
operador ternario, parte de la semantica core.

funciones puras: reciben los tipos ya inferidos de los operandos (nunca el ast ni los
scopes, eso lo camina core_semantic_visitor.py) y devuelven el tipo resultante junto con
un codigo de diagnostico opcional. no escriben diagnosticos ellas mismas -- el catalogo de
mensajes CPS-1xx y la bolsa de diagnosticos son responsabilidad exclusiva de
core_semantic_visitor.py, que es quien conoce la posicion real de cada nodo. esto evita
que este modulo dependa de diagnostics.py o de ast_nodes.py, y lo deja trivial de probar
con tipos sueltos.

un tipo ErrorType en cualquier operando se absorbe en silencio (ya se reporto mas abajo
en el arbol) para no cascadear diagnosticos sobre el mismo error.
"""
from __future__ import annotations

from compiler.types import (
    BOOLEAN, ClassHierarchy, ERROR, ErrorType, INTEGER, STRING, Type,
    common_type, is_assignable, numeric_result,
)

_ARITHMETIC_OPS = {"-", "*", "/", "%"}
_RELATIONAL_OPS = {"<", "<=", ">", ">="}
_EQUALITY_OPS = {"==", "!="}
_LOGICAL_OPS = {"&&", "||"}

# resultado de una regla: (tipo resultante, codigo de diagnostico o None si no hay error, detail)
CheckResult = tuple[Type, "str | None", "str | None"]


def check_binary_op(op: str, left: Type, right: Type, hierarchy: ClassHierarchy | None = None) -> CheckResult:
    """
    tipo resultante de aplicar `op` entre `left` y `right` segun las decisiones del proyecto:
    +/-/*/%%  son numericos (integer unicamente, no hay float en esta gramatica), + ademas
    permite string+string; comparaciones relacionales exigen numericos; == / != exigen
    tipos compatibles en cualquier direccion (cubre null y subclases); && / || exigen boolean.
    """
    if isinstance(left, ErrorType) or isinstance(right, ErrorType):
        return ERROR, None, None

    if op == "+":
        if left == STRING and right == STRING:
            return STRING, None, None
        numeric = numeric_result(left, right)
        if numeric is not None:
            return numeric, None, None
        return ERROR, "CPS-104", op

    if op in _ARITHMETIC_OPS:
        numeric = numeric_result(left, right)
        if numeric is not None:
            return numeric, None, None
        return ERROR, "CPS-104", op

    if op in _RELATIONAL_OPS:
        if numeric_result(left, right) is not None:
            return BOOLEAN, None, None
        return ERROR, "CPS-105", op

    if op in _EQUALITY_OPS:
        if is_assignable(left, right, hierarchy) or is_assignable(right, left, hierarchy):
            return BOOLEAN, None, None
        return ERROR, "CPS-106", op

    if op in _LOGICAL_OPS:
        if left == BOOLEAN and right == BOOLEAN:
            return BOOLEAN, None, None
        return ERROR, "CPS-107", op

    # defensivo: la gramatica actual no produce otros operadores en additiveExpr/etc.
    return ERROR, "CPS-104", op


def check_unary_op(op: str, operand: Type) -> CheckResult:
    """'-' exige integer, '!' exige boolean. cualquier otro caso es defensivo."""
    if isinstance(operand, ErrorType):
        return ERROR, None, None
    if op == "-":
        if operand == INTEGER:
            return INTEGER, None, None
        return ERROR, "CPS-108", op
    if op == "!":
        if operand == BOOLEAN:
            return BOOLEAN, None, None
        return ERROR, "CPS-108", op
    return ERROR, "CPS-108", op


def check_condition(condition_type: Type) -> str | None:
    """valida que una condicion (if/while/do-while/for/ternario) sea booleana."""
    if isinstance(condition_type, ErrorType):
        return None
    return None if condition_type == BOOLEAN else "CPS-109"


def check_ternary(then_type: Type, else_type: Type, hierarchy: ClassHierarchy | None = None) -> tuple[Type, "str | None"]:
    """tipo resultante del operador ternario: el supertipo comun mas especifico de sus dos ramas."""
    if isinstance(then_type, ErrorType) or isinstance(else_type, ErrorType):
        return ERROR, None
    result = common_type(then_type, else_type, hierarchy)
    if result is None:
        return ERROR, "CPS-118"
    return result, None
