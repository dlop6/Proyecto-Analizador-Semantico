"""
fixtures .cps del tac core contra su salida esperada (.tac al lado). los .tac se
revisaron a mano una vez; desde ahi cualquier cambio de lowering que altere el texto
rompe este test. ademas: determinismo y no-generacion cuando hay errores.
"""
import pytest

from compiler.runtime.runtime_layout import prepare
from compiler.tac.core_generator import CoreTacGenerator

from .conftest import FIXTURES, semantic, tac_for

VALID = sorted((FIXTURES / "valid").glob("*.cps"))
INVALID = sorted((FIXTURES / "invalid").glob("*.cps"))


def test_hay_fixtures():
    assert len(VALID) >= 10
    assert {p.stem for p in INVALID} >= {"lexical_error", "syntax_error", "semantic_error", "multiple_semantic_errors"}


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_fixture_valida_genera_el_tac_esperado(path):
    expected = path.with_suffix(".tac").read_text(encoding="utf-8")
    assert tac_for(path.read_text(encoding="utf-8")) == expected


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_generacion_determinista(path):
    source = path.read_text(encoding="utf-8")
    assert tac_for(source) == tac_for(source)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_fixture_invalida_no_genera_ir(path):
    result = semantic(path.read_text(encoding="utf-8"))
    assert result.has_errors
    with pytest.raises(ValueError, match="no se genera ir"):
        CoreTacGenerator.generate(result, None)
    with pytest.raises(ValueError, match="no se genera ir"):
        prepare(result)


def test_errores_multiples_se_reportan_todos_y_bloquean_el_ir():
    result = semantic((FIXTURES / "invalid" / "multiple_semantic_errors.cps").read_text(encoding="utf-8"))
    assert len({d.code for d in result.diagnostics if d.severity.value == "error"}) >= 3
    with pytest.raises(ValueError):
        CoreTacGenerator.generate(result, None)
