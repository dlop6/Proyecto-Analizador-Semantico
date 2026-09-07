"""
reglas de control de flujo, parte de la semantica core: discriminante y cases de
'switch', y deteccion de codigo muerto. las condiciones booleanas de if/while/do-while/for
son responsabilidad de expression_rules.check_condition (una sola regla de "es booleano",
no se repite aca).

'break'/'continue' fuera de bucle y 'return' fuera de funcion ya los reporta
symbol_collector.py durante la fase de scopes del frontend (necesita la pila de scopes
que arma esa misma pasada) -- este modulo no los vuelve a chequear, seria duplicar una
regla ya cubierta (dry).

igual que los otros modulos de reglas, funciones puras que devuelven un codigo de
diagnostico o None; no escriben en la bolsa de diagnosticos ni conocen su catalogo.
"""
from __future__ import annotations

from compiler.ast_nodes import BreakStatement, ContinueStatement, ReturnStatement, Stmt
from compiler.types import ArrayType, BOOLEAN, ClassHierarchy, ErrorType, INTEGER, STRING, Type, is_assignable

_VALID_SWITCH_TYPES = (INTEGER, STRING, BOOLEAN)
_TERMINATORS = (ReturnStatement, BreakStatement, ContinueStatement)


def check_switch_subject(subject_type: Type) -> "str | None":
    """el discriminante de switch debe ser integer, string o boolean (regla 8)."""
    if isinstance(subject_type, ErrorType):
        return None
    return None if subject_type in _VALID_SWITCH_TYPES else "CPS-115"


def check_switch_case(subject_type: Type, case_type: Type, hierarchy: ClassHierarchy | None = None) -> "str | None":
    """cada 'case' debe ser compatible con el tipo del discriminante, en cualquier direccion."""
    if isinstance(subject_type, ErrorType) or isinstance(case_type, ErrorType):
        return None
    compatible = is_assignable(subject_type, case_type, hierarchy) or is_assignable(case_type, subject_type, hierarchy)
    return None if compatible else "CPS-116"


def check_foreach_iterable(iterable_type: Type) -> "str | None":
    """foreach necesita un arreglo cuyo tipo de elemento ya sea conocido."""
    if isinstance(iterable_type, ErrorType):
        return None
    return None if isinstance(iterable_type, ArrayType) else "CPS-120"


def find_dead_code(statements: list[Stmt]) -> list[Stmt]:
    """
    devuelve las statements posteriores a un return/break/continue dentro de la MISMA lista
    (mismo bloque). deteccion lineal, sin cfg -- exactamente lo que pide la regla 13.
    """
    dead: list[Stmt] = []
    terminated = False
    for stmt in statements:
        if terminated:
            dead.append(stmt)
            continue
        if isinstance(stmt, _TERMINATORS):
            terminated = True
    return dead
