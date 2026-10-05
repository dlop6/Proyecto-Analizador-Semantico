"""
generador de tac para el subconjunto core (persona 2, gate B). API congelada:

  program = CoreTacGenerator.generate(semantic_result, runtime_layout)   # -> IRProgram

recorre el ast semantico ya validado y lo baja a TACInstruction usando SOLO la
infraestructura de persona 1: IRBuilder (opcodes, temporales, etiquetas), RuntimeLayout
(slots, etiquetas de funcion, registros de activacion) y ScopedVisitor (resolver cada
nombre al mismo simbolo que declaro el collector). no valida tipos ni nombres de nuevo
y no crea otra tabla de simbolos, otro manager de temporales ni otro formato de texto.

con cualquier error lexico, sintactico o semantico rechaza la entrada de forma
explicita (ValueError de require_semantic_success) antes de emitir nada.

cada familia de construcciones vive en su modulo (srp):
  expression_lowering    literales, variables, asignacion, operadores, ternario, && / ||
  control_flow_lowering  if, while, do-while, for, switch, break, continue
  function_lowering      funciones, return, llamadas, recursion, anidadas
y este archivo solo las compone y agrega declaraciones, print y sentencias-expresion.

extension (persona 3): ExtendedTacGenerator(CoreTacGenerator) sobreescribe los visit_
de arreglos, objetos, foreach y try/catch y los ganchos lower_member_assignment /
lower_method_call. aca esos nodos fallan con UnsupportedConstructError en vez de
generarse a medias.
"""
from __future__ import annotations

from compiler.ast_nodes import (
    ArrayLiteral, ClassDecl, ErrorExpr, ExprStatement, ForeachStatement,
    IndexAccess, NewExpr, Node, PrintStatement, PropertyAccess, ThisExpr, TryCatchStatement,
    VarDecl,
)
from compiler.extended_semantics import SemanticResult
from compiler.ir.builder import IRBuilder, IRError
from compiler.ir.model import IRProgram
from compiler.ir.opcodes import Opcode
from compiler.runtime.runtime_layout import RuntimeLayout, require_semantic_success
from compiler.runtime.scoped_visitor import ScopedVisitor
from compiler.runtime.storage import StorageRef
from compiler.symbols import Symbol, VariableSymbol
from compiler.tac.control_flow_lowering import ControlFlowLowering
from compiler.tac.expression_lowering import ExpressionLowering, walk_nodes
from compiler.tac.function_lowering import FunctionLowering


class UnsupportedConstructError(IRError):
    """construccion fuera del subconjunto core: la baja el generador extendido."""


class CoreTacGenerator(ExpressionLowering, ControlFlowLowering, FunctionLowering, ScopedVisitor):

    @classmethod
    def generate(cls, semantic_result: SemanticResult, runtime_layout: RuntimeLayout) -> IRProgram:
        generator = cls(semantic_result, runtime_layout)
        generator.visit(semantic_result.ast)
        return generator.builder.build()

    def __init__(self, semantic_result: SemanticResult, runtime_layout: RuntimeLayout) -> None:
        require_semantic_success(semantic_result)
        if not isinstance(runtime_layout, RuntimeLayout):
            raise IRError("el generador necesita el RuntimeLayout de runtime_layout.prepare()")
        super().__init__(semantic_result.symbols)
        self.layout = runtime_layout
        self.builder = IRBuilder(runtime_layout)
        self.init_jump_targets()
        # declaraciones que el recorrido todavia no alcanzo (ver variable_ref)
        self._undeclared: set[tuple[int, int]] = {
            (node.line, node.column) for node in walk_nodes(semantic_result.ast) if isinstance(node, VarDecl)
        }

    # ------------------------------------------------------------------
    # nombres
    # ------------------------------------------------------------------

    def variable_ref(self, name: str) -> StorageRef:
        """donde vive la variable `name` vista desde el punto actual del recorrido."""
        symbol = self._visible(name)
        if not isinstance(symbol, VariableSymbol):
            raise IRError(f"'{name}' no es una variable visible en {self.current_scope}")
        return self.layout.ref_for(symbol, self.current_function)

    def _visible(self, name: str) -> Symbol | None:
        """
        como resolve(), pero salta las variables cuyo `let` todavia no se recorrio. es lo
        que vio symbol_collector, que declara al llegar a cada VarDecl (despues de su
        inicializador): en `{ print(x); let x = 2; }` ese x es el de afuera, no el local
        que despues aparece en la tabla completa.
        """
        scope = self.current_scope
        while scope is not None:
            symbol = scope.symbols.get(name)
            if symbol is not None and (symbol.line, symbol.column) not in self._undeclared:
                return symbol
            scope = scope.parent
        return None

    def unsupported(self, node: Node):
        raise UnsupportedConstructError(
            f"{type(node).__name__} en {node.line}:{node.column} no es parte del tac core"
        )

    # ------------------------------------------------------------------
    # sentencias simples
    # ------------------------------------------------------------------

    def visit_VarDecl(self, node: VarDecl) -> None:
        """
        let/var/const son iguales aca: la semantica ya prohibio reasignar constantes. sin
        inicializador no se emite nada (el slot ya existe en el frame o en el area global).
        """
        value = self.lower_value(node.initializer) if node.initializer is not None else None
        # se declara DESPUES del inicializador: en `let x = x + 1;` el x de la derecha es el de afuera
        self._undeclared.discard((node.line, node.column))
        if value is not None:
            self.builder.emit(Opcode.MOV, self.variable_ref(node.name), value)
            self.release(value)

    def visit_PrintStatement(self, node: PrintStatement) -> None:
        value = self.lower_value(node.expression)
        self.builder.emit(Opcode.PRINT, arg1=value)
        self.release(value)

    def visit_ExprStatement(self, node: ExprStatement) -> None:
        self.lower_effect(node.expression)

    # ------------------------------------------------------------------
    # fuera del subconjunto core (persona 3)
    # ------------------------------------------------------------------

    def visit_ClassDecl(self, node: ClassDecl) -> None:
        self.unsupported(node)

    def visit_ForeachStatement(self, node: ForeachStatement) -> None:
        self.unsupported(node)

    def visit_TryCatchStatement(self, node: TryCatchStatement) -> None:
        self.unsupported(node)

    def visit_ArrayLiteral(self, node: ArrayLiteral):
        return self.unsupported(node)

    def visit_IndexAccess(self, node: IndexAccess):
        return self.unsupported(node)

    def visit_PropertyAccess(self, node: PropertyAccess):
        return self.unsupported(node)

    def visit_NewExpr(self, node: NewExpr):
        return self.unsupported(node)

    def visit_ThisExpr(self, node: ThisExpr):
        return self.unsupported(node)

    def visit_ErrorExpr(self, node: ErrorExpr):
        return self.unsupported(node)
