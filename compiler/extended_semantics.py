"""
fachada de la semantica extendida: encadena el ExtendedSemanticVisitor sobre el
CoreSemanticResult ya producido por la semantica core (persona 2). API congelada,
analoga a core_semantics.analyze y frontend.analyze_source.

extended_semantics.analyze(core_result) -> ExtendedSemanticResult(ast, symbols, diagnostics)
"""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import fields

from compiler.ast_nodes import Program
from compiler.core_semantics import CoreSemanticResult
from compiler.core_semantic_visitor import CoreSemanticVisitor
from compiler.diagnostics import Diagnostic, DiagnosticBag
from compiler.extended_semantic_visitor import ExtendedSemanticVisitor
from compiler.scopes import SymbolTable
from compiler.ast_nodes import Node
from compiler.symbols import FunctionSymbol, VariableSymbol


@dataclass(frozen=True, slots=True)
class ExtendedSemanticResult:
    """mismo contrato que CoreSemanticResult/FrontendResult: ast, symbols, diagnostics."""
    ast: Program | None
    symbols: SymbolTable
    diagnostics: list[Diagnostic]

    @property
    def has_errors(self) -> bool:
        return any(d.severity.value == "error" for d in self.diagnostics)

    @property
    def ok(self) -> bool:
        return self.ast is not None and not self.has_errors


def _walk_nodes(value):
    if isinstance(value, Node):
        yield value
        for field in fields(value):
            yield from _walk_nodes(getattr(value, field.name))
    elif isinstance(value, list):
        for item in value:
            yield from _walk_nodes(item)


def _semantic_state(program: Program, symbols: SymbolTable) -> tuple:
    """Estado tipable que debe estabilizar entre core y extendida."""
    node_types = tuple((id(node), node.inferred_type) for node in _walk_nodes(program) if hasattr(node, "inferred_type"))
    symbol_types = []
    for scope in symbols.all_scopes():
        for symbol in scope.symbols.values():
            if isinstance(symbol, VariableSymbol):
                symbol_types.append((id(symbol), symbol.type))
            elif isinstance(symbol, FunctionSymbol):
                symbol_types.append((id(symbol), symbol.return_type))
    return node_types, tuple(symbol_types)


def analyze(core_result: CoreSemanticResult) -> ExtendedSemanticResult:
    """
    punto de entrada congelado de la semantica extendida. no reconstruye ast, scopes ni
    tabla de simbolos: reutiliza exactamente los que trae `core_result`. si la core ya
    fallo (sin ast, error de sintaxis previo), no hay nada que analizar y se devuelven
    los diagnosticos de la core tal cual.
    """
    if core_result.ast is None:
        return ExtendedSemanticResult(ast=None, symbols=core_result.symbols, diagnostics=core_result.diagnostics)

    diagnostics = DiagnosticBag()
    for diag in core_result.diagnostics:
        diagnostics.add(diag)

    # Core deja sin tipo los nodos de clases/arreglos; al tiparlos, algunos padres
    # (return, condiciones, llamadas y operadores) necesitan revalidarse. Alternamos
    # ambas etapas sobre los mismos AST/simbolos hasta que no quede informacion nueva.
    visitor = ExtendedSemanticVisitor(core_result.symbols, diagnostics)
    visitor.analyze(core_result.ast)
    max_iterations = sum(1 for _ in _walk_nodes(core_result.ast)) + sum(
        1 for scope in core_result.symbols.all_scopes() for _ in scope.symbols.values()
    ) + 1
    for _ in range(max_iterations):
        before = _semantic_state(core_result.ast, core_result.symbols)
        CoreSemanticVisitor(core_result.symbols, diagnostics).analyze(core_result.ast)
        ExtendedSemanticVisitor(core_result.symbols, diagnostics).analyze(core_result.ast)
        if _semantic_state(core_result.ast, core_result.symbols) == before:
            break

    return ExtendedSemanticResult(
        ast=core_result.ast,
        symbols=core_result.symbols,
        diagnostics=diagnostics.to_list(),
    )
