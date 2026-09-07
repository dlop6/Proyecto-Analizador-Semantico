"""
fachada de la semantica extendida: encadena el ExtendedSemanticVisitor sobre el
CoreSemanticResult ya producido por la semantica core (persona 2). API congelada,
analoga a core_semantics.analyze y frontend.analyze_source.

extended_semantics.analyze(core_result) -> ExtendedSemanticResult(ast, symbols, diagnostics)
"""
from __future__ import annotations

from dataclasses import dataclass

from compiler.ast_nodes import Program
from compiler.core_semantics import CoreSemanticResult
from compiler.diagnostics import Diagnostic, DiagnosticBag
from compiler.extended_semantic_visitor import ExtendedSemanticVisitor
from compiler.scopes import SymbolTable


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

    visitor = ExtendedSemanticVisitor(core_result.symbols, diagnostics)
    visitor.analyze(core_result.ast)

    return ExtendedSemanticResult(
        ast=core_result.ast,
        symbols=core_result.symbols,
        diagnostics=diagnostics.to_list(),
    )
