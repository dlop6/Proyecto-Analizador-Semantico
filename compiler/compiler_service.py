"""
fachada de integracion: encadena todo el pipeline

  frontend -> semantica core -> semantica extendida -> runtime layout
           -> ExtendedTacGenerator -> serializer

mas la visualizacion del ast. es el UNICO compositor del pipeline completo (dip): ni
ide/app.py ni ningun otro modulo instancia las etapas por separado.

compiler_service.compile_source(source)
    -> CompilationResult(success, diagnostics, ast_svg, tac_text, symbols)

invariante: con cualquier error lexico, sintactico o semantico no se genera ir
(tac_text=None) y ni siquiera se llama a runtime_layout.prepare. las advertencias no
bloquean la generacion.
"""
from __future__ import annotations

from dataclasses import dataclass

import graphviz

from compiler import core_semantics, extended_semantics, frontend
from compiler.ast_visualizer import render_svg
from compiler.diagnostics import Diagnostic
from compiler.ir.serializer import serialize
from compiler.runtime.runtime_layout import prepare
from compiler.scopes import SymbolTable
from compiler.tac.extended_generator import ExtendedTacGenerator

# excepciones puntuales que graphviz.Digraph.pipe() puede lanzar cuando el binario 'dot'
# no esta instalado o falla -- no se captura Exception a secas para no esconder bugs
# reales de _add_node/_label_for si algun dia se rompen.
_GRAPHVIZ_ERRORS = (graphviz.ExecutableNotFound, graphviz.CalledProcessError)


@dataclass(frozen=True, slots=True)
class CompilationResult:
    """
    contrato que consume el ide: exito, diagnosticos de todo el pipeline, svg del ast,
    el tac serializado (None si hubo cualquier error) y la tabla de simbolos completa
    (arbol de scopes, con la informacion de runtime que agrega prepare cuando hubo ir).
    """
    success: bool
    diagnostics: list[Diagnostic]
    ast_svg: str | None
    tac_text: str | None
    symbols: SymbolTable


def compile_source(source: str) -> CompilationResult:
    """
    corre el pipeline completo sobre `source`. si hubo error de sintaxis (sin ast), no
    hay diagrama que dibujar -- `ast_svg` queda en None. si el ast existe pero la CLI
    'dot' no esta disponible en este entorno, la compilacion sigue siendo valida y solo
    se pierde el diagrama (el ide sigue funcionando con los diagnosticos igual).
    """
    frontend_result = frontend.analyze_source(source)
    core_result = core_semantics.analyze(frontend_result)
    extended_result = extended_semantics.analyze(core_result)

    ast_svg = None
    if extended_result.ast is not None:
        try:
            ast_svg = render_svg(extended_result.ast)
        except _GRAPHVIZ_ERRORS:
            ast_svg = None

    success = extended_result.ast is not None and not extended_result.has_errors
    tac_text = None
    if success:
        program = ExtendedTacGenerator.generate(extended_result, prepare(extended_result))
        tac_text = serialize(program)

    return CompilationResult(
        success=success,
        diagnostics=extended_result.diagnostics,
        ast_svg=ast_svg,
        tac_text=tac_text,
        symbols=extended_result.symbols,
    )
