"""
unico serializador del codigo intermedio a texto. determinista: el mismo IRProgram da
siempre el mismo texto. la forma de cada instruccion sale de opcodes.SIGNATURES; la
gramatica completa esta en docs/INTERMEDIATE_CODE.md.

  - primero el codigo global, despues cada funcion en el orden en que se emitio,
    separados por una linea en blanco
  - FUNC_BEGIN, FUNC_END y LABEL van al margen; el resto con dos espacios
"""
from __future__ import annotations

import json

from compiler.ir.model import ClassRef, Const, IRProgram, Label, MethodRef, OperandValue, TACInstruction, Temp
from compiler.ir.opcodes import SIGNATURES, Opcode
from compiler.runtime.storage import StorageKind, StorageRef

_FLUSH_LEFT = frozenset({Opcode.FUNC_BEGIN, Opcode.FUNC_END, Opcode.LABEL})
_INDENT = "  "


def operand_text(value: OperandValue) -> str:
    if isinstance(value, Temp):
        return value.name
    if isinstance(value, Const):
        if value.value is None:
            return "null"
        if isinstance(value.value, bool):
            return "true" if value.value else "false"
        if isinstance(value.value, str):
            return json.dumps(value.value, ensure_ascii=False)
        return str(value.value)
    if isinstance(value, StorageRef):
        if value.kind is StorageKind.GLOBAL:
            return f"{value.name}@global[{value.slot}]"
        if value.kind is StorageKind.FIELD:
            return f"{value.name}@field[{value.slot}]"
        if value.kind is StorageKind.NONLOCAL:
            return f"{value.name}@frame^{value.lexical_depth}[{value.slot}]"
        return f"{value.name}@frame[{value.slot}]"
    if isinstance(value, (Label, ClassRef)):
        return value.name
    if isinstance(value, MethodRef):
        return f"{value.name}[{value.slot}]"
    raise TypeError(f"operando desconocido: {value!r}")


def instruction_text(instruction: TACInstruction) -> str:
    signature = SIGNATURES[instruction.opcode]
    metadata = dict(instruction.metadata)
    parts: list[str] = []
    if "op" in metadata:
        parts.append(str(metadata["op"]))
    if signature.form == "plain" and instruction.result is not None:
        parts.append(operand_text(instruction.result))
    parts.extend(operand_text(v) for v in (instruction.arg1, instruction.arg2) if v is not None)
    parts.extend(f"{key}={value}" for key, value in instruction.metadata if key != "op")

    text = instruction.opcode.value + (" " + ", ".join(parts) if parts else "")
    if signature.form == "assign":
        text = f"{operand_text(instruction.result)} = {text}"
    return text if instruction.opcode in _FLUSH_LEFT else _INDENT + text


def serialize(program: IRProgram) -> str:
    blocks = [program.entry.instructions] + [fn.instructions for fn in program.functions]
    texts = ["\n".join(instruction_text(i) for i in block) for block in blocks if block]
    return "\n\n".join(texts) + "\n" if texts else ""
