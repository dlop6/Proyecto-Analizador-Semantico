"""
tests de compiler/core_semantics.py: la fachada congelada de la semantica core, analoga
a frontend.analyze_source. mezcla contrato (introspeccion) con integracion basica.
"""
import dataclasses
import inspect

from compiler.core_semantics import CoreSemanticResult, analyze
from compiler.frontend import analyze_source

from .conftest import analyze_full, codes_of


# ---------- contrato ----------

def test_core_semantic_result_tiene_exactamente_los_atributos_del_pdf():
    field_names = {f.name for f in dataclasses.fields(CoreSemanticResult)}
    assert field_names == {"ast", "symbols", "diagnostics"}


def test_analyze_firma_no_cambio():
    sig = inspect.signature(analyze)
    assert list(sig.parameters) == ["frontend_result"]


def test_no_reconstruye_ast_ni_tabla_de_simbolos():
    frontend_result = analyze_source("let x: integer = 1;")
    result = analyze(frontend_result)
    assert result.ast is frontend_result.ast
    assert result.symbols is frontend_result.symbols


# ---------- frontend con error de sintaxis: no hay nada que analizar ----------

def test_frontend_sin_ast_no_corre_el_visitor():
    frontend_result = analyze_source("let x: integer = ;")
    assert frontend_result.ast is None
    result = analyze(frontend_result)
    assert result.ast is None
    assert result.diagnostics == frontend_result.diagnostics


# ---------- diagnosticos del frontend se preservan junto a los de la semantica core ----------

def test_conserva_diagnosticos_del_frontend_y_agrega_los_propios():
    frontend_result = analyze_source("let x: integer = 1;\nlet x: integer = 2;\nlet y: integer = \"a\";")
    result = analyze(frontend_result)
    codes = codes_of(result)
    assert "CPS-020" in codes  # del frontend (redeclaracion)
    assert "CPS-100" in codes  # de la semantica core (tipo incompatible)


def test_acumula_multiples_diagnosticos_sin_detenerse_en_el_primero():
    result = analyze_full("let a: integer = \"x\"; let b: integer = \"y\"; let c = w;")
    codes = codes_of(result)
    assert len([d for d in result.diagnostics if d.code == "CPS-100"]) == 2
    assert "CPS-103" in codes


# ---------- programa valido: cero diagnosticos, inferred_type presente ----------

def test_programa_valido_cero_diagnosticos():
    result = analyze_full("let x: integer = 1;\nlet y = x + 1;\nprint(y);")
    assert result.diagnostics == []
    assert result.ok is True


def test_expresion_core_queda_con_inferred_type():
    frontend_result = analyze_source("let y = 1 + 2;")
    result = analyze(frontend_result)
    var_decl = result.ast.statements[0]
    assert var_decl.initializer.inferred_type is not None


# ---------- catalogo propio de la semantica core no usa el catalogo del frontend ----------

def test_catalogo_cps1xx_no_vive_en_diagnostics_py():
    from compiler.diagnostics import _MESSAGES as frontend_messages
    assert not any(code.startswith("CPS-1") for code in frontend_messages)
