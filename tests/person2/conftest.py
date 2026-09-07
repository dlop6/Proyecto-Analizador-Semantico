"""fixtures y helpers compartidos para los tests de la semantica core."""
from pathlib import Path

import pytest

from compiler.core_semantics import CoreSemanticResult, analyze
from compiler.frontend import analyze_source

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def analyze_full(source: str) -> CoreSemanticResult:
    """atajo: corre el frontend y encima la semantica core, en una sola llamada."""
    frontend_result = analyze_source(source)
    assert frontend_result.ast is not None, f"error de sintaxis inesperado: {frontend_result.diagnostics}"
    return analyze(frontend_result)


@pytest.fixture
def cps_fixture():
    """lee un .cps de fixtures/valid o fixtures/invalid por nombre relativo, ej 'valid/functions.cps'."""
    def _read(relative_path: str) -> str:
        path = FIXTURES_DIR / relative_path
        return path.read_text(encoding="utf-8")
    return _read


def codes_of(result: CoreSemanticResult) -> set[str]:
    return {d.code for d in result.diagnostics}
