"""fixtures y helpers compartidos para los tests de la semantica extendida."""
from pathlib import Path

import pytest

from compiler.core_semantics import analyze as analyze_core
from compiler.extended_semantics import ExtendedSemanticResult, analyze as analyze_extended
from compiler.frontend import analyze_source

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def analyze_full(source: str) -> ExtendedSemanticResult:
    """atajo: corre frontend -> semantica core -> semantica extendida, en una sola llamada."""
    frontend_result = analyze_source(source)
    assert frontend_result.ast is not None, f"error de sintaxis inesperado: {frontend_result.diagnostics}"
    core_result = analyze_core(frontend_result)
    return analyze_extended(core_result)


@pytest.fixture
def cps_fixture():
    """lee un .cps de fixtures/valid o fixtures/invalid por nombre relativo, ej 'valid/classes.cps'."""
    def _read(relative_path: str) -> str:
        path = FIXTURES_DIR / relative_path
        return path.read_text(encoding="utf-8")
    return _read


def codes_of(result: ExtendedSemanticResult) -> set[str]:
    return {d.code for d in result.diagnostics}
