"""fixtures .cps del tac extendido: salida dorada exacta, determinismo y bloqueo del ir con errores."""
import pytest

from compiler.compiler_service import compile_source
from compiler.runtime.runtime_layout import prepare
from compiler.tac.extended_generator import ExtendedTacGenerator

from .conftest import FIXTURES, semantic, tac_for

VALID = sorted((FIXTURES / "valid").glob("*.cps"))
INVALID = sorted((FIXTURES / "invalid").glob("*.cps"))


def test_hay_fixtures_por_cada_constructo():
    assert {p.stem for p in VALID} >= {
        "arrays", "nested_arrays", "foreach", "foreach_break_continue", "classes_objects",
        "field_initializers", "inheritance_override", "this_in_nested_function", "try_catch", "complete",
    }
    assert {p.stem for p in INVALID} >= {"array_errors", "class_errors", "foreach_errors", "try_catch_errors"}


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_fixture_valida_genera_el_tac_esperado(path):
    expected = path.with_suffix(".tac").read_text(encoding="utf-8")
    assert tac_for(path.read_text(encoding="utf-8")) == expected


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_generacion_determinista(path):
    source = path.read_text(encoding="utf-8")
    assert tac_for(source) == tac_for(source)


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_el_servicio_entrega_el_mismo_tac(path):
    result = compile_source(path.read_text(encoding="utf-8"))
    assert result.success is True
    assert result.tac_text == path.with_suffix(".tac").read_text(encoding="utf-8")


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_fixture_invalida_queda_en_fase_semantica_y_no_genera_ir(path):
    source = path.read_text(encoding="utf-8")
    result = semantic(source)
    assert result.ast is not None  # sintaxis limpia: el error es semantico
    assert result.has_errors
    with pytest.raises(ValueError, match="no se genera ir"):
        ExtendedTacGenerator.generate(result, None)
    with pytest.raises(ValueError, match="no se genera ir"):
        prepare(result)
    compiled = compile_source(source)
    assert compiled.success is False
    assert compiled.tac_text is None
