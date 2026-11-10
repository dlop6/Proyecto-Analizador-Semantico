"""
lowering de arreglos a tac: literales, acceso por indice, asignacion indexada y foreach.
las formas exactas estan en docs/INTERMEDIATE_CODE.md §10.

  [e0, e1]       t = NEW_ARR 2 ; ARR_SET t, 0, e0 ; ARR_SET t, 1, e1
  a[i]           t = ARR_GET a, i
  a[i] = v       ARR_SET a, i, v
  foreach        indice + LEN + ARR_GET (el arreglo, el indice y la longitud quedan
                 vivos durante todo el cuerpo)

los arreglos multidimensionales no tienen nada especial: un literal anidado es un arreglo
cuyos elementos son arreglos, y `m[i][j]` son dos ARR_GET encadenados.

no hay chequeo estatico de limites: el indice fuera de rango queda para el runtime.

mixin del generador extendido. usa de la clase concreta: builder, enter(nodo), visit,
lower_value, release, new_temp_for, variable_ref, jump_targets y _may_overwrite.
"""
from __future__ import annotations

from compiler.ast_nodes import ArrayLiteral, Assignment, Expr, ForeachStatement, IndexAccess
from compiler.ir.model import Const, OperandValue, Temp
from compiler.ir.opcodes import Opcode
from compiler.runtime.storage import StorageRef
from compiler.types import BOOLEAN, INTEGER


class ArrayLowering:

    def visit_ArrayLiteral(self, node: ArrayLiteral) -> Temp:
        array = self.new_temp_for(node)
        self.builder.emit(Opcode.NEW_ARR, array, Const(len(node.elements), INTEGER))
        for index, element in enumerate(node.elements):
            value = self.lower_value(element)
            self.builder.emit(Opcode.ARR_SET, array, Const(index, INTEGER), value)
            self.release(value)
        return array

    def visit_IndexAccess(self, node: IndexAccess) -> Temp:
        array, index = self._lower_array_and_index(node, then=None)
        result = self.new_temp_for(node)
        self.builder.emit(Opcode.ARR_GET, result, array, index)
        self.release(array)
        self.release(index)
        return result

    def lower_index_assignment(self, node: Assignment, want_value: bool) -> OperandValue | None:
        """`a[i] = v`: se evaluan a, i y v en ese orden y se emite ARR_SET a, i, v."""
        target: IndexAccess = node.target
        array, index = self._lower_array_and_index(target, then=node.value)
        value = self.lower_value(node.value)
        self.builder.emit(Opcode.ARR_SET, array, index, value)
        self.release(array)
        self.release(index)
        if want_value:
            return value
        self.release(value)
        return None

    def _lower_array_and_index(self, node: IndexAccess, then: Expr | None) -> tuple[OperandValue, OperandValue]:
        """
        arreglo e indice de izquierda a derecha. si lo que se evalua despues (el indice o el
        valor asignado) puede escribir la variable que ya se leyo, se copia antes a un
        temporal: mismo criterio de orden de evaluacion que BinaryOp en el core.
        """
        array = self._protect(self.lower_value(node.collection), node.collection, [node.index, then])
        index = self._protect(self.lower_value(node.index), node.index, [then])
        return array, index

    def _protect(self, operand: OperandValue, expr: Expr, later: list[Expr | None]) -> OperandValue:
        if isinstance(operand, StorageRef) and any(e is not None and self._may_overwrite(operand, e) for e in later):
            return self._snapshot(operand, expr)
        return operand

    # ------------------------------------------------------------------
    # foreach
    # ------------------------------------------------------------------

    def visit_ForeachStatement(self, node: ForeachStatement) -> None:
        cond_label = self.builder.new_label("foreach_cond")
        step_label, end_label = self.builder.new_label("foreach_step"), self.builder.new_label("foreach_end")

        # el iterable va FUERA del scope del foreach (igual que en symbol_collector) y se
        # copia a un temporal propio: reasignar la variable en el cuerpo no cambia el recorrido
        iterable = self.lower_value(node.iterable)
        array = self.new_temp_for(node.iterable)
        self.builder.emit(Opcode.MOV, array, iterable)
        self.release(iterable)
        index = self.builder.new_temp(INTEGER)
        self.builder.emit(Opcode.MOV, index, Const(0, INTEGER))
        length = self.builder.new_temp(INTEGER)
        self.builder.emit(Opcode.LEN, length, array)

        self.builder.mark_label(cond_label)
        in_range = self.builder.new_temp(BOOLEAN)
        self.builder.emit(Opcode.BIN, in_range, index, length, op="<")
        self.builder.emit(Opcode.IF_FALSE, None, in_range, end_label)
        self.release(in_range)

        # la semantica ya garantizo un ArrayType con tipo de elemento conocido (CPS-120)
        element_type = node.iterable.inferred_type.element
        with self.enter(node):
            item = self.builder.new_temp(element_type)
            self.builder.emit(Opcode.ARR_GET, item, array, index)
            self.builder.emit(Opcode.MOV, self.variable_ref(node.var_name), item)
            self.release(item)
            with self.jump_targets(end_label, step_label):
                self.visit(node.body)

        self.builder.mark_label(step_label)
        self.builder.emit(Opcode.BIN, index, index, Const(1, INTEGER), op="+")
        self.builder.emit(Opcode.GOTO, arg1=cond_label)
        self.builder.mark_label(end_label)
        for temp in (array, index, length):
            self.release(temp)
