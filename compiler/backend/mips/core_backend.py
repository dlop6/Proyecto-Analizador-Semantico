"""
backend mips core (persona 2, gate B). API congelada:

  program = CoreMipsBackend.generate(ir_program, runtime_layout)   # -> AssemblyProgram
  text = program.render()

recorre SOLO el ir estructurado (IRProgram / TACInstruction): no ve el ast, no reparsea el
texto del tac y no recalcula tipos, scopes ni slots. todo lo que necesita del frame, de los
registros y de las llamadas lo pide a la base del backend (builder, FramePlanner,
RegisterAllocator, ActivationEmitter).

cada familia de opcodes vive en su modulo (srp), igual que en el generador de tac:
  expression_lowering  MOV, BIN, UN, PRINT
  control_lowering     LABEL, GOTO, IF_TRUE, IF_FALSE
  function_lowering    FUNC_BEGIN, FUNC_END, ARG, CALL, RETURN
y este archivo solo las compone: valida el ir, despacha cada instruccion a su handler y
arma el programa (globales, codigo global, funciones y helpers de runtime usados).

despacho: el handler de un opcode es el metodo `lower_<opcode en minusculas>` (MOV ->
lower_mov). un opcode sin handler es un contrato roto: se rechaza el programa ENTERO antes
de emitir nada (IRContractError), nunca se genera ensamblador a medias.

extension (persona 3): ExtendedMipsBackend(CoreMipsBackend) agrega lower_new_arr,
lower_call_method, lower_try_begin... sobreescribe error_target() para mandar los errores al
catch activo y pasa un catalogo de runtime mas grande en RUNTIME. no edita este archivo.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Iterator

from compiler.backend.mips.abi import WORD
from compiler.backend.mips.activation import ENTRY_ERROR_LABEL, UNCAUGHT_HELPER, ActivationEmitter
from compiler.backend.mips.builder import MipsBuilder
from compiler.backend.mips.control_lowering import ControlLowering
from compiler.backend.mips.expression_lowering import ExpressionLowering
from compiler.backend.mips.frame_planner import ENTRY_LABEL, plan_program
from compiler.backend.mips.function_lowering import FunctionLowering
from compiler.backend.mips.liveness import dead_temps
from compiler.backend.mips.model import AssemblyProgram
from compiler.backend.mips.operands import GLOBALS_LABEL
from compiler.backend.mips.register_allocator import RegisterAllocator
from compiler.backend.mips.runtime_helpers import CORE_RUNTIME, RuntimeLibrary
from compiler.ir.model import Const, IRFunction, IRProgram, OperandValue, TACInstruction, Temp
from compiler.ir.opcodes import Opcode
from compiler.runtime.storage import StorageKind, StorageRef
from compiler.types import Type

if TYPE_CHECKING:
    from compiler.runtime.runtime_layout import RuntimeLayout
    from compiler.symbols import FunctionSymbol


class IRContractError(ValueError):
    """el ir no cumple el contrato que el backend sabe bajar (opcode sin handler, estructura rota)."""


class CoreMipsBackend(ExpressionLowering, ControlLowering, FunctionLowering):

    # catalogo de helpers de runtime disponibles; el backend extendido lo amplia
    RUNTIME = CORE_RUNTIME

    @classmethod
    def generate(cls, program: IRProgram, layout: "RuntimeLayout") -> AssemblyProgram:
        return cls(program, layout).build()

    @classmethod
    def handler_name(cls, opcode: Opcode) -> str:
        return f"lower_{opcode.value.lower()}"

    @classmethod
    def supports(cls, opcode: Opcode) -> bool:
        return callable(getattr(cls, cls.handler_name(opcode), None))

    def __init__(self, program: IRProgram, layout: "RuntimeLayout") -> None:
        if not isinstance(program, IRProgram):
            raise IRContractError(f"el backend solo consume un IRProgram, no {type(program).__name__}")
        self.program = program
        self.layout = layout
        self.validate()
        self.builder = MipsBuilder(ENTRY_LABEL)
        self.plans = plan_program(program, layout)
        self.allocator = RegisterAllocator(self.builder, self.plans[ENTRY_LABEL])
        self.emitter = ActivationEmitter(self.builder, self.allocator, layout, self.plans)
        self.runtime = RuntimeLibrary(self.RUNTIME)
        self.current_function: "FunctionSymbol | None" = None
        self._dying: tuple[Temp, ...] = ()
        self._ir_functions = {fn.label: fn for fn in program.functions}
        self._symbols = {fn.label: fn for fn in layout.functions}
        self._built = False

    # ------------------------------------------------------------------
    # validacion del ir (antes de emitir una sola instruccion)
    # ------------------------------------------------------------------

    def validate(self) -> None:
        problems: list[str] = []
        for instr in self.program.entry.instructions:
            if instr.opcode in (Opcode.FUNC_BEGIN, Opcode.FUNC_END):
                problems.append(f"el codigo global no puede tener {instr.opcode.value}")
        for function in self.program.functions:
            problems += _structure_problems(function)
        missing = sorted({
            instr.opcode.value for instr in self._all_instructions() if not self.supports(instr.opcode)
        })
        if missing:
            problems.append(f"{type(self).__name__} no sabe bajar: {', '.join(missing)}")
        if problems:
            raise IRContractError("ir invalido para el backend mips: " + "; ".join(problems))

    def _all_instructions(self) -> Iterator[TACInstruction]:
        yield from self.program.entry.instructions
        for function in self.program.functions:
            yield from function.instructions

    # ------------------------------------------------------------------
    # armado del programa
    # ------------------------------------------------------------------

    def build(self) -> AssemblyProgram:
        if self._built:
            raise RuntimeError("cada CoreMipsBackend genera un solo programa: usar generate()")
        self._built = True
        self.builder.add_data(GLOBALS_LABEL, "space", WORD * max(1, self.layout.globals_count))

        self.emitter.begin_entry()
        self.lower_all(self.program.entry.instructions)
        self.emitter.end_entry()
        for function in self.program.functions:
            self.lower_all(function.instructions)   # FUNC_BEGIN / FUNC_END abren y cierran
        self.runtime.emit(self.builder)
        return self.builder.build()

    def lower_all(self, instructions: tuple[TACInstruction, ...]) -> None:
        """baja una unidad completa (codigo global o funcion) con su analisis de vida."""
        for instr, dying in zip(instructions, dead_temps(instructions)):
            self.lower_instruction(instr, dying)

    def lower_instruction(self, instr: TACInstruction, dying: tuple[Temp, ...] = ()) -> None:
        handler: Callable[[TACInstruction], None] = getattr(self, self.handler_name(instr.opcode))
        self._dying = dying
        # cada instruccion del ir fija sus registros: el segundo operando no expulsa al primero
        with self.allocator.instruction():
            handler(instr)
            self.release_dying()

    def release_dying(self) -> None:
        """
        libera los temporales que mueren en la instruccion actual: su registro queda libre y
        no se vuelve a guardar en el home. el valor sigue fisicamente en el registro, por eso
        un salto puede llamarlo despues de cargar su condicion y antes de saltar (el flush
        del salto ya no lo guarda). si el temporal no esta en un registro no hay nada que hacer.
        """
        dying, self._dying = self._dying, ()
        for temp in dying:
            if self.allocator.holding(temp) is not None:
                self.allocator.release(temp)

    # ------------------------------------------------------------------
    # servicios para los lowerers
    # ------------------------------------------------------------------

    def ir_function(self, label: str) -> IRFunction:
        return self._ir_functions[label]

    def function_symbol(self, label: str) -> "FunctionSymbol":
        return self._symbols[label]

    def type_of(self, operand: OperandValue) -> Type:
        """tipo estatico de un valor del ir, tal como lo dejo la semantica (no se recalcula)."""
        if isinstance(operand, (Temp, Const)):
            return operand.type
        if isinstance(operand, StorageRef) and operand.kind is not StorageKind.FIELD:
            return self.layout.storage_type(operand, self.current_function)
        raise IRContractError(f"{operand!r} no es un valor con tipo")

    def error_target(self) -> str:
        """
        a donde salta un error de runtime en este punto. en el core no hay try: el error sale
        de la funcion tal cual ($v1 = 1) o, en el codigo global, termina en main_error, que
        llama a rt_uncaught_error. el backend extendido lo sobreescribe con el catch activo.
        """
        target = self.emitter.error_target()
        if target == ENTRY_ERROR_LABEL:
            self.runtime.require(UNCAUGHT_HELPER)
        return target

    def call_helper(
        self, name: str, args: tuple[OperandValue, ...] = (), result: Temp | None = None,
        *, on_error: str | None = None,
    ) -> None:
        """llamada a un helper de runtime: lo registra para emitir su cuerpo al final."""
        self.runtime.require(name)
        self.emitter.emit_helper_call(name, args, result, on_error=on_error)


def _structure_problems(function: IRFunction) -> list[str]:
    instrs = function.instructions
    first, last = (instrs[0], instrs[-1]) if instrs else (None, None)
    problems = []
    if first is None or first.opcode is not Opcode.FUNC_BEGIN or first.arg1.name != function.label:
        problems.append(f"{function.label} no empieza con su FUNC_BEGIN")
    if last is None or last.opcode is not Opcode.FUNC_END or last.arg1.name != function.label:
        problems.append(f"{function.label} no termina con su FUNC_END")
    inner = [i.opcode.value for i in instrs[1:-1] if i.opcode in (Opcode.FUNC_BEGIN, Opcode.FUNC_END)]
    if inner:
        problems.append(f"{function.label} tiene {', '.join(inner)} en el medio")
    return problems
