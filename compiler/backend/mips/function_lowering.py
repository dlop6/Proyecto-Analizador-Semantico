"""
lowering de FUNC_BEGIN, FUNC_END, ARG, CALL y RETURN a mips.

todo el registro de activacion (prologo, epilogo, static link, bloque de argumentos,
limpieza por el que llama, $v0/$v1) es de la base del backend: aca solo se conecta cada
opcode con el ActivationEmitter, sin un segundo abi.

- FUNC_BEGIN / FUNC_END abren y cierran la funcion; el emisor arma el frame con el FramePlan
  y deja una salida unica (<fn>_exit).
- ARG guarda el argumento apenas se evalua; CALL consume los ultimos `argc` y pasa primero
  el static link si el metadata trae `link=k`.
- despues de cada CALL se revisa $v1: si el llamado termino con error, se salta a
  error_target() (la salida de esta funcion, o main_error en el codigo global). asi un
  error de runtime atraviesa cualquier cantidad de llamadas sin perder el mensaje.
- la recursion no tiene nada especial: es un CALL a la misma etiqueta con su propio frame.

mixin de CoreMipsBackend. usa de la clase concreta: emitter, ir_function, function_symbol,
error_target y el atributo current_function.
"""
from __future__ import annotations

from compiler.backend.mips.operands import V0
from compiler.ir.model import TACInstruction, Temp
from compiler.runtime.storage import StorageRef


class FunctionLowering:

    def lower_func_begin(self, instr: TACInstruction) -> None:
        label = instr.arg1.name
        self.current_function = self.function_symbol(label)
        self.emitter.begin_function(self.ir_function(label))

    def lower_func_end(self, instr: TACInstruction) -> None:
        self.emitter.end_function()
        self.current_function = None

    def lower_arg(self, instr: TACInstruction) -> None:
        self.emitter.emit_arg(instr.arg1)

    def lower_call(self, instr: TACInstruction) -> None:
        result = instr.result
        self.emitter.emit_call(
            instr.arg1.name, instr.meta("argc"), instr.meta("link"),
            result if isinstance(result, Temp) else None,
            on_error=self.error_target(),
        )
        if isinstance(result, StorageRef):
            # el valor sigue en $v0: el chequeo de $v1 no lo toca
            self.emitter.store_storage(V0, result)

    def lower_return(self, instr: TACInstruction) -> None:
        self.emitter.emit_return(instr.arg1)
