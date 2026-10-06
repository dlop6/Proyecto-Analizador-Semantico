"""
generador de tac completo: el core mas arreglos, foreach, clases/objetos, herencia y
try/catch. API (la misma que la del core, heredada sin cambios):

  program = ExtendedTacGenerator.generate(semantic_result, runtime_layout)   # -> IRProgram

sustituye a CoreTacGenerator (lsp): para cualquier programa del subconjunto core produce
exactamente el mismo ir, porque solo reemplaza los visit_ y ganchos que en el core
terminaban en UnsupportedConstructError. no cambia nada del contrato del core ni del
formato tac.

cada familia vive en su modulo (srp):
  array_lowering      literales, indexacion, asignacion indexada, foreach
  object_lowering     clases, new, this, atributos, llamadas a metodo
  exception_lowering  try/catch
"""
from __future__ import annotations

from compiler.ast_nodes import Assignment, IndexAccess
from compiler.extended_semantics import SemanticResult
from compiler.ir.model import OperandValue
from compiler.runtime.runtime_layout import RuntimeLayout
from compiler.tac.array_lowering import ArrayLowering
from compiler.tac.core_generator import CoreTacGenerator
from compiler.tac.exception_lowering import ExceptionLowering
from compiler.tac.object_lowering import ObjectLowering


class ExtendedTacGenerator(ArrayLowering, ObjectLowering, ExceptionLowering, CoreTacGenerator):

    def __init__(self, semantic_result: SemanticResult, runtime_layout: RuntimeLayout) -> None:
        super().__init__(semantic_result, runtime_layout)
        self.init_object_lowering(semantic_result.ast)

    def lower_member_assignment(self, node: Assignment, want_value: bool) -> OperandValue | None:
        """destino `arr[i]` o `obj.campo` (el core solo baja asignaciones a variables)."""
        if isinstance(node.target, IndexAccess):
            return self.lower_index_assignment(node, want_value)
        return self.lower_property_assignment(node, want_value)
