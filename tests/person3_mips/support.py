"""
helpers de las pruebas del backend extendido: fuente .cps -> ir real -> ExtendedMipsBackend
-> mars. reusa el pipeline, el runner de mars y los helpers del core en vez de duplicarlos.
"""
from __future__ import annotations

from compiler.backend.mips.extended_backend import ExtendedMipsBackend
from compiler.compiler_service import compile_source

from tests.mips_base.mars_runner import MarsResult, run_mars
from tests.person2_mips import support as core_support

MAX_STEPS = core_support.MAX_STEPS


def assemble(source: str) -> str:
    return core_support.assemble(source, ExtendedMipsBackend)


def run(source: str) -> MarsResult:
    return core_support.run(source, backend_class=ExtendedMipsBackend)


def output(source: str) -> list[str]:
    """lineas que imprimio el programa; falla con la salida completa de mars si algo salio mal."""
    return core_support.output(source, ExtendedMipsBackend)


def pipeline_output(source: str, optimized: bool = True) -> list[str]:
    """igual que output, pero por compile_source (el camino de la gui, con mirilla)."""
    result = compile_source(source)
    assert result.success, [(d.code, d.line, d.column, d.message) for d in result.diagnostics]
    asm = result.asm_text if optimized else result.asm_unoptimized
    mars = run_mars(asm, max_steps=MAX_STEPS)
    assert mars.ok, mars.raw
    return mars.stdout.splitlines()
