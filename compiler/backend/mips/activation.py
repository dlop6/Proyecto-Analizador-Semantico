"""
ActivationEmitter: todo lo que toca el registro de activacion (ver abi.py para el dibujo).
los lowerers no escriben ensamblador a mano: piden prologo/epilogo, leer o escribir una
variable, pasar argumentos y llamar, y aca se emite.

- prologo: guarda ra y fp, arma el frame y deja en cero las locales (el ir nunca las
  inicializa).
- variables: globales en __globals+4*slot; del frame en offset($fp); de un frame que
  encierra, siguiendo el static link tantas veces como diga lexical_depth.
- argumentos: cada ARG se guarda en una casilla del frame apenas se ejecuta; el CALL los
  copia a la pila, en orden, despues del static link y del this.
- salida unica por funcion (<fn>_exit): el return la usa y tambien la propagacion de un
  error, porque con $v1 = 1 y el mensaje en $v0 alcanza con salir tal cual.

el que llama envuelve cada instruccion del ir en allocator.instruction(); este modulo no lo
abre para no anidarlo. limites de bloque: usar mark_label / emit_branch / emit_call, que
sincronizan los registros.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

from compiler.backend.mips.abi import (
    OBJECT_VTABLE_OFFSET, OLD_FP_OFFSET, RA_OFFSET, STATUS_OK, WORD, field_offset,
)
from compiler.backend.mips.builder import MipsBuilder
from compiler.backend.mips.frame_planner import ENTRY_LABEL, FramePlan
from compiler.backend.mips.helpers import HELPERS
from compiler.backend.mips.operands import (
    FP, GLOBALS_LABEL, RA, SCRATCH, SP, V0, V1, ZERO, Imm, LabelMem, LabelRef, Mem, Reg, mangle_label,
)
from compiler.backend.mips.register_allocator import RegisterAllocator
from compiler.ir.model import Const, IRFunction, OperandValue, Temp
from compiler.runtime.storage import StorageKind, StorageRef
from compiler.types import BOOLEAN, INTEGER, NULL, STRING

if TYPE_CHECKING:
    from compiler.runtime.runtime_layout import RuntimeLayout

_T8, _T9 = SCRATCH
UNCAUGHT_HELPER = "rt_uncaught_error"
ENTRY_ERROR_LABEL = "main_error"


class ActivationEmitter:
    def __init__(
        self, builder: MipsBuilder, allocator: RegisterAllocator,
        layout: "RuntimeLayout", plans: Mapping[str, FramePlan],
    ) -> None:
        self._b = builder
        self._alloc = allocator
        self._layout = layout
        self._plans = plans
        self._symbols = {fn.label: fn for fn in layout.functions}
        self._plan: FramePlan | None = None
        self._function = None            # FunctionSymbol actual; None en el codigo global
        self._exit = ""
        self._pending = 0                # ARG guardados que todavia no consumio un CALL
        self._entry_error_used = False

    # ------------------------------------------------------------------
    # ciclo de vida
    # ------------------------------------------------------------------

    def begin_function(self, function: IRFunction) -> None:
        label = mangle_label(function.label)
        self._open(self._plans[function.label], self._symbols[function.label], f"{label}_exit")
        self._b.mark(label)
        self._b.emit("addi", SP, SP, Imm(-2 * WORD))
        self._b.emit("sw", RA, Mem(RA_OFFSET, SP))
        self._b.emit("sw", FP, Mem(OLD_FP_OFFSET, SP))
        self._b.emit("move", FP, SP)
        self._reserve_frame()

    def begin_entry(self) -> None:
        self._open(self._plans[ENTRY_LABEL], None, "main_exit")
        self._b.mark(ENTRY_LABEL)
        self._b.emit("move", FP, SP)
        self._reserve_frame()

    def end_function(self) -> None:
        self._require_open()
        self._check_no_pending()
        # si el cuerpo termina sin return, se sale con 0 y sin error
        self._b.emit("li", V0, Imm(0))
        self._b.emit("li", V1, Imm(STATUS_OK))
        self._b.mark(self._exit)
        self._b.emit("lw", RA, Mem(RA_OFFSET, FP))
        self._b.emit("move", SP, FP)
        self._b.emit("lw", FP, Mem(OLD_FP_OFFSET, SP))
        self._b.emit("addi", SP, SP, Imm(2 * WORD))
        self._b.emit("jr", RA)
        self._close()

    def end_entry(self) -> None:
        self._require_open()
        self._check_no_pending()
        self._b.mark(self._exit)
        self._exit_program()
        if self._entry_error_used:
            # un error sin capturar llega con el mensaje en $v0: se le pasa al helper por la pila
            self._b.mark(ENTRY_ERROR_LABEL)
            self._b.emit("addi", SP, SP, Imm(-WORD))
            self._b.emit("sw", V0, Mem(0, SP))
            self._b.emit("jal", LabelRef(UNCAUGHT_HELPER))
            self._exit_program()
        self._close()

    # ------------------------------------------------------------------
    # limites de bloque
    # ------------------------------------------------------------------

    def mark_label(self, label: str) -> None:
        """etiqueta de control: se guarda lo sucio antes y se olvidan los registros despues."""
        self._alloc.flush_live()
        self._b.mark(label)
        self._alloc.invalidate_caller_saved()

    def emit_branch(self, opcode: str, *operands) -> None:
        self._alloc.flush_live()
        self._b.emit_branch(opcode, *operands)

    def error_target(self) -> str:
        """a donde saltar para propagar un error hacia afuera: la salida de la funcion, o el fin del programa."""
        self._require_open()
        if self._function is None:
            self._entry_error_used = True
            return ENTRY_ERROR_LABEL
        return self._exit

    def emit_error_check(self, target: str) -> None:
        """despues de una llamada que puede fallar: $v1 != 0 -> salta a `target`."""
        self._alloc.flush_live()
        self._b.emit_branch("bne", V1, ZERO, LabelRef(target))

    # ------------------------------------------------------------------
    # valores y variables
    # ------------------------------------------------------------------

    def value_in_reg(self, operand: OperandValue, scratch: Reg = _T8) -> Reg:
        """registro con el valor: el del propio temporal, o `scratch` cargado con la constante/variable."""
        if isinstance(operand, Temp):
            return self._alloc.get_reg(operand)
        self.load_value(operand, scratch)
        return scratch

    def load_value(self, operand: OperandValue, into: Reg) -> None:
        if isinstance(operand, Temp):
            reg = self._alloc.get_reg(operand)
            if reg != into:
                self._b.emit("move", into, reg)
        elif isinstance(operand, Const):
            self._load_const(operand, into)
        elif isinstance(operand, StorageRef):
            self._access("lw", into, operand, into)
        else:
            raise ValueError(f"no se puede cargar {operand!r} como valor")

    def store_storage(self, src: Reg, ref: StorageRef, via: Reg = _T9) -> None:
        """escribe `src` en la variable. `via` es el registro que usa para seguir el static link (distinto de src)."""
        if ref.kind is StorageKind.NONLOCAL and src == via:
            raise ValueError("src y via no pueden ser el mismo registro")
        self._access("sw", src, ref, via)

    def load_field(self, into: Reg, obj: Reg, slot: int) -> None:
        self._b.emit("lw", into, Mem(field_offset(slot), obj))

    def store_field(self, src: Reg, obj: Reg, slot: int) -> None:
        self._b.emit("sw", src, Mem(field_offset(slot), obj))

    # ------------------------------------------------------------------
    # argumentos, llamadas y retorno
    # ------------------------------------------------------------------

    def emit_arg(self, operand: OperandValue) -> None:
        self._require_open()
        stash = self._plan.arg_stash
        if self._pending >= len(stash):
            raise ValueError(f"{self._plan.label} no reservo casillas para el argumento {self._pending}")
        reg = self.value_in_reg(operand)
        self._b.emit("sw", reg, Mem(stash[self._pending], FP), comment=f"arg {self._pending}")
        self._pending += 1

    def emit_call(
        self, callee_label: str, argc: int, link_hops: int | None, result: Temp | None, *, on_error: str,
    ) -> None:
        """CALL del ir. link_hops es el metadata `link` (None si el llamado no usa static link)."""
        sources = [("link", link_hops)] if link_hops is not None else []
        sources += self._take_pending(argc)
        self._invoke(sources, lambda: self._b.emit("jal", LabelRef(mangle_label(callee_label))))
        self._finish_call(result, on_error)

    def emit_method_call(
        self, receiver: OperandValue, slot: int, argc: int, result: Temp | None, *, on_error: str,
    ) -> None:
        """CALL_METHOD del ir: despacho por la tabla de la clase. el receptor ya tiene que ser no-null."""
        recv = self.value_in_reg(receiver, _T8)
        self._b.emit("lw", _T9, Mem(OBJECT_VTABLE_OFFSET, recv))
        self._b.emit("lw", _T9, Mem(WORD * slot, _T9), comment=f"metodo {slot}")
        sources = [("value", receiver)] + self._take_pending(argc)
        self._invoke(sources, lambda: self._b.emit("jalr", _T9))
        self._finish_call(result, on_error)

    def emit_helper_call(
        self, name: str, args: tuple[OperandValue, ...] = (), result: Temp | None = None, *, on_error: str | None = None,
    ) -> None:
        contract = HELPERS.get(name)
        if contract is None:
            raise ValueError(f"helper desconocido: {name}")
        if len(args) != contract.params:
            raise ValueError(f"{name} recibe {contract.params} argumentos, no {len(args)}")
        if contract.can_fail and on_error is None:
            raise ValueError(f"{name} puede fallar: hay que decir a donde saltar con on_error")
        if result is not None and not contract.returns:
            raise ValueError(f"{name} no devuelve valor")
        self._invoke([("value", a) for a in args], lambda: self._b.emit("jal", LabelRef(name)))
        if contract.returns:
            self._take_result(result)
        if contract.can_fail:
            self.emit_error_check(on_error)

    def emit_return(self, value: OperandValue | None) -> None:
        self._require_open()
        if value is None:
            self._b.emit("li", V0, Imm(0))
        else:
            self.load_value(value, V0)
        self._b.emit("li", V1, Imm(STATUS_OK))
        self._b.emit_branch("j", LabelRef(self._exit))

    # ------------------------------------------------------------------
    # internos
    # ------------------------------------------------------------------

    def _open(self, plan: FramePlan, function, exit_label: str) -> None:
        if self._plan is not None:
            raise RuntimeError(f"{self._plan.label} sigue abierta: falta cerrarla antes de empezar otra")
        self._plan, self._function, self._exit, self._pending = plan, function, exit_label, 0
        self._alloc.reset(plan)

    def _close(self) -> None:
        self._plan = self._function = None

    def _reserve_frame(self) -> None:
        if self._plan.size:
            self._b.emit("addi", SP, SP, Imm(-self._plan.size))
        for offset in self._plan.local_offsets.values():
            self._b.emit("sw", ZERO, Mem(offset, FP), comment="local en cero")

    def _require_open(self) -> None:
        if self._plan is None:
            raise RuntimeError("no hay una funcion abierta (begin_function / begin_entry)")

    def _check_no_pending(self) -> None:
        if self._pending:
            raise ValueError(f"{self._plan.label} termino con {self._pending} argumentos sin consumir")

    def _exit_program(self) -> None:
        self._b.emit("li", V0, Imm(10))
        self._b.emit("syscall")

    def _load_const(self, const: Const, into: Reg) -> None:
        if const.type == STRING:
            self._b.emit("la", into, LabelRef(self._b.add_string(const.value)))
        elif const.type == INTEGER:
            self._b.emit("li", into, Imm(const.value))
        elif const.type == BOOLEAN:
            self._b.emit("li", into, Imm(1 if const.value else 0))
        elif const.type == NULL:
            self._b.emit("li", into, Imm(0))
        else:
            raise ValueError(f"constante de tipo {const.type} no soportada")

    def _access(self, opcode: str, reg: Reg, ref: StorageRef, walker: Reg) -> None:
        """lw/sw de `reg` hacia/desde la variable. `walker` es el registro que sigue el static link."""
        if ref.kind is StorageKind.GLOBAL:
            self._b.emit(opcode, reg, LabelMem(GLOBALS_LABEL, WORD * ref.slot))
        elif ref.kind in (StorageKind.THIS, StorageKind.PARAM, StorageKind.LOCAL):
            self._require_open()
            self._b.emit(opcode, reg, Mem(self._plan.offset_of(ref.kind, ref.slot), FP))
        elif ref.kind is StorageKind.NONLOCAL:
            base, owner = self._walk(ref.lexical_depth, walker)
            self._b.emit(opcode, reg, Mem(self._plans[owner.label].slot_offset(ref.slot), base))
        else:
            raise ValueError(f"'{ref.name}' es un campo: se accede con load_field/store_field")

    def _walk(self, hops: int, into: Reg):
        """sigue `hops` static links desde el frame actual. devuelve (registro base, funcion duenia del frame)."""
        self._require_open()
        base, function = FP, self._function
        for _ in range(hops):
            link = self._plans[function.label].static_link if function is not None else None
            if link is None:
                raise ValueError(f"no se puede subir {hops} frames desde {self._plan.label}: falta static link")
            self._b.emit("lw", into, Mem(link, base), comment="static link")
            base, function = into, self._layout.enclosing_function(function)
        return base, function

    def _take_pending(self, argc: int) -> list[tuple[str, int]]:
        if argc < 0 or argc > self._pending:
            raise ValueError(f"el CALL consume {argc} argumentos y hay {self._pending} pendientes")
        first = self._pending - argc
        self._pending = first
        return [("stash", first + i) for i in range(argc)]

    def _invoke(self, sources, jump) -> None:
        """reserva el bloque de argumentos, lo llena en orden, salta y lo limpia."""
        self._alloc.flush_live()
        if sources:
            self._b.emit("addi", SP, SP, Imm(-WORD * len(sources)))
        for index, (kind, payload) in enumerate(sources):
            self._b.emit("sw", self._word(kind, payload), Mem(WORD * index, SP))
        jump()
        if sources:
            self._b.emit("addi", SP, SP, Imm(WORD * len(sources)))
        self._alloc.invalidate_caller_saved()

    def _word(self, kind: str, payload) -> Reg:
        if kind == "stash":
            self._b.emit("lw", _T8, Mem(self._plan.arg_stash[payload], FP))
            return _T8
        if kind == "link":
            base, _ = self._walk(payload, _T8)
            if base == FP:
                self._b.emit("move", _T8, FP, comment="static link = este frame")
            return _T8
        return self.value_in_reg(payload, _T8)

    def _take_result(self, result: Temp | None) -> None:
        if result is not None:
            reg = self._alloc.get_reg(result, load=False)
            self._b.emit("move", reg, V0)
            self._alloc.mark_dirty(result)

    def _finish_call(self, result: Temp | None, on_error: str) -> None:
        self._take_result(result)
        self.emit_error_check(on_error)
