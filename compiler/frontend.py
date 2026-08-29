"""
fachada del frontend: encadena lexer -> parser -> ast propio -> tabla de simbolos.
esta es la API congelada que consumen las etapas siguientes, no se le cambia la firma.

frontend.analyze_source(source) -> FrontendResult(ast, symbols, diagnostics)
"""
from __future__ import annotations

from dataclasses import dataclass

from antlr4 import CommonTokenStream, InputStream

from compiler.ast_builder import AstBuilder
from compiler.ast_nodes import Program
from compiler.diagnostics import CollectingErrorListener, Diagnostic, DiagnosticBag
from compiler.generated import CompiscriptLexer, CompiscriptParser
from compiler.scopes import SymbolTable
from compiler.symbol_collector import collect_symbols

# hardening (owasp asvs / nist sp 800-53 si-10): un limite razonable evita que alguien
# tire el analizador con una fuente gigante cuando la etapa de integracion lo exponga por flask.
MAX_SOURCE_BYTES = 5 * 1024 * 1024  # 5 mib


@dataclass(frozen=True, slots=True)
class FrontendResult:
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


def analyze_source(source: str) -> FrontendResult:
    """
    punto de entrada congelado del frontend. sin estado global: cada llamada crea su
    propia bolsa de diagnosticos y su propia tabla de simbolos, dos llamadas seguidas
    con la misma fuente dan resultados independientes e identicos.
    """
    diagnostics = DiagnosticBag()

    source_bytes = len(source.encode("utf-8"))
    if source_bytes > MAX_SOURCE_BYTES:
        diagnostics.error("CPS-004", 1, 1, detail=str(MAX_SOURCE_BYTES))
        return FrontendResult(ast=None, symbols=SymbolTable(), diagnostics=diagnostics.to_list())

    lexer = CompiscriptLexer(InputStream(source))
    lexer.removeErrorListeners()
    lexer.addErrorListener(CollectingErrorListener(diagnostics, is_lexer=True))

    parser = CompiscriptParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(CollectingErrorListener(diagnostics, is_lexer=False))

    tree = parser.program()

    if diagnostics.has_errors:
        # con recovery activo, el parse tree puede traer ErrorNode/contextos None.
        # no se construye el ast sobre un parse roto: los errores de simbolos que
        # saldrian de ahi serian ruido, no informacion (fail-closed).
        return FrontendResult(ast=None, symbols=SymbolTable(), diagnostics=diagnostics.to_list())

    ast = AstBuilder(diagnostics).visit(tree)
    symbols = collect_symbols(ast, diagnostics)

    return FrontendResult(ast=ast, symbols=symbols, diagnostics=diagnostics.to_list())


def analyze_file(path: str) -> FrontendResult:
    """conveniencia: lee un .cps del disco y lo analiza."""
    with open(path, encoding="utf-8") as f:
        source = f.read()
    return analyze_source(source)
