"""
lowering de expresiones core a tac: literales, identificadores, asignacion, aritmetica,
comparaciones, unarios, ternario y && / || con cortocircuito.

contrato de cada expresion: devuelve un operando de VALOR (Temp | Const | StorageRef).
quien recibe un Temp es su duenio y lo libera (release) justo despues de su ultimo uso;
variables, constantes y StorageRef nunca se liberan. literales e identificadores no
crean temporales: salen como Const y StorageRef directos.

mixin de CoreTacGenerator. usa de la clase concreta: builder, layout, current_function,
variable_ref(nombre), resolve(nombre), unsupported(nodo) y lower_call(nodo, want_value).
no valida tipos ni nombres: eso ya lo hizo la semantica; solo lee inferred_type para
elegir el pool del temporal.
"""
from __future__ import annotations

from dataclasses import fields

from compiler.ast_nodes import (
    Assignment, BinaryOp, BooleanLiteral, Call, Expr, Identifier, IntegerLiteral, NewExpr,
    Node, NullLiteral, StringLiteral, Ternary, UnaryOp,
)
from compiler.ir.builder import IRError
from compiler.ir.model import Const, OperandValue, Temp
from compiler.ir.opcodes import Opcode
from compiler.runtime.storage import FRAME_KINDS, StorageRef
from compiler.symbols import FunctionSymbol
from compiler.types import BOOLEAN, INTEGER, NULL, STRING

# && y || no existen como BIN: se bajan con saltos (prefijo de la etiqueta de salida)
_SHORT_CIRCUIT = {"&&": ("and_end", Opcode.IF_FALSE), "||": ("or_end", Opcode.IF_TRUE)}


def walk_nodes(node: Node):
    """el nodo y todos sus descendientes, en preorden."""
    yield node
    for f in fields(node):
        value = getattr(node, f.name)
        children = value if isinstance(value, list) else [value]
        for child in children:
            if isinstance(child, Node):
                yield from walk_nodes(child)


