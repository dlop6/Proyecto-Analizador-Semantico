"""
reglas de tipos para arreglos: literales y acceso por indice. parte de la semantica
extendida (persona 3).

funciones puras, mismo patron que expression_rules.py: reciben tipos ya inferidos (nunca
el ast) y devuelven el tipo resultante junto con un codigo de diagnostico opcional. no
escriben diagnosticos ni conocen diagnostics.py.
"""
from __future__ import annotations

from compiler.types import (
    ArrayType, ClassHierarchy, EMPTY_ARRAY, EmptyArrayType, ERROR, ErrorType, INTEGER,
    Type, common_type,
)


def check_array_literal(
    element_types: list[Type], hierarchy: ClassHierarchy | None = None,
) -> tuple[Type, "str | None"]:
    """
    tipo de un literal `[e1, e2, ...]`: el supertipo comun mas especifico de todos sus
    elementos, reduciendo par a par con common_type -- exactamente la misma logica que
    expression_rules.check_ternary usa para 2 ramas, generalizada a N elementos. arrays
    anidados salen gratis: si los elementos ya son ArrayType (porque el visitor los
    infirio primero, de adentro hacia afuera), common_type los combina igual que
    cualquier otro tipo.

    un literal vacio (`[]`) da EMPTY_ARRAY, el tipo comodin ya definido en types.py.
    """
    if not element_types:
        return EMPTY_ARRAY, None
    if any(isinstance(t, ErrorType) for t in element_types):
        return ERROR, None  # se absorbe en silencio, ya se reporto mas abajo en el arbol

    result = element_types[0]
    for candidate in element_types[1:]:
        joined = common_type(result, candidate, hierarchy)
        if joined is None:
            return ERROR, "CPS-207"
        result = joined
    return ArrayType(result), None


def check_index_access(collection_type: Type) -> tuple[Type, "str | None"]:
    """
    tipo de `coleccion[indice]` a partir del tipo ya inferido de `coleccion` (el tipo del
    indice se valida aparte, en el visitor, con CPS-205: siempre debe ser integer).
    """
    if isinstance(collection_type, ErrorType):
        return ERROR, None
    if isinstance(collection_type, ArrayType):
        return collection_type.element, None
    # EmptyArrayType: indexar un arreglo vacio (`[][0]`) es raro pero no debe crashear,
    # se absorbe en silencio -- no hay forma de saber el tipo del elemento.
    if isinstance(collection_type, EmptyArrayType):
        return ERROR, None
    return ERROR, "CPS-206"


def is_valid_index_type(index_type: Type) -> bool:
    """el indice de un arreglo debe ser integer (regla 9: sin analisis estatico de rangos)."""
    return isinstance(index_type, ErrorType) or index_type == INTEGER
