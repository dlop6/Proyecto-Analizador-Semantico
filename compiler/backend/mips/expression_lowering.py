"""
lowering de MOV, BIN, UN y PRINT a mips.

decisiones (ver docs/BACKEND_MIPS.md, seccion del backend core):
- integer es aritmetica de 32 bits en complemento a dos: + y - usan addu/subu/addiu, que
  desbordan dando la vuelta en vez de abortar; * es mul (32 bits bajos).
- / y % truncan hacia cero (div/rem de mips). antes se llama a rt_check_divisor, salvo que
  el divisor sea una constante distinta de cero: la division por cero es un error de
  runtime que sigue la convencion $v1 (no se deja que mars haga trap).
- comparaciones con seq/sne/slt/sle/sgt/sge: dejan 0/1, igual que los boolean.
- `+` con un string es concatenacion (la semantica ya decidio que el otro lado es string,
  integer o boolean): el que no es string se convierte primero dentro del temporal
  resultado, que el tac nunca comparte con un operando.
- `==` / `!=` entre dos string comparan contenido (rt_string_equals); entre cualquier otra
  cosa comparan la palabra (numero, boolean o puntero).
- PRINT imprime el valor y un salto de linea. boolean como true/false y null como "null",
  eligiendo el texto con movz (sin saltos, asi no se cortan los bloques del allocator).

mixin de CoreMipsBackend. usa de la clase concreta: builder, allocator, emitter, type_of,
call_helper, error_target.
"""
from __future__ import annotations

from typing import Callable

from compiler.backend.mips.operands import A0, T, V0, ZERO, Imm, LabelRef, Reg
from compiler.backend.mips.runtime_helpers import (
    NULL_TEXT, SYSCALL_PRINT_CHAR, SYSCALL_PRINT_INT, SYSCALL_PRINT_STRING,
)
from compiler.ir.model import Const, OperandValue, TACInstruction, Temp
from compiler.runtime.storage import StorageRef
from compiler.types import BOOLEAN, INTEGER, STRING, NullType, Type

T8, T9 = T[8], T[9]

_ARITHMETIC = {"+": "addu", "-": "subu", "*": "mul", "/": "div", "%": "rem"}
_COMPARISON = {"==": "seq", "!=": "sne", "<": "slt", "<=": "sle", ">": "sgt", ">=": "sge"}
_DIVISION = frozenset({"/", "%"})
_IMM16 = range(-(2**15), 2**15)
TRUE_TEXT, FALSE_TEXT = "true", "false"


