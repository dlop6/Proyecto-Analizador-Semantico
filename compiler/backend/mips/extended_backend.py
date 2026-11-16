"""
backend mips completo (persona 3, gate C): el core mas arreglos, objetos, herencia y
try/catch. API, la misma del core:

  program = ExtendedMipsBackend.generate(ir_program, runtime_layout)   # -> AssemblyProgram
  text = program.render()

sustituye a CoreMipsBackend (lsp): no edita el core, solo agrega los handlers que faltaban
(lower_new_arr, lower_call_method, lower_try_begin...), un catalogo de runtime mas grande y
el destino de los errores dentro de un try. para un programa core genera exactamente el
mismo ensamblador que el core: sin clases no hay vtables, sin try error_target() es el del
core y los helpers extra solo se emiten si se usan.

cada familia vive en su modulo (srp), igual que en el generador de tac:
  array_lowering      NEW_ARR, ARR_GET, ARR_SET, LEN
  object_lowering     NEW_OBJ, GET_FIELD, SET_FIELD, CALL_METHOD (+ vtables)
  exception_lowering  TRY_BEGIN, TRY_END, CATCH (+ manejadores lexicos)

como en el core, todo se valida antes de emitir una sola instruccion: un IR que no se puede
bajar entero se rechaza con un IRContractError y nunca queda ensamblador a medias.
"""
from __future__ import annotations

from compiler.backend.mips.array_lowering import ArrayLowering, new_array_problem
from compiler.backend.mips.core_backend import CoreMipsBackend, IRContractError
from compiler.backend.mips.exception_lowering import ExceptionLowering, try_balance_problem
from compiler.backend.mips.model import AssemblyProgram
from compiler.backend.mips.object_lowering import ObjectLowering, new_object_problem
from compiler.backend.mips.runtime_helpers import EXTENDED_RUNTIME
from compiler.ir.opcodes import Opcode


class ExtendedMipsBackend(ArrayLowering, ObjectLowering, ExceptionLowering, CoreMipsBackend):

    RUNTIME = EXTENDED_RUNTIME

    def validate(self) -> None:
        try:
            super().validate()
            problems: list[str] = []
        except IRContractError as error:
            problems = [str(error)]
        units = [("el codigo global", self.program.entry.instructions)]
        units += [(fn.label, fn.instructions) for fn in self.program.functions]
        for name, instructions in units:
            problem = try_balance_problem(name, instructions)
            if problem:
                problems.append(problem)
        for instr in self._all_instructions():
            problem = None
            if instr.opcode is Opcode.NEW_ARR:
                problem = new_array_problem(instr.arg1)
            elif instr.opcode is Opcode.NEW_OBJ:
                problem = new_object_problem(instr, self.layout.class_layouts)
            if problem:
                problems.append(problem)
        if problems:
            raise IRContractError("; ".join(problems))

    def build(self) -> AssemblyProgram:
        instantiated = {
            instr.arg1.name for instr in self._all_instructions() if instr.opcode is Opcode.NEW_OBJ
        }
        if instantiated and not self._built:   # build() repetido: lo rechaza el core
            self.emit_vtables(instantiated)
        return super().build()

    def lower_instruction(self, instr, dying=()) -> None:
        self.forget_known_lengths(instr)
        super().lower_instruction(instr, dying)

    def error_target(self) -> str:
        """dentro de un try, el manejador mas interno; afuera, lo mismo que el core."""
        return self.active_handler() or super().error_target()
