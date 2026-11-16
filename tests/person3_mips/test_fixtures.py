"""
fixtures de calificacion del backend extendido: cada tests/fixtures/mips_extended/<n>.cps
pasa por compile_source (ANTLR -> semantica -> TAC -> ExtendedMipsBackend -> mirilla), el
.asm que mostraria la gui se ejecuta en mars y su salida tiene que ser exactamente <n>.out.
"""
from pathlib import Path

import pytest

from .support import pipeline_output

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "mips_extended"
CASES = sorted(FIXTURES.glob("*.cps"))


def test_hay_fixtures_para_cada_rubro_de_persona_3():
    names = {case.stem for case in CASES}
    assert {"arreglos", "matrices", "foreach", "clases_objetos", "herencia", "try_catch",
            "error_no_capturado", "mirilla"} <= names
    assert all(case.with_suffix(".out").is_file() for case in CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.stem)
def test_fixture_en_mars(case):
    expected = case.with_suffix(".out").read_text(encoding="utf-8").splitlines()
    assert pipeline_output(case.read_text(encoding="utf-8")) == expected


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.stem)
def test_fixture_sin_mirilla_da_la_misma_salida(case):
    expected = case.with_suffix(".out").read_text(encoding="utf-8").splitlines()
    assert pipeline_output(case.read_text(encoding="utf-8"), optimized=False) == expected
