"""
tests de integracion: compiler_service.compile_source, el UNICO compositor del pipeline
completo (frontend -> core -> extended -> visualizacion). corre sobre codigo fuente real,
sin mockear ninguna etapa -- es la prueba de que las 3 etapas encajan.
"""
from pathlib import Path

import dataclasses

from compiler.compiler_service import CompilationResult, compile_source

PROGRAM_DIR = Path(__file__).resolve().parents[2] / "program"


# ---------- contrato ----------

def test_compilation_result_tiene_exactamente_los_campos_esperados():
    # symbols se agrego para que el ide pueda mostrar la tabla de simbolos completa
    # (insercion/recuperacion/actualizacion/manejo de ambitos), no solo explicarla.
    field_names = {f.name for f in dataclasses.fields(CompilationResult)}
    assert field_names == {"success", "diagnostics", "ast_svg", "symbols"}


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


def test_programa_oficial_de_ejemplo_compila(tmp_path=None):
    program_file = PROGRAM_DIR / "program.cps"
    if not program_file.exists():
        return  # el archivo de ejemplo es opcional, no todos los entornos lo traen
    source = program_file.read_text(encoding="utf-8")
    result = compile_source(source)
    # no se exige que sea valido semanticamente (es un ejemplo, no una fixture curada),
    # pero el pipeline completo no debe reventar sobre el.
    assert isinstance(result.diagnostics, list)
