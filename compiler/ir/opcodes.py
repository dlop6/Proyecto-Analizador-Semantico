"""
contrato del codigo intermedio: los unicos opcodes permitidos y la firma de cada uno.

SIGNATURES es la fuente unica que usan el builder (para validar) y el serializer (para
escribir texto). agregar un opcode = agregar una entrada aca y documentarla en
docs/INTERMEDIATE_CODE.md; no hay que tocar ni builder ni serializer.

roles de operando (los traduce el builder a validaciones concretas):
  value     Temp | Const | StorageRef que no sea FIELD   (algo que se lee)
  dest      Temp | StorageRef que no sea FIELD           (algo donde se escribe)
  label     Label de control (L_...)
  function  Label de funcion (fn::...)
  class     ClassRef
  method    MethodRef
  field     StorageRef FIELD                             (slot de un atributo)

formas de texto:
  assign    <result> = OPCODE args...      (ej. t0 = BIN *, b, c)
  plain     OPCODE [result,] args...       (ej. MOV x, t1 / CALL t0, fn::f, argc=1)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Opcode(Enum):
    # datos
    MOV = "MOV"
    BIN = "BIN"
    UN = "UN"
    PRINT = "PRINT"
    # control
    LABEL = "LABEL"
    GOTO = "GOTO"
    IF_TRUE = "IF_TRUE"
    IF_FALSE = "IF_FALSE"
    # funciones
    FUNC_BEGIN = "FUNC_BEGIN"
    FUNC_END = "FUNC_END"
    ARG = "ARG"
    CALL = "CALL"
    RETURN = "RETURN"
    # arreglos
    NEW_ARR = "NEW_ARR"
    ARR_GET = "ARR_GET"
    ARR_SET = "ARR_SET"
    LEN = "LEN"
    # objetos
    NEW_OBJ = "NEW_OBJ"
    GET_FIELD = "GET_FIELD"
    SET_FIELD = "SET_FIELD"
    CALL_METHOD = "CALL_METHOD"
    # excepciones
    TRY_BEGIN = "TRY_BEGIN"
    TRY_END = "TRY_END"
    CATCH = "CATCH"


# && y || no estan a proposito: se bajan con cortocircuito (saltos), nunca como BIN
BINARY_OPERATORS = frozenset({"+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">="})
UNARY_OPERATORS = frozenset({"-", "!"})


@dataclass(frozen=True, slots=True)
class Operand:
    role: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class Meta:
    key: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class Signature:
    form: str                          # "assign" | "plain"
    result: Operand | None = None
    arg1: Operand | None = None
    arg2: Operand | None = None
    meta: tuple[Meta, ...] = ()        # "op" siempre va primero y se escribe como operando


_VALUE, _DEST = Operand("value"), Operand("dest")
_OP = (Meta("op"),)

SIGNATURES: dict[Opcode, Signature] = {
    Opcode.MOV: Signature("plain", result=_DEST, arg1=_VALUE),
    Opcode.BIN: Signature("assign", result=_DEST, arg1=_VALUE, arg2=_VALUE, meta=_OP),
    Opcode.UN: Signature("assign", result=_DEST, arg1=_VALUE, meta=_OP),
    Opcode.PRINT: Signature("plain", arg1=_VALUE),

    Opcode.LABEL: Signature("plain", arg1=Operand("label")),
    Opcode.GOTO: Signature("plain", arg1=Operand("label")),
    Opcode.IF_TRUE: Signature("plain", arg1=_VALUE, arg2=Operand("label")),
    Opcode.IF_FALSE: Signature("plain", arg1=_VALUE, arg2=Operand("label")),

    Opcode.FUNC_BEGIN: Signature("plain", arg1=Operand("function"), meta=(Meta("frame"),)),
    Opcode.FUNC_END: Signature("plain", arg1=Operand("function"), meta=(Meta("temps"),)),
    Opcode.ARG: Signature("plain", arg1=_VALUE),
    Opcode.CALL: Signature(
        "plain", result=Operand("dest", required=False), arg1=Operand("function"),
        meta=(Meta("argc"), Meta("link", required=False)),
    ),
    Opcode.RETURN: Signature("plain", arg1=Operand("value", required=False)),

    Opcode.NEW_ARR: Signature("assign", result=_DEST, arg1=_VALUE),
    Opcode.ARR_GET: Signature("assign", result=_DEST, arg1=_VALUE, arg2=_VALUE),
    Opcode.ARR_SET: Signature("plain", result=_DEST, arg1=_VALUE, arg2=_VALUE),
    Opcode.LEN: Signature("assign", result=_DEST, arg1=_VALUE),

    Opcode.NEW_OBJ: Signature("assign", result=_DEST, arg1=Operand("class"), meta=(Meta("fields"),)),
    Opcode.GET_FIELD: Signature("assign", result=_DEST, arg1=_VALUE, arg2=Operand("field")),
    Opcode.SET_FIELD: Signature("plain", result=_DEST, arg1=Operand("field"), arg2=_VALUE),
    Opcode.CALL_METHOD: Signature(
        "plain", result=Operand("dest", required=False), arg1=_VALUE, arg2=Operand("method"),
        meta=(Meta("argc"),),
    ),

    Opcode.TRY_BEGIN: Signature("plain", arg1=Operand("label")),
    Opcode.TRY_END: Signature("plain"),
    Opcode.CATCH: Signature("plain", arg1=_DEST),
}

# saltos cuyo destino tiene que estar marcado dentro de la misma unidad (funcion o global)
JUMPS = frozenset({Opcode.GOTO, Opcode.IF_TRUE, Opcode.IF_FALSE, Opcode.TRY_BEGIN})
# los emite el builder solo, con begin_function / end_function
STRUCTURAL = frozenset({Opcode.FUNC_BEGIN, Opcode.FUNC_END, Opcode.LABEL})
