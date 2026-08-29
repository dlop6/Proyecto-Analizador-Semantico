"""
arbol de ambitos (scopes) y la tabla de simbolos que lo gestiona, parte del frontend.

dos abstracciones separadas a proposito:
- Scope: estructura pasiva, solo guarda simbolos y sabe resolver nombres subiendo
  por su padre. no conoce diagnosticos ni el ast.
- SymbolTable: el cursor que arma el arbol de scopes mientras se recorre el ast,
  con push() como context manager para que el pop este garantizado incluso si
  algo revienta a medio camino. esto es lo que viaja en FrontendResult.symbols.
"""
from __future__ import annotations

from contextlib import contextmanager
from enum import Enum, auto
from typing import Iterator

from compiler.symbols import ClassSymbol, FunctionSymbol, Symbol, VariableSymbol


class ScopeKind(Enum):
    GLOBAL = auto()
    FUNCTION = auto()
    CLASS = auto()
    BLOCK = auto()
    LOOP = auto()
    CATCH = auto()
    SWITCH = auto()


class Scope:
    """nodo del arbol de scopes. estructura de datos pasiva, sin logica de orquestacion."""

    def __init__(self, kind: ScopeKind, name: str, parent: "Scope | None", line: int = 0, column: int = 0) -> None:
        self.kind = kind
        self.name = name
        self.parent = parent
        self.children: list[Scope] = []
        self.symbols: dict[str, Symbol] = {}
        self.line = line
        self.column = column
        if parent is not None:
            parent.children.append(self)

    def declare(self, symbol: Symbol) -> bool:
        """True si se pudo declarar. False si ya existia algo con ese nombre EN ESTE scope."""
        if symbol.name in self.symbols:
            return False
        symbol.scope_name = self.name
        self.symbols[symbol.name] = symbol
        return True

    def lookup_local(self, name: str) -> Symbol | None:
        return self.symbols.get(name)

    def lookup(self, name: str) -> Symbol | None:
        """busca en este scope y sube por los padres. nunca baja a los hijos."""
        scope: Scope | None = self
        while scope is not None:
            found = scope.symbols.get(name)
            if found is not None:
                return found
            scope = scope.parent
        return None

    def enclosing_of_kind(self, kind: ScopeKind) -> "Scope | None":
        scope: Scope | None = self
        while scope is not None:
            if scope.kind == kind:
                return scope
            scope = scope.parent
        return None

    def enclosing_class(self) -> "Scope | None":
        return self.enclosing_of_kind(ScopeKind.CLASS)

    def enclosing_function(self) -> "Scope | None":
        return self.enclosing_of_kind(ScopeKind.FUNCTION)

    def __repr__(self) -> str:
        return f"Scope({self.kind.name}, {self.name!r}, {len(self.symbols)} simbolos)"


class SymbolTable:
    """
    cursor + arbol de scopes de una compilacion. sin estado compartido entre
    instancias -- cada llamada a analyze_source crea la suya.
    """

    def __init__(self) -> None:
        self.global_scope = Scope(ScopeKind.GLOBAL, "global", parent=None)
        self.current = self.global_scope

    @contextmanager
    def push(self, kind: ScopeKind, name: str, line: int = 0, column: int = 0) -> Iterator[Scope]:
        """
        abre un scope hijo del actual y lo deja como current mientras dura el bloque
        'with'. al salir (incluso por excepcion) restaura el scope anterior -- asi
        no hay forma de dejar un scope "colgado" a medio construir.
        """
        new_scope = Scope(kind, name, parent=self.current, line=line, column=column)
        previous = self.current
        self.current = new_scope
        try:
            yield new_scope
        finally:
            self.current = previous

    def declare(self, symbol: Symbol) -> Symbol | None:
        """declara en el scope actual. None si ya habia un duplicado (el llamador diagnostica)."""
        return symbol if self.current.declare(symbol) else None

    def lookup(self, name: str) -> Symbol | None:
        return self.current.lookup(name)

    def all_scopes(self) -> Iterator[Scope]:
        """recorrido pre-order de todo el arbol, para que la etapa de integracion lo pueda dibujar."""
        stack = [self.global_scope]
        while stack:
            scope = stack.pop()
            yield scope
            # se insertan en reversa para que el pop mantenga el orden de declaracion
            stack.extend(reversed(scope.children))

    def find_scope_for(self, node) -> "Scope | None":
        """busca el scope cuyo (line, column) coincide con la posicion del nodo dado."""
        for scope in self.all_scopes():
            if scope.line == getattr(node, "line", None) and scope.column == getattr(node, "column", None):
                return scope
        return None
