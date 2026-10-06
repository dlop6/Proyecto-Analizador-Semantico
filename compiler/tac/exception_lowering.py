"""
lowering de try/catch a tac (docs/INTERMEDIATE_CODE.md §10):

  TRY_BEGIN L_try_handler
  <bloque try>
  TRY_END
  GOTO L_try_end
  LABEL L_try_handler
  CATCH <variable del catch>
  <bloque catch>
  LABEL L_try_end

no hay `throw` en la gramatica: CATCH solo recibe lo que levante el runtime (por ejemplo
un indice fuera de rango). el try abre su propio BLOCK; el catch y su cuerpo comparten el
scope CATCH, igual que en symbol_collector.

mixin del generador extendido. usa de la clase concreta: builder, enter(nodo), visit y
variable_ref.
"""
from __future__ import annotations

from compiler.ast_nodes import TryCatchStatement
from compiler.ir.opcodes import Opcode


class ExceptionLowering:

    def visit_TryCatchStatement(self, node: TryCatchStatement) -> None:
        handler_label, end_label = self.builder.new_label("try_handler"), self.builder.new_label("try_end")
        self.builder.emit(Opcode.TRY_BEGIN, arg1=handler_label)
        self.visit(node.try_block)
        self.builder.emit(Opcode.TRY_END)
        self.builder.emit(Opcode.GOTO, arg1=end_label)
        self.builder.mark_label(handler_label)
        with self.enter(node):
            self.builder.emit(Opcode.CATCH, arg1=self.variable_ref(node.exception_name))
            self.visit(node.catch_block)
        self.builder.mark_label(end_label)
