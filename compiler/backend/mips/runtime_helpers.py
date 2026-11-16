"""
cuerpos de los helpers de runtime (el contrato esta en helpers.py). cada helper es una
rutina hoja en ensamblador que sigue el abi de siempre: argumentos en la pila (0($sp),
4($sp)...), valor en $v0, $v1 = 0 normal o 1 con el mensaje de error en $v0.

reglas de los cuerpos:
- son hojas: no llaman a nadie (la memoria se pide con la syscall 9 de mars, que no toca
  registros $t), asi que no arman frame ni guardan $ra.
- pueden pisar $t0-$t9, $a0, $v0 y $v1: el que llama ya guardo sus temporales y despues de
  la llamada no confia en ningun registro (ver activation.py).
- se emiten con el MipsBuilder igual que el resto del codigo; nada de texto a mano.

solo se emiten los helpers que el programa usa (RuntimeLibrary.require), en el orden del
catalogo, para que el ensamblador sea chico y determinista. el backend extendido agrega sus
helpers (null, limites) en EXTENDED_RUNTIME, un catalogo mas grande que deja CORE_RUNTIME
intacto.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Callable, Mapping

from compiler.backend.mips.abi import STATUS_ERROR, STATUS_OK, WORD
from compiler.backend.mips.builder import MipsBuilder
from compiler.backend.mips.helpers import HELPERS
from compiler.backend.mips.operands import A0, RA, SP, T, V0, V1, ZERO, Imm, LabelRef, Mem

HelperBody = Callable[[MipsBuilder], None]

# syscalls de mars que usa el runtime
SYSCALL_PRINT_INT = 1
SYSCALL_PRINT_STRING = 4
SYSCALL_SBRK = 9
SYSCALL_EXIT = 10
SYSCALL_PRINT_CHAR = 11

# mensajes de error de runtime: son el valor que recibe la variable de un catch
DIVISION_BY_ZERO = "division entre cero"
UNCAUGHT_PREFIX = "Error no capturado: "
NULL_TEXT = "null"

_INT_BUFFER = 12   # signo + 10 digitos + terminador; ya es multiplo de 4


def _arg(b: MipsBuilder, index: int, into) -> None:
    b.emit("lw", into, Mem(WORD * index, SP), comment=f"arg {index}")


def _return(b: MipsBuilder, status: int = STATUS_OK) -> None:
    b.emit("li", V1, Imm(status))
    b.emit("jr", RA)


def _sbrk_words(b: MipsBuilder, size) -> None:
    """$v0 = bloque nuevo de `size` bytes (registro) redondeado a palabras. pisa $a0."""
    b.emit("addi", A0, size, Imm(WORD - 1))
    b.emit("srl", A0, A0, Imm(2))
    b.emit("sll", A0, A0, Imm(2))
    b.emit("li", V0, Imm(SYSCALL_SBRK))
    b.emit("syscall")


def _strlen(b: MipsBuilder, prefix: str, string, length, cursor, char) -> None:
    """length = cantidad de bytes de `string` antes del terminador."""
    b.emit("move", cursor, string)
    b.mark(f"{prefix}_loop")
    b.emit("lb", char, Mem(0, cursor))
    b.emit_branch("beqz", char, LabelRef(f"{prefix}_done"))
    b.emit("addi", cursor, cursor, Imm(1))
    b.emit_branch("j", LabelRef(f"{prefix}_loop"))
    b.mark(f"{prefix}_done")
    b.emit("sub", length, cursor, string)


# ----------------------------------------------------------------------
# cuerpos
# ----------------------------------------------------------------------

def emit_alloc(b: MipsBuilder) -> None:
    """rt_alloc(bytes) -> puntero a memoria nueva (mars la entrega en cero)."""
    b.mark("rt_alloc")
    _arg(b, 0, T[0])
    _sbrk_words(b, T[0])
    _return(b)


def emit_check_divisor(b: MipsBuilder) -> None:
    """rt_check_divisor(d): falla con DIVISION_BY_ZERO si d == 0."""
    b.mark("rt_check_divisor")
    _arg(b, 0, T[0])
    b.emit_branch("beqz", T[0], LabelRef("rt_check_divisor_fail"))
    b.emit("li", V0, Imm(0))
    _return(b)
    b.mark("rt_check_divisor_fail")
    b.emit("la", V0, LabelRef(b.add_string(DIVISION_BY_ZERO)))
    _return(b, STATUS_ERROR)


def emit_int_to_string(b: MipsBuilder) -> None:
    """
    rt_int_to_string(n) -> string decimal nuevo. trabaja con el valor en negativo para que
    -2147483648 tambien funcione (su positivo no entra en 32 bits).
    """
    n, buf, cursor, m, ten, digit = T[0], T[1], T[2], T[3], T[4], T[5]
    b.mark("rt_int_to_string")
    _arg(b, 0, n)
    b.emit("li", T[6], Imm(_INT_BUFFER))
    _sbrk_words(b, T[6])
    b.emit("move", buf, V0)
    b.emit("addi", cursor, buf, Imm(_INT_BUFFER - 1))
    b.emit("sb", ZERO, Mem(0, cursor), comment="terminador")
    b.emit("li", ten, Imm(10))
    b.emit("move", m, n)
    b.emit_branch("blt", m, ZERO, LabelRef("rt_int_to_string_loop"))
    b.emit("sub", m, ZERO, m, comment="m = -|n|")
    b.mark("rt_int_to_string_loop")
    b.emit("rem", digit, m, ten)
    b.emit("sub", digit, ZERO, digit)
    b.emit("addi", digit, digit, Imm(ord("0")))
    b.emit("addi", cursor, cursor, Imm(-1))
    b.emit("sb", digit, Mem(0, cursor))
    b.emit("div", m, m, ten)
    b.emit_branch("bnez", m, LabelRef("rt_int_to_string_loop"))
    b.emit_branch("bge", n, ZERO, LabelRef("rt_int_to_string_done"))
    b.emit("li", digit, Imm(ord("-")))
    b.emit("addi", cursor, cursor, Imm(-1))
    b.emit("sb", digit, Mem(0, cursor))
    b.mark("rt_int_to_string_done")
    b.emit("move", V0, cursor)
    _return(b)


def emit_concat(b: MipsBuilder) -> None:
    """rt_concat(a, b) -> string nuevo con a seguido de b. un string null se toma como "null"."""
    left, right, cursor, char, len_a, len_b, dest = T[0], T[1], T[2], T[3], T[4], T[5], T[6]
    b.mark("rt_concat")
    _arg(b, 0, left)
    _arg(b, 1, right)
    b.emit("la", T[9], LabelRef(b.add_string(NULL_TEXT)))
    b.emit("movz", left, T[9], left)
    b.emit("movz", right, T[9], right)
    _strlen(b, "rt_concat_len_a", left, len_a, cursor, char)
    _strlen(b, "rt_concat_len_b", right, len_b, cursor, char)
    b.emit("add", T[7], len_a, len_b)
    b.emit("addi", T[7], T[7], Imm(1), comment="terminador")
    _sbrk_words(b, T[7])
    b.emit("move", dest, V0)
    b.mark("rt_concat_copy_a")
    b.emit("lb", char, Mem(0, left))
    b.emit_branch("beqz", char, LabelRef("rt_concat_copy_b"))
    b.emit("sb", char, Mem(0, dest))
    b.emit("addi", left, left, Imm(1))
    b.emit("addi", dest, dest, Imm(1))
    b.emit_branch("j", LabelRef("rt_concat_copy_a"))
    b.mark("rt_concat_copy_b")
    b.emit("lb", char, Mem(0, right))
    b.emit("sb", char, Mem(0, dest), comment="copia tambien el terminador")
    b.emit_branch("beqz", char, LabelRef("rt_concat_done"))
    b.emit("addi", right, right, Imm(1))
    b.emit("addi", dest, dest, Imm(1))
    b.emit_branch("j", LabelRef("rt_concat_copy_b"))
    b.mark("rt_concat_done")
    _return(b)   # $v0 sigue siendo el inicio del bloque


def emit_string_equals(b: MipsBuilder) -> None:
    """rt_string_equals(a, b) -> 1 si tienen el mismo contenido. null solo es igual a null."""
    left, right, char_a, char_b = T[0], T[1], T[2], T[3]
    b.mark("rt_string_equals")
    _arg(b, 0, left)
    _arg(b, 1, right)
    b.emit_branch("beq", left, right, LabelRef("rt_string_equals_yes"))
    b.emit_branch("beqz", left, LabelRef("rt_string_equals_no"))
    b.emit_branch("beqz", right, LabelRef("rt_string_equals_no"))
    b.mark("rt_string_equals_loop")
    b.emit("lb", char_a, Mem(0, left))
    b.emit("lb", char_b, Mem(0, right))
    b.emit_branch("bne", char_a, char_b, LabelRef("rt_string_equals_no"))
    b.emit_branch("beqz", char_a, LabelRef("rt_string_equals_yes"))
    b.emit("addi", left, left, Imm(1))
    b.emit("addi", right, right, Imm(1))
    b.emit_branch("j", LabelRef("rt_string_equals_loop"))
    b.mark("rt_string_equals_yes")
    b.emit("li", V0, Imm(1))
    _return(b)
    b.mark("rt_string_equals_no")
    b.emit("li", V0, Imm(0))
    _return(b)


def emit_uncaught_error(b: MipsBuilder) -> None:
    """rt_uncaught_error(mensaje): imprime 'Error no capturado: <mensaje>' y termina el programa."""
    b.mark("rt_uncaught_error")
    _arg(b, 0, T[0])
    b.emit("la", A0, LabelRef(b.add_string(UNCAUGHT_PREFIX)))
    b.emit("li", V0, Imm(SYSCALL_PRINT_STRING))
    b.emit("syscall")
    b.emit("move", A0, T[0])
    b.emit("li", V0, Imm(SYSCALL_PRINT_STRING))
    b.emit("syscall")
    b.emit("li", A0, Imm(ord("\n")))
    b.emit("li", V0, Imm(SYSCALL_PRINT_CHAR))
    b.emit("syscall")
    b.emit("li", V0, Imm(SYSCALL_EXIT))
    b.emit("syscall")


# catalogo core, en el orden en que se emiten
CORE_RUNTIME: Mapping[str, HelperBody] = MappingProxyType({
    "rt_alloc": emit_alloc,
    "rt_check_divisor": emit_check_divisor,
    "rt_int_to_string": emit_int_to_string,
    "rt_concat": emit_concat,
    "rt_string_equals": emit_string_equals,
    "rt_uncaught_error": emit_uncaught_error,
})


# ----------------------------------------------------------------------
# helpers del backend extendido (persona 3): chequeos de null y de limites
# ----------------------------------------------------------------------

NULL_ACCESS = "acceso a null"
INDEX_OUT_OF_RANGE = "indice fuera de rango"


def emit_check_null(b: MipsBuilder) -> None:
    """rt_check_null(p): falla con NULL_ACCESS si p == 0 (objeto o arreglo sin crear)."""
    b.mark("rt_check_null")
    _arg(b, 0, T[0])
    b.emit_branch("beqz", T[0], LabelRef("rt_check_null_fail"))
    b.emit("li", V0, Imm(0))
    _return(b)
    b.mark("rt_check_null_fail")
    b.emit("la", V0, LabelRef(b.add_string(NULL_ACCESS)))
    _return(b, STATUS_ERROR)


def emit_check_bounds(b: MipsBuilder) -> None:
    """
    rt_check_bounds(arreglo, indice): falla si el arreglo es null (NULL_ACCESS) o si el
    indice no cumple 0 <= indice < longitud (INDEX_OUT_OF_RANGE). la longitud es la palabra 0.
    """
    array, index, length = T[0], T[1], T[2]
    b.mark("rt_check_bounds")
    _arg(b, 0, array)
    _arg(b, 1, index)
    b.emit_branch("beqz", array, LabelRef("rt_check_bounds_null"))
    b.emit("lw", length, Mem(0, array), comment="longitud")
    b.emit_branch("blt", index, ZERO, LabelRef("rt_check_bounds_fail"))
    b.emit_branch("bge", index, length, LabelRef("rt_check_bounds_fail"))
    b.emit("li", V0, Imm(0))
    _return(b)
    b.mark("rt_check_bounds_fail")
    b.emit("la", V0, LabelRef(b.add_string(INDEX_OUT_OF_RANGE)))
    _return(b, STATUS_ERROR)
    b.mark("rt_check_bounds_null")
    b.emit("la", V0, LabelRef(b.add_string(NULL_ACCESS)))
    _return(b, STATUS_ERROR)


# catalogo del backend extendido: el core intacto (mismo orden, lsp) y los chequeos al final
EXTENDED_RUNTIME: Mapping[str, HelperBody] = MappingProxyType({
    **CORE_RUNTIME,
    "rt_check_null": emit_check_null,
    "rt_check_bounds": emit_check_bounds,
})


class RuntimeLibrary:
    """lleva la cuenta de que helpers usa el programa y al final emite solo esos."""

    def __init__(self, bodies: Mapping[str, HelperBody] = CORE_RUNTIME) -> None:
        unknown = set(bodies) - set(HELPERS)
        if unknown:
            raise ValueError(f"helpers sin contrato en helpers.py: {', '.join(sorted(unknown))}")
        self._bodies = dict(bodies)
        self._required: set[str] = set()

    @property
    def required(self) -> frozenset[str]:
        return frozenset(self._required)

    def require(self, name: str) -> None:
        if name not in self._bodies:
            raise ValueError(f"el runtime no implementa el helper {name}")
        self._required.add(name)

    def emit(self, builder: MipsBuilder) -> None:
        for name, body in self._bodies.items():
            if name in self._required:
                body(builder)
