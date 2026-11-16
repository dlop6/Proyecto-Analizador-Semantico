"""
lsp: el backend extendido sustituye al core. para cualquier programa core genera EXACTAMENTE
el mismo ensamblador (sin vtables, sin helpers nuevos, mismos destinos de error).
"""
from pathlib import Path

import pytest

from compiler.backend.mips.core_backend import CoreMipsBackend
from compiler.backend.mips.extended_backend import ExtendedMipsBackend

from tests.mips_base.pipeline import ir_for

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
CORE_PROGRAMS = sorted((FIXTURES / "mips_core").glob("*.cps")) + sorted((FIXTURES / "core_tac" / "valid").glob("*.cps"))


def test_hay_programas_core_para_comparar():
    assert len(CORE_PROGRAMS) >= 20


@pytest.mark.parametrize("case", CORE_PROGRAMS, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_programa_core_genera_el_mismo_ensamblador(case):
    program, layout = ir_for(case.read_text(encoding="utf-8"))
    core = CoreMipsBackend.generate(program, layout).render()
    extended = ExtendedMipsBackend.generate(program, layout).render()
    assert extended == core
