"""
tests de compiler/frontend.py: la fachada congelada que consumen persona 2 y persona 3.
mezcla tests de contrato (introspeccion de la api) con tests de integracion (fuente
completa -> FrontendResult).
"""
import dataclasses
import inspect
from pathlib import Path

from compiler.frontend import MAX_SOURCE_BYTES, FrontendResult, analyze_file, analyze_source

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------- contrato (introspeccion, congela la api) ----------

def test_frontend_result_tiene_exactamente_los_atributos_del_pdf():
    field_names = {f.name for f in dataclasses.fields(FrontendResult)}
    assert field_names == {"ast", "symbols", "diagnostics"}


def test_analyze_source_firma_no_cambio():
    sig = inspect.signature(analyze_source)
    assert list(sig.parameters) == ["source"]


# ---------- integracion: program.cps oficial (smoke de gate a) ----------

def test_program_oficial_cero_diagnosticos():
    source = (FIXTURES_DIR / "valid" / "program_oficial.cps").read_text(encoding="utf-8")
    result = analyze_source(source)
    assert result.ok is True
    assert result.diagnostics == []
    assert result.ast is not None
    assert len(result.symbols.global_scope.symbols) > 0


def test_todas_las_fixtures_validas_sin_errores():
    for cps_file in sorted((FIXTURES_DIR / "valid").glob("*.cps")):
        source = cps_file.read_text(encoding="utf-8")
        result = analyze_source(source)
        errors = [d for d in result.diagnostics if d.severity.value == "error"]
        assert errors == [], f"{cps_file.name}: {errors}"


# ---------- error de sintaxis ----------

def test_error_de_sintaxis_ast_es_none():
    result = analyze_source("let x: integer = ;")
    assert result.ast is None
    assert len(result.diagnostics) >= 1
    assert result.ok is False


def test_error_de_sintaxis_no_escribe_a_stderr(capsys):
    analyze_source("let x: integer = ;")
    captured = capsys.readouterr()
    assert captured.err == ""


def test_multiples_errores_de_sintaxis_con_recovery():
    result = analyze_source("let x: integer = ; let y: string = ;")
    assert len(result.diagnostics) >= 2


# ---------- fuente vacia / solo comentarios ----------

def test_fuente_vacia():
    result = analyze_source("")
    assert result.ast is not None
    assert len(result.ast.statements) == 0
    assert result.diagnostics == []


def test_fuente_solo_comentarios():
    result = analyze_source("// nada\n/* tampoco esto */")
    assert len(result.ast.statements) == 0
    assert result.diagnostics == []


# ---------- limite de tamaño ----------

def test_fuente_excede_limite_reporta_cps004():
    huge = "x" * (MAX_SOURCE_BYTES + 1)
    result = analyze_source(huge)
    codes = [d.code for d in result.diagnostics]
    assert "CPS-004" in codes
    assert result.ast is None


# ---------- idempotencia y determinismo ----------

def test_idempotencia_dos_llamadas_no_acumulan():
    source = "let x: integer = 1;\nlet x: integer = 2;"
    r1 = analyze_source(source)
    r2 = analyze_source(source)
    assert len(r1.diagnostics) == len(r2.diagnostics) == 1


def test_determinismo_misma_fuente_mismo_resultado():
    source = "let x: integer = 1;\nlet x: integer = 2;"
    r1 = analyze_source(source)
    r2 = analyze_source(source)
    keys1 = [(d.code, d.line, d.column, d.message) for d in r1.diagnostics]
    keys2 = [(d.code, d.line, d.column, d.message) for d in r2.diagnostics]
    assert keys1 == keys2


# ---------- redeclaracion / duplicado con linea y columna (checklist gate a) ----------

def test_redeclaracion_reporta_linea_y_columna():
    result = analyze_source("let x: integer = 1;\nlet x: integer = 2;")
    dup = next(d for d in result.diagnostics if d.code == "CPS-020")
    assert dup.line == 2
    assert dup.column > 0


# ---------- funciones y clases visibles antes de sus cuerpos ----------

def test_funciones_y_clases_predeclaradas():
    result = analyze_source(
        "function fact(n: integer): integer { return fact(n - 1); }\n"
        "class A : B {}\n"
        "class B {}\n"
    )
    assert result.diagnostics == []


# ---------- analyze_file ----------

def test_analyze_file_lee_desde_disco():
    path = FIXTURES_DIR / "valid" / "minimal.cps"
    result = analyze_file(str(path))
    assert result.ok is True
