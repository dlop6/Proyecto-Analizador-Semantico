"""
sustitucion (lsp): el generador extendido produce exactamente el mismo ir que el core
para cualquier programa del subconjunto core.
"""
import pytest

from compiler.ir.serializer import serialize
from compiler.runtime.runtime_layout import prepare
from compiler.tac.core_generator import CoreTacGenerator, UnsupportedConstructError
from compiler.tac.extended_generator import ExtendedTacGenerator

from .conftest import CORE_FIXTURES, FIXTURES, semantic, tac_for

CORE_VALID = sorted((CORE_FIXTURES / "valid").glob("*.cps"))


def test_hay_fixtures_core_para_comparar():
    assert len(CORE_VALID) >= 10


@pytest.mark.parametrize("path", CORE_VALID, ids=lambda p: p.stem)
def test_programa_core_produce_el_mismo_tac_dorado_que_el_core(path):
    expected = path.with_suffix(".tac").read_text(encoding="utf-8")
    assert tac_for(path.read_text(encoding="utf-8")) == expected


@pytest.mark.parametrize("path", CORE_VALID, ids=lambda p: p.stem)
def test_programa_core_produce_la_misma_salida_con_ambos_generadores(path):
    source = path.read_text(encoding="utf-8")
    core_result = semantic(source)
    core = serialize(CoreTacGenerator.generate(core_result, prepare(core_result)))
    extended_result = semantic(source)
    extended = serialize(ExtendedTacGenerator.generate(extended_result, prepare(extended_result)))
    assert core == extended


def test_lo_que_el_core_rechaza_el_extendido_lo_genera():
    source = (FIXTURES / "valid" / "complete.cps").read_text(encoding="utf-8")
    result = semantic(source)
    with pytest.raises(UnsupportedConstructError):
        CoreTacGenerator.generate(result, prepare(result))
    assert tac_for(source)
