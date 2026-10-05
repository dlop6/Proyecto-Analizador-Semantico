"""
contrato publico del generador core (gate B): firma congelada, rechazo explicito de
resultados con errores, ejemplos de INTERMEDIATE_CODE.md y construcciones que le tocan
al generador extendido.
"""
import inspect
from pathlib import Path

import pytest

from compiler.ir.builder import IRError
from compiler.ir.model import IRProgram
from compiler.runtime.runtime_layout import prepare
from compiler.tac.core_generator import CoreTacGenerator, UnsupportedConstructError

from .conftest import program_for, semantic, tac_for

DOC = Path(__file__).resolve().parents[2] / "docs" / "INTERMEDIATE_CODE.md"


def test_generate_es_classmethod_con_la_firma_del_pdf():
    assert isinstance(inspect.getattr_static(CoreTacGenerator, "generate"), classmethod)
    assert list(inspect.signature(CoreTacGenerator.generate).parameters) == ["semantic_result", "runtime_layout"]


def test_generate_devuelve_un_ir_program():
    assert isinstance(program_for("print(1);"), IRProgram)


def test_programa_vacio_no_genera_instrucciones():
    program = program_for("")
    assert program.entry.instructions == () and program.functions == ()


def test_rechaza_resultado_con_error_semantico_aunque_reciba_un_layout_valido():
    valid = semantic("let x: integer = 1;")
    broken = semantic('let x: integer = "no";')
    with pytest.raises(ValueError, match="no se genera ir"):
        CoreTacGenerator.generate(broken, prepare(valid))


def test_rechaza_resultado_sin_ast():
    result = semantic("let x: integer = ;")
    assert result.ast is None
    with pytest.raises(ValueError, match="no se genera ir"):
        CoreTacGenerator.generate(result, None)


def test_rechaza_un_layout_que_no_salio_de_prepare():
    with pytest.raises(IRError, match="RuntimeLayout"):
        CoreTacGenerator.generate(semantic("print(1);"), object())


def test_warnings_no_bloquean_la_generacion():
    result = semantic("function f(): integer { return 1; print(2); }")
    assert result.diagnostics and not result.has_errors
    assert "PRINT 2" in tac_for("function f(): integer { return 1; print(2); }")


def test_dos_generaciones_no_comparten_estado():
    source = "let x: integer = 1 + 2; if (x > 1) { print(x); }"
    first = tac_for(source)
    tac_for("while (true) { break; }")  # otra compilacion en el medio no corre etiquetas ni temporales
    assert tac_for(source) == first
    assert "L_if_end_0" in first


# ----------------------------------------------------------------------
# los ejemplos core del documento salen tal cual del generador
# ----------------------------------------------------------------------

DOC_EXAMPLES = {
    "aritmetica": "let a: integer = 1; let b: integer = 2; let c: integer = 3;\n"
                  "let x: integer = 0; let y: integer = 0;\n"
                  "x = a + b * c;\ny = b - c;",
    "cortocircuito": "let p: boolean = true; let q: boolean = false; let r: boolean = p && q;",
    "recursion": "function factorial(n: integer): integer {\n"
                 "  if (n <= 1) { return 1; }\n"
                 "  return n * factorial(n - 1);\n"
                 "}",
    "anidada": "function contador(): integer {\n"
               "  let total: integer = 10;\n"
               "  function sumar(n: integer): integer { return total + n; }\n"
               "  return sumar(5);\n"
               "}",
}


@pytest.mark.parametrize("name", DOC_EXAMPLES)
def test_ejemplo_core_del_documento_sale_del_generador(name):
    text = tac_for(DOC_EXAMPLES[name])
    doc = DOC.read_text(encoding="utf-8")
    if name == "aritmetica":
        # el documento muestra solo las dos sentencias, sin los MOV de las declaraciones
        text = "\n".join(text.splitlines()[5:]) + "\n"
    elif name == "cortocircuito":
        text = "\n".join(text.splitlines()[2:]) + "\n"
    assert text.rstrip("\n") in doc, text


# ----------------------------------------------------------------------
# fuera del subconjunto core: falla explicito, nunca tac a medias
# ----------------------------------------------------------------------

@pytest.mark.parametrize("source,node", [
    ("class A { }", "ClassDecl"),
    ("let a: integer[] = [1, 2];", "ArrayLiteral"),
    ("try { print(1); } catch (e) { print(e); }", "TryCatchStatement"),
    ("function f(a: integer[]) { foreach (x in a) { print(x); } }", "ForeachStatement"),
    ("function f(a: integer[]): integer { return a[0]; }", "IndexAccess"),
])
def test_construcciones_extendidas_no_se_generan_en_el_core(source, node):
    with pytest.raises(UnsupportedConstructError, match=node):
        program_for(source)


def test_unsupported_es_un_error_del_ir():
    assert issubclass(UnsupportedConstructError, IRError)
