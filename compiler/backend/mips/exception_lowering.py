"""
lowering de TRY_BEGIN, TRY_END y CATCH a mips (persona 3).

el tac de un try/catch es (docs/INTERMEDIATE_CODE.md §10):

    TRY_BEGIN L_try_handler_n
    <cuerpo del try>
    TRY_END
    GOTO L_try_end_m
    LABEL L_try_handler_n
    CATCH <variable>
    <cuerpo del catch>
    LABEL L_try_end_m

no hay throw: los errores son los de runtime (division entre cero, indice fuera de rango,
acceso a null). todos siguen la convencion del abi: quien falla deja $v1 = 1 y el mensaje en
$v0, y el que llama hace `bne $v1, $zero, error_target()`.

por eso el try no necesita nada en tiempo de ejecucion: los manejadores son LEXICOS y se
resuelven al compilar. TRY_BEGIN apila la etiqueta del manejador y TRY_END la desapila;
mientras la pila no esta vacia, error_target() devuelve el manejador de arriba, asi cada
chequeo de $v1 dentro del cuerpo salta directo al catch correcto (el mas interno en try
anidados). fuera de todo try se usa el destino del core: la salida de la funcion (el error
sube al que llamo, que a su vez lo manda a SU catch) o main_error.

- la pila se recorre en el orden lineal del tac. un return/break/continue dentro del try no
  emite TRY_END (docs/BASELINE_P3.md), pero no importa: el codigo que sigue en orden lineal
  hasta el TRY_END sigue siendo cuerpo del try, y al salir de la funcion los manejadores de
  esta dejan de aplicar solos (el que llama revisa $v1 con los suyos).
- el cuerpo del catch esta despues del TRY_END: un error ahi va al try que encierra.
- CATCH guarda $v0 (el mensaje) en la variable. se llega por un `bne` que ya sincronizo el
  allocator, y LABEL no toca $v0, asi que el mensaje sigue intacto.
- validate() exige TRY_BEGIN/TRY_END balanceados por unidad, para no generar a medias.

mixin del backend extendido. usa de la clase concreta: allocator, builder, emitter.
"""
from __future__ import annotations

from compiler.backend.mips.operands import V0, mangle_label
from compiler.ir.model import TACInstruction, Temp
from compiler.ir.opcodes import Opcode


def try_balance_problem(unit_name: str, instructions) -> str | None:
    """por que los try de una unidad no estan balanceados, o None (lo usa validate())."""
    depth = 0
    for instr in instructions:
        if instr.opcode is Opcode.TRY_BEGIN:
            depth += 1
        elif instr.opcode is Opcode.TRY_END:
            depth -= 1
            if depth < 0:
                return f"{unit_name} tiene un TRY_END sin TRY_BEGIN"
    return f"{unit_name} tiene {depth} TRY_BEGIN sin TRY_END" if depth else None


class ExceptionLowering:

    def handler_stack(self) -> list[str]:
        if not hasattr(self, "_handlers"):
            self._handlers: list[str] = []
        return self._handlers

    def active_handler(self) -> str | None:
        handlers = self.handler_stack()
        return handlers[-1] if handlers else None

    def lower_try_begin(self, instr: TACInstruction) -> None:
        self.handler_stack().append(mangle_label(instr.arg1.name))

    def lower_try_end(self, instr: TACInstruction) -> None:
        self.handler_stack().pop()

    def lower_catch(self, instr: TACInstruction) -> None:
        variable = instr.arg1
        if isinstance(variable, Temp):
            reg = self.allocator.get_reg(variable, load=False)
            self.builder.emit("move", reg, V0, comment="mensaje del error")
            self.allocator.mark_dirty(variable)
        else:
            self.emitter.store_storage(V0, variable)
