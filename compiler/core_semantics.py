"""
fachada de la semantica core: encadena el CoreSemanticVisitor sobre el FrontendResult ya
aprobado (gate a). API congelada que exige el pdf, analoga a frontend.analyze_source.

core_semantics.analyze(frontend_result) -> CoreSemanticResult(ast, symbols, diagnostics)
"""
from __future__ import annotations

from dataclasses import dataclass

from compiler.ast_nodes import Program
from compiler.core_semantic_visitor import CoreSemanticVisitor
from compiler.diagnostics import Diagnostic, DiagnosticBag
from compiler.frontend import FrontendResult
from compiler.scopes import SymbolTable


@dataclass(frozen=True, slots=True)
class CoreSemanticResult:
    """contrato exacto que exige el pdf: ast, symbols, diagnostics. nada mas, nada menos."""
    ast: Program | None
    symbols: SymbolTable
    diagnostics: list[Diagnostic]

    @property
    def has_errors(self) -> bool:
        return any(d.severity.value == "error" for d in self.diagnostics)

    @property
    def ok(self) -> bool:
        return self.ast is not None and not self.has_errors


def analyze(frontend_result: FrontendResult) -> CoreSemanticResult:
    """
    punto de entrada congelado de la semantica core. no reconstruye ast, scopes ni tabla
    de simbolos: reutiliza exactamente los que trae `frontend_result`. si el frontend ya
    fallo (sin ast, error de sintaxis), no hay nada que analizar y se devuelven los
    diagnosticos del frontend tal cual, sin correr el visitor sobre un ast inexistente.
    """
    if frontend_result.ast is None:
        return CoreSemanticResult(ast=None, symbols=frontend_result.symbols, diagnostics=frontend_result.diagnostics)

    diagnostics = DiagnosticBag()
    for diag in frontend_result.diagnostics:
        diagnostics.add(diag)

    visitor = CoreSemanticVisitor(frontend_result.symbols, diagnostics)
    visitor.analyze(frontend_result.ast)

    return CoreSemanticResult(
        ast=frontend_result.ast,
        symbols=frontend_result.symbols,
        diagnostics=diagnostics.to_list(),
    )
