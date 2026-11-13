"""
convencion de llamada (ABI) del backend mips. una sola para todo: funciones del usuario,
metodos, constructores y helpers de runtime. las constantes de aca son el contrato que
comparten los tres lowerers; el pdf del proyecto fija los offsets del frame.

pila (crece hacia abajo). el que llama reserva el bloque de argumentos y lo limpia:

    mayor direccion
    | arg n-1        |   8+4(n-1)($fp)
    | ...            |
    | arg 0          |   8($fp)        orden: static link, this, explicitos
    | ra guardado    |   4($fp)
    | fp viejo       |   0($fp)   <- $fp
    | locales        |   -4($fp), -8($fp)...
    | home de temps  |
    | args pendientes|   (ver frame_planner)
    menor direccion  <- $sp

retorno: $v0 = valor; $v1 = 0 normal, $v1 = 1 error (el mensaje queda en $v0).
"""
from __future__ import annotations

from compiler.backend.mips.operands import mangle_label
from compiler.runtime.activation_records import ClassLayout

WORD = 4

# valores
TRUE, FALSE, NULL = 1, 0, 0

# frame
OLD_FP_OFFSET = 0
RA_OFFSET = 4
FIRST_ARG_OFFSET = 8

# convencion de retorno
STATUS_OK, STATUS_ERROR = 0, 1

# datos en el heap: arreglo = [longitud][elementos...]; objeto = [vtable][campos...]
ARRAY_LENGTH_OFFSET = 0
ARRAY_FIRST_ELEMENT_OFFSET = 4
OBJECT_VTABLE_OFFSET = 0
OBJECT_FIRST_FIELD_OFFSET = 4


def field_offset(slot: int) -> int:
    """offset de un campo dentro del objeto (la palabra 0 es la vtable)."""
    if slot < 0:
        raise ValueError("el slot de un campo no puede ser negativo")
    return OBJECT_FIRST_FIELD_OFFSET + WORD * slot


def vtable_entries(class_layout: ClassLayout) -> tuple[str, ...]:
    """
    etiquetas mips de la tabla de despacho de una clase, en orden de slot: es el contenido de
    su .word. el constructor no esta (se llama directo) y un metodo heredado apunta a la
    implementacion del ancestro, tal cual lo resolvio el layout.
    """
    return tuple(mangle_label(entry.impl_label) for entry in class_layout.methods)


def object_size(field_count: int) -> int:
    return OBJECT_FIRST_FIELD_OFFSET + WORD * field_count


def array_size(length: int) -> int:
    return ARRAY_FIRST_ELEMENT_OFFSET + WORD * length


def incoming_arg_offset(index: int) -> int:
    """offset (desde $fp) del argumento `index` contando desde 0 en el orden de la convencion."""
    if index < 0:
        raise ValueError("el indice de argumento no puede ser negativo")
    return FIRST_ARG_OFFSET + WORD * index


def local_area_offset(index: int) -> int:
    """offset (desde $fp) de la casilla `index` del area bajo $fp: -4, -8, -12..."""
    if index < 0:
        raise ValueError("el indice de casilla no puede ser negativo")
    return -WORD * (index + 1)
