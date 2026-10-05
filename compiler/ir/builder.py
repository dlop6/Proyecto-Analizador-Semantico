"""
unico camino para construir un IRProgram. solo se crea desde un RuntimeLayout, y un
RuntimeLayout solo existe para resultados semanticos sin errores: asi un programa ir
nunca puede existir si hubo errores lexicos, sintacticos o semanticos.

  builder = IRBuilder(layout)
  t = builder.new_temp(INTEGER)
  builder.emit(Opcode.BIN, t, a, b, op="*")
  builder.release_temp(t)
  program = builder.build()

cada unidad (el codigo global y cada funcion) tiene su propio TempManager. las
funciones se abren con begin_function y se cierran con end_function; una anidada se
puede abrir mientras la de afuera sigue abierta, sin interrumpirle el codigo.

lo que se valida al emitir: firma del opcode (opcodes.SIGNATURES), roles de cada
operando, metadata, que todo temporal usado este vivo, que las etiquetas sean de esta
compilacion y que los StorageRef sean visibles desde la unidad actual. al cerrar una
unidad no pueden quedar temporales vivos; al construir, todo salto tiene que caer en
una etiqueta marcada en su misma unidad y todo CALL en una funcion emitida.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from compiler.ir.model import (
    ClassRef, Const, IRFragment, IRFunction, IRProgram, Label, MethodRef, OperandValue,
    TACInstruction, Temp,
)
from compiler.ir.opcodes import (
    BINARY_OPERATORS, JUMPS, SIGNATURES, STRUCTURAL, UNARY_OPERATORS, Opcode, Operand,
)
from compiler.ir.temp_manager import TempManager
from compiler.runtime.runtime_layout import RuntimeLayout
from compiler.runtime.storage import FRAME_KINDS, StorageKind, StorageRef
from compiler.symbols import FunctionSymbol
from compiler.types import Type


class IRError(Exception):
    """instruccion o secuencia de emision que viola el contrato del codigo intermedio."""


@dataclass
class _Unit:
    function: FunctionSymbol | None  # None = codigo global
    temps: TempManager
    instructions: list[TACInstruction] = field(default_factory=list)


def _is_storage(value, *, field_slot: bool) -> bool:
    return isinstance(value, StorageRef) and (value.kind is StorageKind.FIELD) == field_slot


_ROLE_CHECKS = {
    "value": lambda v: isinstance(v, (Temp, Const)) or _is_storage(v, field_slot=False),
    "dest": lambda v: isinstance(v, Temp) or _is_storage(v, field_slot=False),
    "label": lambda v: isinstance(v, Label) and v.name.startswith("L_"),
    "function": lambda v: isinstance(v, Label) and v.name.startswith("fn::"),
    "class": lambda v: isinstance(v, ClassRef),
    "method": lambda v: isinstance(v, MethodRef),
    "field": lambda v: _is_storage(v, field_slot=True),
}


class IRBuilder:
    def __init__(self, layout: RuntimeLayout) -> None:
        if not isinstance(layout, RuntimeLayout):
            raise IRError("el builder necesita el RuntimeLayout de una semantica exitosa")
        self._layout = layout
        self._units_created = 1
        self._stack: list[_Unit] = [_Unit(function=None, temps=TempManager(unit=0))]
        self._functions: list[IRFunction] = []
        self._begun: set[str] = set()
        self._all_marked: set[str] = set()

    @property
    def layout(self) -> RuntimeLayout:
        return self._layout

    # ------------------------------------------------------------------
    # temporales y etiquetas
    # ------------------------------------------------------------------

    def new_temp(self, type_: Type) -> Temp:
        return self._unit.temps.acquire(type_)

    def release_temp(self, temp: Temp) -> None:
        self._unit.temps.release(temp)

    def new_label(self, prefix: str) -> Label:
        return Label(self._layout.labels.new_label(prefix))

    def mark_label(self, label: Label) -> None:
        self._check_operand(Operand("label"), label, "LABEL")
        if label.name in self._all_marked:
            raise IRError(f"la etiqueta {label.name} ya fue marcada")
        self._all_marked.add(label.name)
        self._append(Opcode.LABEL, None, label, None, ())

    # ------------------------------------------------------------------
    # funciones
    # ------------------------------------------------------------------

    def begin_function(self, fn: FunctionSymbol) -> None:
        record = fn.activation_record
        if record is None or fn.label not in self._layout.records:
            raise IRError(f"'{fn.name}' no tiene registro de activacion en este layout")
        if fn.label in self._begun:
            raise IRError(f"la funcion {fn.label} ya fue emitida")
        self._begun.add(fn.label)
        self._stack.append(_Unit(function=fn, temps=TempManager(unit=self._units_created)))
        self._units_created += 1
        self._append(Opcode.FUNC_BEGIN, None, Label(fn.label), None, (("frame", record.frame_size),))

    def end_function(self) -> IRFunction:
        unit = self._unit
        if unit.function is None:
            raise IRError("end_function sin una funcion abierta")
        self._require_no_live_temps(unit)
        self._append(Opcode.FUNC_END, None, Label(unit.function.label), None, (("temps", unit.temps.peak),))
        self._stack.pop()
        function = IRFunction(
            label=unit.function.label, instructions=tuple(unit.instructions),
            peak_temps=unit.temps.peak, created_temps=unit.temps.created,
        )
        self._functions.append(function)
        return function

    # ------------------------------------------------------------------
    # emision
    # ------------------------------------------------------------------

    def emit(
        self,
        opcode: Opcode,
        result: OperandValue | None = None,
        arg1: OperandValue | None = None,
        arg2: OperandValue | None = None,
        **metadata: object,
    ) -> TACInstruction:
        if opcode in STRUCTURAL:
            raise IRError(f"{opcode.value} no se emite a mano: usa mark_label / begin_function / end_function")
        signature = SIGNATURES[opcode]
        for name, spec, value in (("result", signature.result, result), ("arg1", signature.arg1, arg1),
                                  ("arg2", signature.arg2, arg2)):
            if spec is None:
                if value is not None:
                    raise IRError(f"{opcode.value} no lleva {name}")
            elif value is None:
                if spec.required:
                    raise IRError(f"{opcode.value} necesita {name}")
            else:
                self._check_operand(spec, value, opcode.value)
        return self._append(opcode, result, arg1, arg2, self._check_metadata(opcode, metadata))

    def build(self) -> IRProgram:
        if len(self._stack) != 1:
            raise IRError(f"quedo abierta la funcion {self._unit.function.label}")
        entry = self._stack[0]
        self._require_no_live_temps(entry)
        emitted = {fn.label for fn in self._functions}
        for instructions in [entry.instructions] + [fn.instructions for fn in self._functions]:
            marked = {i.arg1.name for i in instructions if i.opcode is Opcode.LABEL}
            for instruction in instructions:
                if instruction.opcode in JUMPS:
                    target = instruction.arg2 if instruction.opcode in (Opcode.IF_TRUE, Opcode.IF_FALSE) else instruction.arg1
                    if target.name not in marked:
                        raise IRError(f"{instruction.opcode.value} salta a {target.name}, que no esta marcada en su unidad")
                elif instruction.opcode is Opcode.CALL and instruction.arg1.name not in emitted:
                    raise IRError(f"CALL a {instruction.arg1.name}, que nunca se emitio")
        return IRProgram(
            entry=IRFragment(tuple(entry.instructions), entry.temps.peak, entry.temps.created),
            functions=tuple(self._functions),
        )

    # ------------------------------------------------------------------
    # validaciones
    # ------------------------------------------------------------------

    @property
    def _unit(self) -> _Unit:
        return self._stack[-1]

    def _append(self, opcode, result, arg1, arg2, metadata) -> TACInstruction:
        instruction = TACInstruction(opcode, result, arg1, arg2, metadata)
        self._unit.instructions.append(instruction)
        return instruction

    def _require_no_live_temps(self, unit: _Unit) -> None:
        if unit.temps.live_count:
            where = unit.function.label if unit.function else "el codigo global"
            raise IRError(f"quedaron {unit.temps.live_count} temporales vivos al cerrar {where}")

    def _check_operand(self, spec: Operand, value: OperandValue, opcode: str) -> None:
        if not _ROLE_CHECKS[spec.role](value):
            raise IRError(f"{opcode}: {value!r} no sirve como {spec.role}")
        if isinstance(value, Temp) and not self._unit.temps.is_live(value):
            raise IRError(f"{opcode}: {value.name} no esta vivo en esta unidad")
        if isinstance(value, Label) and not self._layout.labels.owns(value.name):
            raise IRError(f"{opcode}: la etiqueta {value.name} no es de esta compilacion")
        if isinstance(value, StorageRef):
            self._check_storage(value, opcode)

    def _check_storage(self, ref: StorageRef, opcode: str) -> None:
        fn = self._unit.function
        if ref.kind is StorageKind.GLOBAL:
            if ref.slot >= self._layout.globals_count:
                raise IRError(f"{opcode}: no existe el slot global {ref.slot}")
        elif ref.kind in FRAME_KINDS:
            if fn is None or ref.slot >= fn.activation_record.frame_size:
                raise IRError(f"{opcode}: {ref.name} no esta en el frame actual")
            if ref.kind is StorageKind.THIS and not fn.activation_record.is_method:
                raise IRError(f"{opcode}: this solo existe en metodos y constructores")
        elif ref.kind is StorageKind.NONLOCAL:
            record = fn.activation_record if fn is not None else None
            if record is None or not record.static_link or ref.lexical_depth > record.lexical_depth:
                raise IRError(f"{opcode}: {ref.name} no es alcanzable por static link desde aca")

    def _check_metadata(self, opcode: Opcode, metadata: dict[str, object]) -> tuple[tuple[str, object], ...]:
        signature = SIGNATURES[opcode]
        allowed = {m.key for m in signature.meta}
        unknown = set(metadata) - allowed
        if unknown:
            raise IRError(f"{opcode.value} no acepta metadata {sorted(unknown)}")
        ordered = []
        for spec in signature.meta:
            if spec.key not in metadata:
                if spec.required:
                    raise IRError(f"{opcode.value} necesita {spec.key}=")
                continue
            value = metadata[spec.key]
            if spec.key == "op":
                operators = BINARY_OPERATORS if opcode is Opcode.BIN else UNARY_OPERATORS
                if value not in operators:
                    raise IRError(f"{opcode.value} no acepta el operador {value!r}")
            elif not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise IRError(f"{opcode.value}: {spec.key} tiene que ser un entero >= 0")
            ordered.append((spec.key, value))
        return tuple(ordered)
