"""
lowering de LABEL, GOTO, IF_TRUE e IF_FALSE a mips.

el tac ya resolvio todo el control de flujo (if/else, while, do-while, for, switch,
break/continue, ternario y el cortocircuito de && / ||) con etiquetas y saltos: aca solo se
traducen uno a uno, sin mirar el ast ni recalcular condiciones.

las etiquetas y los saltos pasan por el ActivationEmitter (mark_label / emit_branch), que
sincroniza el allocator en cada limite de bloque: antes de saltar o de marcar una etiqueta
se guardan los temporales sucios, y despues de una etiqueta ningun registro se da por valido.

un IF sobre una constante (`while (true)`) se decide al compilar: o salta siempre (j) o no
emite nada.

mixin de CoreMipsBackend. usa de la clase concreta: emitter y release_dying.
"""
from __future__ import annotations

from compiler.backend.mips.operands import T, LabelRef, mangle_label
from compiler.ir.model import Const, TACInstruction
from compiler.types import BOOLEAN

T8 = T[8]


def target(instr_label) -> LabelRef:
    return LabelRef(mangle_label(instr_label.name))


class ControlLowering:

    def lower_label(self, instr: TACInstruction) -> None:
        self.emitter.mark_label(mangle_label(instr.arg1.name))

    def lower_goto(self, instr: TACInstruction) -> None:
        self.emitter.emit_branch("j", target(instr.arg1))

    def lower_if_true(self, instr: TACInstruction) -> None:
        self._conditional_jump(instr, jump_when=True)

    def lower_if_false(self, instr: TACInstruction) -> None:
        self._conditional_jump(instr, jump_when=False)

    def _conditional_jump(self, instr: TACInstruction, jump_when: bool) -> None:
        condition, label = instr.arg1, target(instr.arg2)
        if isinstance(condition, Const):
            if condition.type != BOOLEAN:
                raise ValueError(f"condicion constante que no es boolean: {condition!r}")
            if condition.value == jump_when:
                self.emitter.emit_branch("j", label)
            return
        reg = self.emitter.value_in_reg(condition, T8)
        # si la condicion muere aca, se libera antes del flush del salto: el registro todavia
        # tiene el valor para el bnez/beqz, pero ya no se guarda en su home
        self.release_dying()
        self.emitter.emit_branch("bnez" if jump_when else "beqz", reg, label)
