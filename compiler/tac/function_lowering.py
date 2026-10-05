"""
lowering de funciones core: declaracion (FUNC_BEGIN/FUNC_END), return, llamadas por
nombre (ARG + CALL) y recursion.

- la etiqueta y el registro de activacion salen de runtime_layout (persona 1): aca no se
  calculan slots ni se redeclaran parametros, ya viven en el frame.
- una funcion anidada se emite como unidad propia mientras la de afuera sigue abierta;
  sus accesos a frames ajenos salen como NONLOCAL de ref_for y el CALL lleva link=k
  solo si la funcion llamada usa static link.
- la recursion es un CALL normal a la misma etiqueta (no se desenrolla ni optimiza).

mixin de CoreTacGenerator. usa de la clase concreta: builder, layout, enter(nodo), visit,
current_function, resolve(nombre), unsupported(nodo), lower_value, release,
new_temp_for e isolated_jump_targets.
"""
from __future__ import annotations

from compiler.ast_nodes import Call, Expr, FunctionDecl, Identifier, ReturnStatement
from compiler.ir.builder import IRError
from compiler.ir.model import Const, Label, OperandValue
from compiler.ir.opcodes import Opcode
from compiler.symbols import FunctionSymbol
from compiler.types import NULL, VoidType


class FunctionLowering:

    def visit_FunctionDecl(self, node: FunctionDecl) -> None:
        """sirve igual para funciones, anidadas, metodos y constructores (this ya esta en el frame)."""
        with self.enter(node):
            self.builder.begin_function(self.current_function)
            with self.isolated_jump_targets():
                self.visit(node.body)
            body = node.body.statements
            if not body or not isinstance(body[-1], ReturnStatement):
                self.builder.emit(Opcode.RETURN)
            self.builder.end_function()

    def visit_ReturnStatement(self, node: ReturnStatement) -> None:
        if node.value is None:
            self.builder.emit(Opcode.RETURN)
            return
        value = self.lower_value(node.value)
        self.builder.emit(Opcode.RETURN, arg1=value)
        self.release(value)

    # ------------------------------------------------------------------
    # llamadas
    # ------------------------------------------------------------------

    def visit_Call(self, node: Call) -> OperandValue:
        return self.lower_call(node, want_value=True)

    def lower_call(self, node: Call, want_value: bool) -> OperandValue | None:
        if not isinstance(node.callee, Identifier):
            return self.lower_method_call(node, want_value)
        fn = self.resolve(node.callee.name)
        if not isinstance(fn, FunctionSymbol):
            raise IRError(f"'{node.callee.name}' en {node.line}:{node.column} no es una funcion")
        argc = self.emit_arguments(node.args)
        returns_value = not isinstance(node.inferred_type, VoidType)
        result = self.new_temp_for(node) if want_value and returns_value else None
        link = self.layout.link_hops(self.current_function, fn)
        metadata = {"argc": argc} if link is None else {"argc": argc, "link": link}
        self.builder.emit(Opcode.CALL, result, Label(fn.label), **metadata)
        if want_value and not returns_value:
            # la semantica acepta usar una funcion void como valor (`let y = f();`):
            # se llama igual y el valor que queda es null (decision de diseno)
            return Const(None, NULL)
        return result

    def emit_arguments(self, args: list[Expr]) -> int:
        """izquierda -> derecha: cada argumento se evalua y se pasa con ARG antes del siguiente."""
        for arg in args:
            value = self.lower_value(arg)
            self.builder.emit(Opcode.ARG, arg1=value)
            self.release(value)
        return len(args)

    def lower_method_call(self, node: Call, want_value: bool) -> OperandValue | None:
        """`obj.metodo(args)`: lo implementa el generador extendido (persona 3) con CALL_METHOD."""
        return self.unsupported(node)
