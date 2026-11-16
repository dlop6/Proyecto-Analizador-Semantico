"""
fachada de integracion: encadena todo el pipeline

  frontend (ANTLR) -> semantica core -> semantica extendida -> runtime layout
           -> ExtendedTacGenerator -> serializer (tac_text)
           -> ExtendedMipsBackend (asm sin optimizar) -> PeepholeOptimizer (asm_text)

mas la visualizacion del ast. es el UNICO compositor del pipeline completo (dip): ni
ide/app.py ni ningun otro modulo instancia las etapas por separado.

compiler_service.compile_source(source)
    -> CompilationResult(success, diagnostics, ast_svg, tac_text, symbols,
                         asm_text, asm_unoptimized, peephole)

invariantes:
- con cualquier error lexico, sintactico o semantico no se genera ir: tac_text y asm_text
  quedan en None y ni siquiera se llama a runtime_layout.prepare. las advertencias no
  bloquean la generacion.
- el ensamblador sale SOLO del ir estructurado (IRProgram), nunca del ast ni del texto tac.
- si el backend rechaza el ir (un contrato roto entre etapas, o sea un bug del compilador y
  no del programa) no hay generacion parcial: se informa como diagnostico CPS-900 y los dos
  codigos quedan en None.
"""
from __future__ import annotations

from dataclasses import dataclass

import graphviz

from compiler import core_semantics, extended_semantics, frontend
from compiler.ast_visualizer import render_svg
from compiler.backend.mips.core_backend import IRContractError
from compiler.backend.mips.extended_backend import ExtendedMipsBackend
from compiler.backend.mips.peephole import PeepholeOptimizer, PeepholeReport
from compiler.diagnostics import Diagnostic, Severity
from compiler.ir.serializer import serialize
from compiler.runtime.runtime_layout import prepare
from compiler.scopes import SymbolTable
from compiler.tac.extended_generator import ExtendedTacGenerator

# excepciones puntuales que graphviz.Digraph.pipe() puede lanzar cuando el binario 'dot'
# no esta instalado o falla -- no se captura Exception a secas para no esconder bugs
# reales de _add_node/_label_for si algun dia se rompen.
_GRAPHVIZ_ERRORS = (graphviz.ExecutableNotFound, graphviz.CalledProcessError)

# codigo del unico diagnostico propio de la integracion (rango CPS-9xx: no choca con
# frontend 0xx, semantica core 1xx ni extendida 2xx)
BACKEND_ERROR_CODE = "CPS-900"


@dataclass(frozen=True, slots=True)
class CompilationResult:
    """
    contrato que consume el ide: exito, diagnosticos de todo el pipeline, svg del ast, el
    tac serializado, la tabla de simbolos completa (con la informacion de runtime que
    agrega prepare cuando hubo ir) y el ensamblador mips. tac_text, asm_text y
    asm_unoptimized son None si hubo cualquier error; peephole dice que hizo la mirilla.
    """
    success: bool
    diagnostics: list[Diagnostic]
    ast_svg: str | None
    tac_text: str | None
    symbols: SymbolTable
    asm_text: str | None = None          # ensamblador final (optimizado), el que se muestra y descarga
    asm_unoptimized: str | None = None   # antes de la mirilla (interno: tests de equivalencia)
    peephole: PeepholeReport | None = None


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
    diagnostics = list(extended_result.diagnostics)

    ast_svg = None
    if extended_result.ast is not None:
        try:
            ast_svg = render_svg(extended_result.ast)
        except _GRAPHVIZ_ERRORS:
            ast_svg = None

    success = extended_result.ast is not None and not extended_result.has_errors
    tac_text = asm_text = asm_unoptimized = None
    peephole = None
    if success:
        layout = prepare(extended_result)
        program = ExtendedTacGenerator.generate(extended_result, layout)
        try:
            assembly = ExtendedMipsBackend.generate(program, layout)
        except (IRContractError, ValueError) as error:
            success = False
            diagnostics.append(Diagnostic(
                code=BACKEND_ERROR_CODE,
                message=f"error interno del generador de ensamblador: {error}",
                line=1, column=1, severity=Severity.ERROR,
            ))
        else:
            optimized, peephole = PeepholeOptimizer.optimize(assembly)
            tac_text = serialize(program)
            asm_unoptimized = assembly.render()
            asm_text = optimized.render()

    return CompilationResult(
        success=success,
        diagnostics=diagnostics,
        ast_svg=ast_svg,
        tac_text=tac_text,
        symbols=extended_result.symbols,
        asm_text=asm_text,
        asm_unoptimized=asm_unoptimized,
        peephole=peephole,
    )
