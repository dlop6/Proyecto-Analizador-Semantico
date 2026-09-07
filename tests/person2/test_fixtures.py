"""smoke tests basados en archivos .cps completos, complementan los tests unitarios de arriba."""
from .conftest import codes_of


def test_fixture_valida_no_reporta_diagnosticos(cps_fixture):
    from compiler.frontend import analyze_source
    from compiler.core_semantics import analyze

    source = cps_fixture("valid/functions_and_control_flow.cps")
    frontend_result = analyze_source(source)
    assert frontend_result.ast is not None, frontend_result.diagnostics
    result = analyze(frontend_result)
    assert result.diagnostics == [], result.diagnostics


def test_fixture_invalida_reporta_todos_los_errores_esperados(cps_fixture):
    from compiler.frontend import analyze_source
    from compiler.core_semantics import analyze

    source = cps_fixture("invalid/type_errors.cps")
    frontend_result = analyze_source(source)
    assert frontend_result.ast is not None, frontend_result.diagnostics
    result = analyze(frontend_result)
    codes = codes_of(result)
    assert {"CPS-100", "CPS-103", "CPS-109", "CPS-112", "CPS-113", "CPS-116"} <= codes
    assert result.ok is False
