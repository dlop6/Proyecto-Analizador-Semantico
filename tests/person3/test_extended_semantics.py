"""
tests de compiler/extended_semantics.py: la fachada congelada de la semantica extendida,
analoga a core_semantics.analyze y frontend.analyze_source.
"""
import dataclasses
import inspect

from compiler.core_semantics import analyze as analyze_core
from compiler.extended_semantics import ExtendedSemanticResult, analyze
from compiler.frontend import analyze_source

from .conftest import analyze_full, codes_of


# ---------- contrato ----------

def test_extended_semantic_result_tiene_exactamente_los_atributos_del_pdf():
    field_names = {f.name for f in dataclasses.fields(ExtendedSemanticResult)}
    assert field_names == {"ast", "symbols", "diagnostics"}


def test_analyze_firma_no_cambio():
    sig = inspect.signature(analyze)
    assert list(sig.parameters) == ["core_result"]


def test_no_reconstruye_ast_ni_tabla_de_simbolos():
    frontend_result = analyze_source("let x: integer = 1;")
    core_result = analyze_core(frontend_result)
    result = analyze(core_result)
    assert result.ast is core_result.ast
    assert result.symbols is core_result.symbols


# ---------- core sin ast: no hay nada que analizar ----------

def test_core_sin_ast_no_corre_el_visitor():
    frontend_result = analyze_source("let x: integer = ;")
    core_result = analyze_core(frontend_result)
    assert core_result.ast is None
    result = analyze(core_result)
    assert result.ast is None
    assert result.diagnostics == core_result.diagnostics


# ---------- diagnosticos previos se preservan junto a los nuevos ----------

def test_conserva_diagnosticos_previos_y_agrega_los_propios():
    source = 'class Animal {}\nlet a: Animal = new Animal();\nprint(a.inexistente);\nlet x: integer = "no";'
    result = analyze_full(source)
    codes = codes_of(result)
    assert "CPS-200" in codes  # de la semantica extendida (miembro inexistente)
    assert "CPS-100" in codes  # de la semantica core (tipo incompatible)


# ---------- programa valido: cero diagnosticos ----------

def test_programa_valido_cero_diagnosticos():
    source = """
    class Animal {
        let name: string;
        function constructor(name: string) { this.name = name; }
        function hablar(): string { return this.name; }
    }
    let a: Animal = new Animal("Rex");
    print(a.hablar());
    let numeros: integer[] = [1, 2, 3];
    print(numeros[0]);
    """
    result = analyze_full(source)
    assert result.diagnostics == []
    assert result.ok is True


def test_expresion_extendida_queda_con_inferred_type():
    source = "class A {}\nlet a: A = new A();"
    frontend_result = analyze_source(source)
    core_result = analyze_core(frontend_result)
    result = analyze(core_result)
    var_decl = result.ast.statements[1]
    assert var_decl.initializer.inferred_type is not None


# ---------- catalogo propio no vive en los otros catalogos ----------

def test_catalogo_cps2xx_no_vive_en_diagnostics_py():
    from compiler.diagnostics import _MESSAGES as frontend_messages
    assert not any(code.startswith("CPS-2") for code in frontend_messages)


def test_catalogo_cps2xx_no_vive_en_core_semantic_visitor():
    from compiler.core_semantic_visitor import _MESSAGES as core_messages
    assert not any(code.startswith("CPS-2") for code in core_messages)
