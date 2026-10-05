"""
recorrido del ast sabiendo en que scope y en que funcion se esta parado, para resolver
un identificador al MISMO simbolo que declaro symbol_collector.

regla: un nodo abre el scope que el collector registro en su (linea, columna), si hay
alguno. ademas cada construccion visita sus partes en el mismo orden que el collector:

  while / do-while   la condicion va FUERA del LOOP; el cuerpo usa el LOOP (sin BLOCK)
  for                cabecera dentro del LOOP; el cuerpo abre su propio BLOCK
  foreach            el iterable va FUERA del LOOP; el cuerpo abre su propio BLOCK
  switch             el sujeto va FUERA del SWITCH; todos los case comparten el SWITCH
  try / catch        el try abre un BLOCK; el catch y su cuerpo comparten el CATCH
  funcion / metodo   el cuerpo reusa el scope FUNCTION (el Block del cuerpo no abre nada)

para extenderlo (persona 2 / persona 3): sobreescribir visit_<Nodo> y, si el nodo abre
scope, envolver lo que corresponda con `with self.enter(node):`. no usar _dispatch para
esos nodos porque se saltaria el manejo de scopes.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from compiler.ast_nodes import (
    AstVisitor, Block, ClassDecl, DoWhileStatement, ForeachStatement, ForStatement,
    FunctionDecl, Node, SwitchStatement, TryCatchStatement, WhileStatement,
)
from compiler.scopes import Scope, ScopeKind, SymbolTable
from compiler.symbols import ClassSymbol, FunctionSymbol, Symbol


def index_scopes(symbols: SymbolTable) -> dict[tuple[int, int], Scope]:
    """(linea, columna) -> scope. el global no tiene nodo propio y queda afuera."""
    index: dict[tuple[int, int], Scope] = {}
    for scope in symbols.all_scopes():
        if scope is symbols.global_scope:
            continue
        key = (scope.line, scope.column)
        if key in index:
            # el collector abre a lo sumo un scope por token; si esto pasa, algo cambio ahi
            raise RuntimeError(f"dos scopes en la misma posicion {key}: {index[key]} y {scope}")
        index[key] = scope
    return index


def all_functions(symbols: SymbolTable) -> list[FunctionSymbol]:
    """funciones, anidadas, metodos y constructores con scope propio, en orden determinista."""
    found: list[FunctionSymbol] = []
    for scope in symbols.all_scopes():
        for symbol in scope.symbols.values():
            if isinstance(symbol, FunctionSymbol):
                found.append(symbol)
            elif isinstance(symbol, ClassSymbol):
                found.extend(symbol.methods.values())
    return [fn for fn in found if fn.scope is not None]


class ScopedVisitor(AstVisitor):
    def __init__(self, symbols: SymbolTable) -> None:
        super().__init__()
        self._index = index_scopes(symbols)
        self._function_of = {id(fn.scope): fn for fn in all_functions(symbols)}
        self._scope: Scope = symbols.global_scope
        self._function: FunctionSymbol | None = None

    @property
    def current_scope(self) -> Scope:
        return self._scope

    @property
    def current_function(self) -> FunctionSymbol | None:
        """la funcion cuyo frame esta activo; None en el codigo global."""
        return self._function

    def resolve(self, name: str) -> Symbol | None:
        return self._scope.lookup(name)

    @contextmanager
    def enter(self, node: Node) -> Iterator[Scope]:
        scope = self._index.get((node.line, node.column))
        if scope is None:
            yield self._scope
            return
        previous = (self._scope, self._function)
        self._scope = scope
        if scope.kind is ScopeKind.FUNCTION:
            self._function = self._function_of.get(id(scope))
        try:
            yield scope
        finally:
            self._scope, self._function = previous

    # ------------------------------------------------------------------
    # orden de recorrido igual al de symbol_collector
    # ------------------------------------------------------------------

    def _visit_optional(self, node: Node | None) -> None:
        if node is not None:
            self.visit(node)

    def visit_FunctionDecl(self, node: FunctionDecl) -> None:
        with self.enter(node):
            self.generic_visit(node)

    def visit_ClassDecl(self, node: ClassDecl) -> None:
        with self.enter(node):
            self.generic_visit(node)

    def visit_Block(self, node: Block) -> None:
        with self.enter(node):
            self.generic_visit(node)

    def visit_WhileStatement(self, node: WhileStatement) -> None:
        self.visit(node.condition)
        with self.enter(node):
            self.visit(node.body)

    def visit_DoWhileStatement(self, node: DoWhileStatement) -> None:
        with self.enter(node):
            self.visit(node.body)
        self.visit(node.condition)

    def visit_ForStatement(self, node: ForStatement) -> None:
        with self.enter(node):
            self._visit_optional(node.init)
            self._visit_optional(node.condition)
            self._visit_optional(node.update)
            self.visit(node.body)

    def visit_ForeachStatement(self, node: ForeachStatement) -> None:
        self.visit(node.iterable)
        with self.enter(node):
            self.visit(node.body)

    def visit_TryCatchStatement(self, node: TryCatchStatement) -> None:
        self.visit(node.try_block)
        with self.enter(node):
            self.visit(node.catch_block)

    def visit_SwitchStatement(self, node: SwitchStatement) -> None:
        self.visit(node.subject)
        with self.enter(node):
            for case in node.cases:
                self.visit(case)
            for stmt in node.default_statements or []:
                self.visit(stmt)
