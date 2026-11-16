"""
lowering de NEW_ARR, ARR_GET, ARR_SET y LEN a mips (persona 3).

layout (abi.py): un arreglo es un puntero al heap con [longitud][elem 0][elem 1]...; cada
elemento ocupa una palabra (integer, boolean, string o referencia), asi que una matriz es
un arreglo cuyos elementos son punteros a otros arreglos y no necesita nada especial.

- NEW_ARR t, n: el tac solo lo emite para literales, con n constante; el tamaño en bytes
  se calcula al compilar (validate() rechaza n negativo o desmedido) y se pide a rt_alloc,
  que entrega la memoria en cero. despues se escribe la longitud en la palabra 0.
- ARR_GET / ARR_SET: antes de tocar memoria se llama a rt_check_bounds (null, indice < 0 o
  >= longitud). el error sigue la convencion $v1 y salta a error_target(): el catch activo,
  la salida de la funcion o main_error.
- un ARR_SET con indice constante sobre el arreglo que se acaba de crear (la inicializacion
  de un literal: `t = NEW_ARR 3 ; ARR_SET t, 0, ...`) no se chequea: la longitud se conoce
  al compilar. vale mientras el temporal no se redefina y dentro del mismo bloque (una
  etiqueta olvida todo, ver forget_known_lengths).
- LEN: rt_check_null y despues la palabra 0. foreach (ya bajado a LEN + ARR_GET + saltos
  por el tac) no necesita nada propio.

mixin del backend extendido. usa de la clase concreta: builder, allocator, emitter, assign,
call_helper, error_target.
"""
from __future__ import annotations

from compiler.backend.mips.abi import ARRAY_FIRST_ELEMENT_OFFSET, ARRAY_LENGTH_OFFSET, WORD, array_size
from compiler.backend.mips.operands import T, Imm, Mem, Reg
from compiler.ir.model import Const, OperandValue, TACInstruction, Temp
from compiler.ir.opcodes import Opcode
from compiler.types import INTEGER

T8, T9 = T[8], T[9]

# un literal de mas elementos que esto no es "razonable" para el heap de mars (4 MB)
MAX_ARRAY_LENGTH = 1 << 16
_IMM16_MAX = 2**15 - 1
# opcodes cuyo `result` es el objeto/arreglo que se escribe (se lee), no una definicion
_RESULT_IS_READ = frozenset({Opcode.ARR_SET, Opcode.SET_FIELD})


def new_array_problem(length: OperandValue) -> str | None:
    """por que un NEW_ARR no se puede bajar, o None si se puede (lo usa validate())."""
    if not (isinstance(length, Const) and length.type == INTEGER):
        return f"NEW_ARR espera una longitud integer constante, no {length!r}"
    if not 0 <= length.value <= MAX_ARRAY_LENGTH:
        return f"NEW_ARR con longitud {length.value} fuera de 0..{MAX_ARRAY_LENGTH}"
    return None


class ArrayLowering:

    def known_lengths(self) -> dict[Temp, int]:
        """temporales que apuntan a un arreglo recien creado en este bloque, con su longitud."""
        if not hasattr(self, "_known_lengths"):
            self._known_lengths: dict[Temp, int] = {}
        return self._known_lengths

    def forget_known_lengths(self, instr: TACInstruction) -> None:
        """antes de cada instruccion: una etiqueta junta caminos y una definicion pisa el temporal."""
        if instr.opcode is Opcode.LABEL:
            self.known_lengths().clear()
        elif isinstance(instr.result, Temp) and instr.opcode not in _RESULT_IS_READ:
            self.known_lengths().pop(instr.result, None)

    def lower_new_arr(self, instr: TACInstruction) -> None:
        result = self._temp_result(instr, "un arreglo nuevo")
        length = instr.arg1.value
        self.call_helper("rt_alloc", (Const(array_size(length), INTEGER),), result)
        array = self.allocator.get_reg(result)
        if length:
            self.builder.emit("li", T8, Imm(length))
            self.builder.emit("sw", T8, Mem(ARRAY_LENGTH_OFFSET, array), comment="longitud")
        self.known_lengths()[result] = length

    def lower_arr_get(self, instr: TACInstruction) -> None:
        array, index = instr.arg1, instr.arg2
        self.call_helper("rt_check_bounds", (array, index), on_error=self.error_target())
        base = self.emitter.value_in_reg(array, T8)
        address, offset = self._element_address(base, index)
        self.assign(instr.result, lambda dest: self.builder.emit("lw", dest, Mem(offset, address)))

    def lower_arr_set(self, instr: TACInstruction) -> None:
        array, index, value = instr.result, instr.arg1, instr.arg2
        if not self._statically_in_bounds(array, index):
            self.call_helper("rt_check_bounds", (array, index), on_error=self.error_target())
        base = self.emitter.value_in_reg(array, T8)
        address, offset = self._element_address(base, index)
        # el valor va al scratch que no tiene la direccion (si la direccion quedo en un
        # registro del allocator, cualquiera de los dos sirve)
        source = self.emitter.value_in_reg(value, T9 if address == T8 else T8)
        self.builder.emit("sw", source, Mem(offset, address))

    def lower_len(self, instr: TACInstruction) -> None:
        array = instr.arg1
        self.call_helper("rt_check_null", (array,), on_error=self.error_target())
        base = self.emitter.value_in_reg(array, T8)
        self.assign(instr.result, lambda dest: self.builder.emit("lw", dest, Mem(ARRAY_LENGTH_OFFSET, base)))

    def _statically_in_bounds(self, array: OperandValue, index: OperandValue) -> bool:
        length = self.known_lengths().get(array) if isinstance(array, Temp) else None
        return length is not None and isinstance(index, Const) and 0 <= index.value < length

    def _element_address(self, base: Reg, index: OperandValue) -> tuple[Reg, int]:
        """(registro, offset) de la palabra del elemento. con indice constante no hace cuentas."""
        if isinstance(index, Const):
            offset = ARRAY_FIRST_ELEMENT_OFFSET + WORD * index.value
            if offset <= _IMM16_MAX:
                return base, offset
        position = self.emitter.value_in_reg(index, T9)
        self.builder.emit("sll", T9, position, Imm(2), comment="indice * 4")
        self.builder.emit("addu", T9, T9, base)
        return T9, ARRAY_FIRST_ELEMENT_OFFSET