class ExpressionLowering:

    # ------------------------------------------------------------------
    # MOV
    # ------------------------------------------------------------------

    def lower_mov(self, instr: TACInstruction) -> None:
        source, result = instr.arg1, instr.result
        if not isinstance(source, Temp):
            # constante o variable: se carga directo en el registro del destino
            self.assign(result, lambda dest: self.emitter.load_value(source, dest))
            return
        # la fuente se lee primero, asi pedir el registro del destino no la puede expulsar
        src = self.allocator.get_reg(source)
        if isinstance(result, StorageRef):
            self.emitter.store_storage(src, result)
            return
        self.assign(result, lambda dest: self._move(dest, src))

    def _move(self, dest: Reg, src: Reg) -> None:
        if dest != src:
            self.builder.emit("move", dest, src)

    # ------------------------------------------------------------------
    # BIN
    # ------------------------------------------------------------------

    def lower_bin(self, instr: TACInstruction) -> None:
        op = instr.meta("op")
        left, right = instr.arg1, instr.arg2
        if op == "+" and STRING in (self.type_of(left), self.type_of(right)):
            self._concat(instr)
        elif op in ("==", "!=") and self.type_of(left) == STRING and self.type_of(right) == STRING:
            self._string_equality(instr, negate=op == "!=")
        elif op in _ARITHMETIC or op in _COMPARISON:
            if op in _DIVISION and not _nonzero_constant(right):
                self.call_helper("rt_check_divisor", (right,), on_error=self.error_target())
            self._register_operation(instr.result, op, left, right)
        else:
            raise ValueError(f"operador binario sin lowering: {op!r}")

    def _register_operation(self, result, op: str, left: OperandValue, right: OperandValue) -> None:
        # + y - contra una constante de 16 bits: una sola instruccion con inmediato
        if op == "+" and _small_int(left) and not _small_int(right):
            left, right = right, left
        if op in ("+", "-") and _small_int(right):
            amount = right.value if op == "+" else -right.value
            if amount in _IMM16:
                a = self.emitter.value_in_reg(left, T8)
                self.assign(result, lambda dest: self.builder.emit("addiu", dest, a, Imm(amount)))
                return
        a = self.emitter.value_in_reg(left, T8)
        b = self.emitter.value_in_reg(right, T9)
        mnemonic = _ARITHMETIC.get(op) or _COMPARISON[op]
        self.assign(result, lambda dest: self.builder.emit(mnemonic, dest, a, b))

    def _concat(self, instr: TACInstruction) -> None:
        result = self._temp_result(instr, "una concatenacion")
        pieces = []
        for operand in (instr.arg1, instr.arg2):
            kind = self.type_of(operand)
            if kind == STRING:
                pieces.append(operand)
                continue
            # a lo sumo un lado no es string (si no, no seria concatenacion): se convierte en result
            if kind == INTEGER:
                self.call_helper("rt_int_to_string", (operand,), result)
            elif kind == BOOLEAN:
                self._boolean_text(operand, result)
            else:
                raise ValueError(f"no se puede concatenar un {kind} con un string")
            pieces.append(result)
        self.call_helper("rt_concat", tuple(pieces), result)

    def _boolean_text(self, operand: OperandValue, result: Temp) -> None:
        value = self.emitter.value_in_reg(operand, T8)
        self.assign(result, lambda dest: self._select_text(dest, value, TRUE_TEXT, FALSE_TEXT))

    def _string_equality(self, instr: TACInstruction, negate: bool) -> None:
        result = self._temp_result(instr, "una comparacion de strings")
        self.call_helper("rt_string_equals", (instr.arg1, instr.arg2), result)
        if negate:
            reg = self.allocator.get_reg(result)
            self.builder.emit("xori", reg, reg, Imm(1))
            self.allocator.mark_dirty(result)

    # ------------------------------------------------------------------
    # UN
    # ------------------------------------------------------------------

    def lower_un(self, instr: TACInstruction) -> None:
        op = instr.meta("op")
        src = self.emitter.value_in_reg(instr.arg1, T8)
        if op == "-":
            self.assign(instr.result, lambda dest: self.builder.emit("subu", dest, ZERO, src))
        elif op == "!":
            self.assign(instr.result, lambda dest: self.builder.emit("xori", dest, src, Imm(1)))
        else:
            raise ValueError(f"operador unario sin lowering: {op!r}")

    # ------------------------------------------------------------------
    # PRINT
    # ------------------------------------------------------------------

    def lower_print(self, instr: TACInstruction) -> None:
        value = instr.arg1
        kind = self.type_of(value)
        if kind == INTEGER:
            self.emitter.load_value(value, A0)
            self._syscall(SYSCALL_PRINT_INT)
        else:
            if kind == STRING:
                self.emitter.load_value(value, A0)
                if not isinstance(value, Const):   # un literal nunca es null
                    self._select_text(A0, A0, None, NULL_TEXT)
            elif kind == BOOLEAN:
                self._select_text(A0, self.emitter.value_in_reg(value, T8), TRUE_TEXT, FALSE_TEXT)
            elif isinstance(kind, NullType):
                self.builder.emit("la", A0, LabelRef(self.builder.add_string(NULL_TEXT)))
            else:
                self.print_reference(kind, value)
            self._syscall(SYSCALL_PRINT_STRING)
        self.builder.emit("li", A0, Imm(ord("\n")))
        self._syscall(SYSCALL_PRINT_CHAR)

    def print_reference(self, kind: Type, value: OperandValue) -> None:
        """
        deja en $a0 el texto de un objeto o arreglo: "null" si es null, si no "<Tipo>". el
        backend extendido puede sobreescribirlo; el core no inspecciona el heap.
        """
        self._select_text(A0, self.emitter.value_in_reg(value, T8), f"<{kind}>", NULL_TEXT)

    # ------------------------------------------------------------------
    # comunes
    # ------------------------------------------------------------------

    def assign(self, result, produce: Callable[[Reg], object]) -> None:
        """produce(dest) deja el valor en `dest`; result es un temporal o una variable."""
        if isinstance(result, Temp):
            reg = self.allocator.get_reg(result, load=False)
            produce(reg)
            self.allocator.mark_dirty(result)
        elif isinstance(result, StorageRef):
            produce(T8)
            self.emitter.store_storage(T8, result)
        else:
            raise ValueError(f"destino invalido: {result!r}")

    def _select_text(self, dest: Reg, condition: Reg, if_true: str | None, if_false: str) -> None:
        """
        dest = condition != 0 ? if_true : if_false, con movz y sin saltos. if_true None quiere
        decir que dest ya tiene el valor para el caso verdadero (el mismo puntero).
        """
        if if_true is not None:
            if dest == condition:
                raise ValueError("dest y condition no pueden ser el mismo registro si se carga if_true")
            self.builder.emit("la", dest, LabelRef(self.builder.add_string(if_true)))
        self.builder.emit("la", T9, LabelRef(self.builder.add_string(if_false)))
        self.builder.emit("movz", dest, T9, condition)

    def _syscall(self, code: int) -> None:
        self.builder.emit("li", V0, Imm(code))
        self.builder.emit("syscall")

    @staticmethod
    def _temp_result(instr: TACInstruction, what: str) -> Temp:
        if not isinstance(instr.result, Temp):
            raise ValueError(f"{what} tiene que dejar su resultado en un temporal, no en {instr.result!r}")
        return instr.result


def _small_int(operand: OperandValue) -> bool:
    return isinstance(operand, Const) and operand.type == INTEGER and operand.value in _IMM16


def _nonzero_constant(operand: OperandValue) -> bool:
    return isinstance(operand, Const) and operand.type == INTEGER and operand.value != 0
