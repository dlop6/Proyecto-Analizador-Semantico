"""
modelo estructurado del codigo intermedio. cada instruccion es un objeto
(opcode, result, arg1, arg2, metadata); el texto que se ve en la gui es solo una
serializacion de esto (serializer.py), nunca se arma tac a mano con strings.

operandos (todos inmutables):
  Temp(index, type)      temporal t<index>, lo reparte solo el TempManager
  Const(value, type)     literal integer/string/boolean/null
  StorageRef             variable, parametro, this o campo (ver runtime/storage.py)
  Label(name)            etiqueta de control (L_...) o de funcion (fn::...)
  ClassRef(name)         clase a instanciar en NEW_OBJ
  MethodRef(name, slot)  entrada de la tabla de despacho para CALL_METHOD
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

from compiler.runtime.storage import StorageRef
from compiler.types import BOOLEAN, INTEGER, NULL, STRING, Type

if TYPE_CHECKING:
    from compiler.ir.opcodes import Opcode


@dataclass(frozen=True, slots=True)
class Temp:
    index: int
    type: Type
    # unidad duenia (0 = codigo global, despues una por funcion). no sale en el texto,
    # pero hace que el t0 de una funcion no se confunda con el t0 de otra
    unit: int = 0

    @property
    def name(self) -> str:
        return f"t{self.index}"


_CONST_PYTHON_TYPES = {INTEGER: int, STRING: str, BOOLEAN: bool}


@dataclass(frozen=True, slots=True)
class Const:
    value: int | str | bool | None
    type: Type

    def __post_init__(self) -> None:
        if self.type == NULL:
            if self.value is not None:
                raise ValueError("una constante null no lleva valor")
            return
        expected = _CONST_PYTHON_TYPES.get(self.type)
        if expected is None:
            raise ValueError(f"no hay constantes de tipo {self.type}")
        # bool es subclase de int en python: hay que descartarlo a mano
        if not isinstance(self.value, expected) or (expected is int and isinstance(self.value, bool)):
            raise ValueError(f"{self.value!r} no es un literal {self.type}")


@dataclass(frozen=True, slots=True)
class Label:
    name: str


@dataclass(frozen=True, slots=True)
class ClassRef:
    name: str


@dataclass(frozen=True, slots=True)
class MethodRef:
    name: str
    slot: int


OperandValue = Union[Temp, Const, StorageRef, Label, ClassRef, MethodRef]


@dataclass(frozen=True, slots=True)
class TACInstruction:
    opcode: "Opcode"
    result: OperandValue | None = None
    arg1: OperandValue | None = None
    arg2: OperandValue | None = None
    metadata: tuple[tuple[str, object], ...] = ()

    def meta(self, key: str, default: object = None) -> object:
        return dict(self.metadata).get(key, default)


@dataclass(frozen=True, slots=True)
class IRFragment:
    """codigo global (fuera de cualquier funcion): el punto de entrada del programa."""
    instructions: tuple[TACInstruction, ...]
    peak_temps: int     # maximo de temporales vivos a la vez
    created_temps: int  # nombres distintos que se llegaron a crear (t0..tN-1)


@dataclass(frozen=True, slots=True)
class IRFunction:
    label: str
    instructions: tuple[TACInstruction, ...]  # arranca con FUNC_BEGIN y termina con FUNC_END
    peak_temps: int
    created_temps: int


@dataclass(frozen=True, slots=True)
class IRProgram:
    entry: IRFragment
    functions: tuple[IRFunction, ...]  # en el orden en que se emitieron