class ExpressionLowering:

    # ------------------------------------------------------------------
    # puntos de entrada
    # ------------------------------------------------------------------

    def lower_value(self, expr: Expr) -> OperandValue:
        """baja `expr` y devuelve donde quedo su valor."""
        return self.visit(expr)

    def lower_effect(self, expr: Expr) -> None:
        """baja `expr` solo por sus efectos (sentencia): el valor se descarta sin temporal extra."""
        if isinstance(expr, Assignment):
            self.lower_assignment(expr, want_value=False)
        elif isinstance(expr, Call):
            self.lower_call(expr, want_value=False)
        else:
            self.release(self.lower_value(expr))

    def release(self, operand: OperandValue | None) -> None:
        if isinstance(operand, Temp):
            self.builder.release_temp(operand)

    def new_temp_for(self, expr: Expr) -> Temp:
        if expr.inferred_type is None:
            raise IRError(f"{type(expr).__name__} en {expr.line}:{expr.column} llego al ir sin tipo inferido")
        return self.builder.new_temp(expr.inferred_type)

    # ------------------------------------------------------------------
    # hojas: sin temporales
    # ------------------------------------------------------------------

    def visit_IntegerLiteral(self, node: IntegerLiteral) -> Const:
        return Const(node.value, INTEGER)

    def visit_StringLiteral(self, node: StringLiteral) -> Const:
        return Const(node.value, STRING)

    def visit_BooleanLiteral(self, node: BooleanLiteral) -> Const:
        return Const(node.value, BOOLEAN)

    def visit_NullLiteral(self, node: NullLiteral) -> Const:
        return Const(None, NULL)

    def visit_Identifier(self, node: Identifier) -> StorageRef:
        return self.variable_ref(node.name)

    # ------------------------------------------------------------------
    # asignacion
    # ------------------------------------------------------------------

    def visit_Assignment(self, node: Assignment) -> OperandValue:
        return self.lower_assignment(node, want_value=True)

    def lower_assignment(self, node: Assignment, want_value: bool) -> OperandValue | None:
        if not isinstance(node.target, Identifier):
            return self.lower_member_assignment(node, want_value)
        target = self.variable_ref(node.target.name)
        value = self.lower_value(node.value)
        self.builder.emit(Opcode.MOV, target, value)
        self.release(value)
        # el valor de `x = e` es x recien escrito: sirve para `a = b = 3` sin otro temporal
        return target if want_value else None

    def lower_member_assignment(self, node: Assignment, want_value: bool) -> OperandValue | None:
        """destino `obj.campo` o `arr[i]`: lo implementa el generador extendido (persona 3)."""
        return self.unsupported(node)

    # ------------------------------------------------------------------
    # operadores
    # ------------------------------------------------------------------

    def visit_UnaryOp(self, node: UnaryOp) -> Temp:
        operand = self.lower_value(node.operand)
        result = self.new_temp_for(node)
        self.builder.emit(Opcode.UN, result, operand, op=node.op)
        self.release(operand)
        return result

    def visit_BinaryOp(self, node: BinaryOp) -> Temp:
        if node.op in _SHORT_CIRCUIT:
            return self._lower_short_circuit(node)
        left = self.lower_value(node.left)
        if isinstance(left, StorageRef) and self._may_overwrite(left, node.right):
            left = self._snapshot(left, node.left)
        right = self.lower_value(node.right)
        # el resultado se pide ANTES de liberar los operandos: el builder no deja leer
        # un temporal ya liberado, asi que nunca queda `t0 = BIN +, t0, ...`
        result = self.new_temp_for(node)
        self.builder.emit(Opcode.BIN, result, left, right, op=node.op)
        self.release(left)
        self.release(right)
        return result

    def _lower_short_circuit(self, node: BinaryOp) -> Temp:
        """
        a && b:  t = a ; IF_FALSE t, L_and_end ; t = b ; LABEL L_and_end
        a || b:  igual con IF_TRUE y L_or_end. un solo temporal para el resultado.
        """
        prefix, jump = _SHORT_CIRCUIT[node.op]
        end = self.builder.new_label(prefix)
        left = self.lower_value(node.left)
        if isinstance(left, Temp):
            result = left  # ya es un temporal nuestro: se reusa sin MOV redundante
        else:
            result = self.builder.new_temp(BOOLEAN)
            self.builder.emit(Opcode.MOV, result, left)
        self.builder.emit(jump, None, result, end)
        right = self.lower_value(node.right)
        self.builder.emit(Opcode.MOV, result, right)
        self.release(right)
        self.builder.mark_label(end)
        return result

    def visit_Ternary(self, node: Ternary) -> Temp:
        else_label, end_label = self.builder.new_label("tern_else"), self.builder.new_label("tern_end")
        condition = self.lower_value(node.condition)
        self.builder.emit(Opcode.IF_FALSE, None, condition, else_label)
        self.release(condition)
        result = self.new_temp_for(node)
        for branch, last in ((node.then_expr, False), (node.else_expr, True)):
            value = self.lower_value(branch)
            self.builder.emit(Opcode.MOV, result, value)
            self.release(value)
            if not last:
                self.builder.emit(Opcode.GOTO, arg1=end_label)
                self.builder.mark_label(else_label)
        self.builder.mark_label(end_label)
        return result

    # ------------------------------------------------------------------
    # orden de evaluacion izquierda -> derecha
    # ------------------------------------------------------------------

    def _snapshot(self, ref: StorageRef, expr: Expr) -> Temp:
        temp = self.new_temp_for(expr)
        self.builder.emit(Opcode.MOV, temp, ref)
        return temp

    def _may_overwrite(self, ref: StorageRef, expr: Expr) -> bool:
        """
        True si evaluar `expr` puede escribir la variable `ref` antes de que BIN la lea.
        en `x + (x = 5)` o `g + f()` (f modifica la global g) leer `ref` en el BIN daria
        el valor nuevo y romperia el orden izquierda -> derecha; en esos casos el operando
        izquierdo se copia antes a un temporal. en el resto (el caso comun) no hay copia.

        - una asignacion a la misma variable siempre la puede escribir;
        - cualquier llamada (o new) puede escribir una global o una variable de otro frame;
        - una variable del frame actual solo la puede escribir una funcion anidada que
          llegue a este frame, o sea una que use static link.
        """
        for node in walk_nodes(expr):
            if isinstance(node, Assignment) and isinstance(node.target, Identifier):
                if self.variable_ref(node.target.name) == ref:
                    return True
            elif isinstance(node, (Call, NewExpr)):
                if ref.kind not in FRAME_KINDS or self._calls_linked_function(node):
                    return True
        return False

    def _calls_linked_function(self, node: Call | NewExpr) -> bool:
        if not isinstance(node, Call) or not isinstance(node.callee, Identifier):
            return False  # metodos y constructores no tienen static link
        callee = self.resolve(node.callee.name)
        return isinstance(callee, FunctionSymbol) and callee.activation_record.static_link
