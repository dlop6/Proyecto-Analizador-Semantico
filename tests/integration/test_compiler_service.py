"""
tests de integracion: compiler_service.compile_source, el UNICO compositor del pipeline
completo (frontend -> core -> extended -> runtime layout -> tac -> visualizacion). corre
sobre codigo fuente real, sin mockear ninguna etapa -- es la prueba de que todo encaja.
"""
from pathlib import Path

import dataclasses

from compiler.compiler_service import CompilationResult, compile_source

PROGRAM_DIR = Path(__file__).resolve().parents[2] / "program"


# ---------- contrato ----------

def test_compilation_result_tiene_exactamente_los_campos_esperados():
    # symbols se agrego para que el ide pueda mostrar la tabla de simbolos completa
    # (insercion/recuperacion/actualizacion/manejo de ambitos), no solo explicarla.
    # tac_text es el codigo intermedio serializado (None si hubo cualquier error).
    field_names = {f.name for f in dataclasses.fields(CompilationResult)}
    assert field_names == {"success", "diagnostics", "ast_svg", "tac_text", "symbols"}


# ---------- programa valido de punta a punta ----------

def test_programa_valido_compila_sin_diagnosticos_y_con_svg():
    source = """
    class Animal {
        let name: string;
        function constructor(name: string) { this.name = name; }
        function hablar(): string { return this.name; }
    }
    class Perro : Animal {
        function constructor(name: string) { this.name = name; }
        function hablar(): string { return this.name + " ladra."; }
    }
    let p: Animal = new Perro("Rex");
    print(p.hablar());
    let numeros: integer[] = [1, 2, 3];
    foreach (n in numeros) { print(n); }
    """
    result = compile_source(source)
    assert result.success is True
    assert result.diagnostics == []
    # el svg puede faltar si 'dot' no esta instalado en este entorno (degradacion
    # documentada), pero si esta, debe ser un documento svg de verdad.
    if result.ast_svg is not None:
        assert "<svg" in result.ast_svg


def test_programa_con_error_de_sintaxis_no_success_y_sin_svg():
    result = compile_source("let x: integer = ;")
    assert result.success is False
    assert result.ast_svg is None
    assert any(d.code == "CPS-001" for d in result.diagnostics)


def test_programa_con_errores_semanticos_de_clases_y_arreglos_no_success():
    source = """
    class A {}
    let a: A = new A();
    print(a.inexistente);
    let mixto = [1, "dos"];
    """
    result = compile_source(source)
    assert result.success is False
    codes = {d.code for d in result.diagnostics}
    assert "CPS-200" in codes
    assert "CPS-207" in codes


def test_programa_oficial_de_ejemplo_compila_sin_errores_y_genera_tac():
    # el ejemplo oficial usa concatenacion string + integer y un constructor heredado
    # (new Dog("Rex") con el constructor de Animal): ambos son validos
    source = (PROGRAM_DIR / "program.cps").read_text(encoding="utf-8")
    result = compile_source(source)
    assert result.success is True
    assert result.diagnostics == []
    assert "CALL fn::Animal.constructor, argc=2" in result.tac_text
    assert 'BIN +, "5 + 1 = ", addFive@global[5]' in result.tac_text
