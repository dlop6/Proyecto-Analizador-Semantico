"""
andamiaje de pruebas: baja IR real a mips usando SOLO las piezas de la base (builder,
allocator, frames, emisor de activacion). cubre enteros, control de flujo y llamadas. NO es
el lowering del producto (arreglos, objetos, strings y excepciones son de otra parte); sirve
para demostrar que frames, registros y llamadas funcionan de punta a punta en mars.

trace=True imprime "enter <fn>" / "exit <fn>" alrededor de cada llamada, para reconstruir
el arbol de activacion desde una ejecucion real sin instrumentar nada del producto.
"""
from compiler.backend.mips.activation import ActivationEmitter
from compiler.backend.mips.builder import MipsBuilder
from compiler.backend.mips.frame_planner import ENTRY_LABEL, plan_program
from compiler.backend.mips.operands import (
    A0, GLOBALS_LABEL, SP, T, V0, Imm, LabelRef, Mem, mangle_label,
)
from compiler.backend.mips.register_allocator import RegisterAllocator
from compiler.ir.model import Temp
from compiler.ir.opcodes import Opcode

T8, T9 = T[8], T[9]
_ARITH = {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "rem"}
_COMPARE = {"==": "seq", "!=": "sne", "<": "slt", "<=": "sle", ">": "sgt", ">=": "sge"}


def lower(program, layout, trace: bool = False) -> str:
    builder = MipsBuilder()
    plans = plan_program(program, layout)
    allocator = RegisterAllocator(builder, plans[ENTRY_LABEL])
    emitter = ActivationEmitter(builder, allocator, layout, plans)
    builder.add_data(GLOBALS_LABEL, "space", max(4, 4 * layout.globals_count))

    emitter.begin_entry()
    if trace:
        _print_text(builder, "enter main\n")
    _body(program.entry.instructions, builder, allocator, emitter, trace)
    if trace:
        _print_text(builder, "exit main\n")
    emitter.end_entry()
    for function in program.functions:
        emitter.begin_function(function)
        _body(function.instructions, builder, allocator, emitter, trace)
        emitter.end_function()
    uncaught_stub(builder)
    return builder.render()


def uncaught_stub(builder) -> None:
    # cuerpo de juguete del helper de errores sin capturar (el real es de otra parte):
    # imprime el mensaje que llega como primer argumento y termina
    builder.mark("rt_uncaught_error")
    builder.emit("lw", A0, Mem(0, SP))
    builder.emit("li", V0, Imm(4))
    builder.emit("syscall")
    builder.emit("li", V0, Imm(10))
    builder.emit("syscall")


def _print_text(builder, text: str) -> None:
    builder.emit("la", A0, LabelRef(builder.add_string(text)))
    builder.emit("li", V0, Imm(4))
    builder.emit("syscall")


def _body(instructions, builder, alloc, emitter, trace) -> None:
    for instr in instructions:
        op = instr.opcode
        if op in (Opcode.FUNC_BEGIN, Opcode.FUNC_END):
            continue
        if op is Opcode.LABEL:
            emitter.mark_label(mangle_label(instr.arg1.name))
        elif op is Opcode.GOTO:
            emitter.emit_branch("j", LabelRef(mangle_label(instr.arg1.name)))
        elif op in (Opcode.IF_TRUE, Opcode.IF_FALSE):
            with alloc.instruction():
                reg = emitter.value_in_reg(instr.arg1)
            emitter.emit_branch("bnez" if op is Opcode.IF_TRUE else "beqz", reg, LabelRef(mangle_label(instr.arg2.name)))
        elif op is Opcode.ARG:
            with alloc.instruction():
                emitter.emit_arg(instr.arg1)
        elif op is Opcode.CALL:
            if trace:
                _print_text(builder, f"enter {instr.arg1.name}\n")
            emitter.emit_call(
                instr.arg1.name, instr.meta("argc"), instr.meta("link"), instr.result,
                on_error=emitter.error_target(),
            )
            if trace:
                _print_text(builder, f"exit {instr.arg1.name}\n")
        elif op is Opcode.RETURN:
            with alloc.instruction():
                emitter.emit_return(instr.arg1)
        elif op is Opcode.PRINT:
            with alloc.instruction():
                emitter.load_value(instr.arg1, A0)
            builder.emit("li", V0, Imm(1))
            builder.emit("syscall")
            builder.emit("li", A0, Imm(10))
            builder.emit("li", V0, Imm(11))
            builder.emit("syscall")
        elif op is Opcode.MOV:
            with alloc.instruction():
                _assign(emitter, alloc, instr.result, lambda dest: emitter.load_value(instr.arg1, dest))
        elif op is Opcode.BIN:
            with alloc.instruction():
                _binary(builder, emitter, alloc, instr)
        elif op is Opcode.UN:
            with alloc.instruction():
                src = emitter.value_in_reg(instr.arg1, T8)
                _assign(emitter, alloc, instr.result, lambda dest: _unary(builder, instr.meta("op"), dest, src))
        else:
            raise NotImplementedError(f"el andamiaje no baja {op.value}")


def _assign(emitter, alloc, result, produce) -> None:
    """produce(dest) deja el valor en `dest`; result es un temporal o una variable."""
    if isinstance(result, Temp):
        reg = alloc.get_reg(result, load=False)
        produce(reg)
        alloc.mark_dirty(result)
    else:
        produce(T8)
        emitter.store_storage(T8, result)


def _binary(builder, emitter, alloc, instr) -> None:
    a = emitter.value_in_reg(instr.arg1, T8)
    b = emitter.value_in_reg(instr.arg2, T9)
    op = instr.meta("op")
    mnemonic = _ARITH.get(op) or _COMPARE[op]
    _assign(emitter, alloc, instr.result, lambda dest: builder.emit(mnemonic, dest, a, b))


def _unary(builder, op, dest, src) -> None:
    if op == "-":
        builder.emit("neg", dest, src)
    else:
        builder.emit("xori", dest, src, Imm(1))
