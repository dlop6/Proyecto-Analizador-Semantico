"""
operandos del ensamblador mips: registros, inmediatos, etiquetas y direcciones de memoria.
todo inmutable y validado al construirse, asi un operando mal formado falla donde se crea
y no cuando mars lo rechaza.

tambien vive aca el mangling de etiquetas: las del ir (fn::A.m, fn::f.g#2) no son
etiquetas validas en mips ('::' no se acepta y '#' abre un comentario).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_REGISTER_NAMES = frozenset(
    ["$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3", "$gp", "$sp", "$fp", "$ra"]
    + [f"$t{i}" for i in range(10)]
    + [f"$s{i}" for i in range(8)]
)
_LABEL = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_CONTROL_LABEL = re.compile(r"^L_[a-z_]+_\d+$")
_FUNCTION_PREFIX = "fn::"
_INT32_MIN, _INT32_MAX = -(2**31), 2**31 - 1

GLOBALS_LABEL = "__globals"


@dataclass(frozen=True, slots=True)
class Reg:
    name: str

    def __post_init__(self) -> None:
        if self.name not in _REGISTER_NAMES:
            raise ValueError(f"registro desconocido: {self.name!r}")

    def __str__(self) -> str:
        return self.name


ZERO, AT, V0, V1, A0 = Reg("$zero"), Reg("$at"), Reg("$v0"), Reg("$v1"), Reg("$a0")
SP, FP, RA = Reg("$sp"), Reg("$fp"), Reg("$ra")
T = tuple(Reg(f"$t{i}") for i in range(10))

# $t0-$t7 los reparte el allocator; $t8-$t9 son scratch del backend (nunca se asignan a un temporal)
POOL = T[:8]
SCRATCH = T[8:]
RESERVED = (ZERO, AT, V0, V1, A0, SP, FP, RA)
CALLER_SAVED = POOL + SCRATCH


@dataclass(frozen=True, slots=True)
class Imm:
    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValueError(f"un inmediato tiene que ser int, no {self.value!r}")
        if not _INT32_MIN <= self.value <= _INT32_MAX:
            raise ValueError(f"inmediato fuera de 32 bits: {self.value}")

    def __str__(self) -> str:
        return str(self.value)


def validate_label(name: str) -> str:
    if not isinstance(name, str) or not _LABEL.match(name):
        raise ValueError(f"etiqueta invalida para mips: {name!r}")
    return name


@dataclass(frozen=True, slots=True)
class LabelRef:
    name: str

    def __post_init__(self) -> None:
        validate_label(self.name)

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class Mem:
    """offset($base)."""
    offset: int
    base: Reg

    def __post_init__(self) -> None:
        if isinstance(self.offset, bool) or not isinstance(self.offset, int):
            raise ValueError(f"offset invalido: {self.offset!r}")
        # el campo de offset de lw/sw es de 16 bits con signo
        if not -(2**15) <= self.offset < 2**15:
            raise ValueError(f"offset fuera de 16 bits: {self.offset}")

    def __str__(self) -> str:
        return f"{self.offset}({self.base})"


@dataclass(frozen=True, slots=True)
class LabelMem:
    """etiqueta+offset, para globales (__globals+8)."""
    label: str
    offset: int = 0

    def __post_init__(self) -> None:
        validate_label(self.label)
        if isinstance(self.offset, bool) or not isinstance(self.offset, int) or self.offset < 0:
            raise ValueError(f"offset invalido: {self.offset!r}")

    def __str__(self) -> str:
        return f"{self.label}+{self.offset}" if self.offset else self.label


Operand = Reg | Imm | LabelRef | Mem | LabelMem


# ----------------------------------------------------------------------
# mangling de etiquetas
# ----------------------------------------------------------------------

def mangle_label(ir_label: str) -> str:
    """
    etiqueta del ir -> etiqueta valida en mips, inyectiva. las de control (L_x_n) ya son
    validas y no cambian; las de funcion pierden el 'fn::' por 'fn_' y escapan:
    '_' -> '_u', '.' -> '_d', '#' -> '_h' (un '_' solo nunca queda suelto, por eso es inyectiva).
    """
    if _CONTROL_LABEL.match(ir_label):
        return ir_label
    if not ir_label.startswith(_FUNCTION_PREFIX):
        raise ValueError(f"etiqueta del ir desconocida: {ir_label!r}")
    body = ir_label[len(_FUNCTION_PREFIX):]
    escaped = body.replace("_", "_u").replace(".", "_d").replace("#", "_h")
    return validate_label(f"fn_{escaped}")


def string_label(index: int) -> str:
    return f"str_{index}"


def vtable_label(class_name: str) -> str:
    return validate_label(f"vt_{class_name}")
