"""
fixtures de calificacion del backend core: cada tests/fixtures/mips_core/<nombre>.cps se
compila con el pipeline real (ANTLR -> semantica -> TAC -> CoreMipsBackend), se ejecuta en
mars y su salida tiene que ser exactamente <nombre>.out.
"""
from pathlib import Path

import pytest

from .support import backend_for, output

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "mips_core"
CASES = sorted(FIXTURES.glob("*.cps"))


def test_hay_fixtures_para_cada_rubro_core():
    names = {case.stem for case in CASES}
    assert {"variables_constantes", "aritmetica", "logica", "control_flujo", "funciones",
            "recursion", "anidadas", "strings", "error_division", "presion_registros"} <= names
    assert all(case.with_suffix(".out").is_file() for case in CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.stem)
def test_fixture_en_mars(case):
    expected = case.with_suffix(".out").read_text(encoding="utf-8").splitlines()
    assert output(case.read_text(encoding="utf-8")) == expected


def test_el_fixture_de_presion_de_registros_realmente_hace_spill():
    backend = backend_for((FIXTURES / "presion_registros.cps").read_text(encoding="utf-8"))
    backend.build()
    assert backend.allocator.spills > 0 and backend.allocator.reloads > 0
