"""
pipeline completo hasta mips (proyecto 03): recuperacion de errores sin generar codigo,
recompilacion limpia y la gui (pestaña MIPS, copia y descarga del .asm). todo entra por
compile_source o por POST /api/compile, igual que la gui. nada mockeado.
"""
from pathlib import Path

import pytest

from compiler.compiler_service import compile_source
from ide.app import app

from tests.mips_base.mars_runner import run_mars

ROOT = Path(__file__).resolve().parents[2]
GRADING = ROOT / "tests" / "grading" / "fixtures"
SCRIPT = ROOT / "ide" / "static" / "app.js"
VALID = "let v: integer[] = [1, 2];\nprint(v[1]);\n"


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def _codes(result):
    return [d.code for d in result.diagnostics]


def _assert_no_code(result):
    assert result.success is False
    assert result.tac_text is None and result.asm_text is None and result.asm_unoptimized is None
    assert result.peephole is None


# ---------- recuperacion: varios errores, sin duplicados, sin codigo ----------

def test_dos_errores_lexicos_en_una_corrida_y_sin_tac_ni_asm():
    result = compile_source((GRADING / "lexical_recovery.cps").read_text(encoding="utf-8"))
    assert _codes(result).count("CPS-000") >= 2
    _assert_no_code(result)


def test_dos_errores_sintacticos_recuperables_y_sin_tac_ni_asm():
    result = compile_source((GRADING / "syntax_recovery.cps").read_text(encoding="utf-8"))
    assert _codes(result).count("CPS-001") >= 2
    _assert_no_code(result)


def test_varios_errores_semanticos_en_una_corrida_y_sin_tac_ni_asm():
    result = compile_source((GRADING / "semantic_errors.cps").read_text(encoding="utf-8"))
    assert {"CPS-103", "CPS-119", "CPS-120", "CPS-215"} <= set(_codes(result))
    _assert_no_code(result)


def test_errores_semanticos_de_clases_arreglos_y_try_bloquean_el_ensamblador():
    result = compile_source("""
    class A { let x: integer; }
    let a: A = new A();
    print(a.noExiste);
    let v: integer[] = [1, "dos"];
    try { print(1); } catch (e) { let n: integer = e; }
    """)
    assert len(result.diagnostics) >= 3
    _assert_no_code(result)


def test_sin_diagnosticos_duplicados():
    source = "let a: integer = \"x\";\nlet b: integer = \"y\";\nprint(noExiste);\nprint(noExiste);\n"
    result = compile_source(source)
    keys = [(d.code, d.line, d.column, d.message) for d in result.diagnostics]
    assert len(keys) == len(set(keys))
    assert len(keys) >= 3


def test_un_error_no_provoca_cascada_de_errores_derivados():
    # el identificador no declarado es la causa primaria; usarlo en una suma no agrega otro error
    result = compile_source("let x: integer = noDeclarado + 1;\nprint(x * 2);\n")
    assert _codes(result) == ["CPS-103"]


def test_recompilar_despues_de_un_error_no_arrastra_estado():
    bad = compile_source("let x: integer = ;")
    good = compile_source(VALID)
    again = compile_source(VALID)
    assert bad.asm_text is None
    assert good.success and good.diagnostics == []
    assert good.asm_text == again.asm_text   # determinista, sin estado entre compilaciones


def test_las_advertencias_no_bloquean_el_ensamblador():
    result = compile_source("function f(): integer { return 1; print(2); }\nprint(f());\n")
    assert result.diagnostics and all(d.severity.value == "warning" for d in result.diagnostics)
    assert result.success and result.asm_text is not None


# ---------- programa valido: tac + mips ejecutable ----------

def test_programa_valido_genera_tac_y_mips_que_corre_en_mars():
    result = compile_source(VALID)
    assert result.success and result.tac_text and result.asm_text
    assert result.asm_text.startswith(".data\n") and "\n.text\nmain:\n" in result.asm_text
    mars = run_mars(result.asm_text)
    assert mars.ok, mars.raw
    assert mars.stdout.splitlines() == ["2"]


def test_el_ensamblador_sale_del_ir_y_no_del_ast():
    import compiler.compiler_service as service
    source = Path(service.__file__).read_text(encoding="utf-8")
    assert "ExtendedMipsBackend.generate(program, layout)" in source   # program = IRProgram del tac
    assert "extended_result.ast, " not in source.split("ExtendedMipsBackend")[1]


# ---------- gui ----------

def test_index_ofrece_la_pestana_mips_con_copia_y_descarga(client):
    html = client.get("/").data
    assert b'type="file" accept=".cps"' in html
    for fragment in (b'data-view="asm"', b'id="asm-container"', b'id="asm-code"', b'id="asm-copy"',
                     b'id="asm-download"', b'id="asm-peephole"'):
        assert fragment in html, fragment


def test_api_devuelve_el_mismo_asm_que_compile_source(client):
    body = client.post("/api/compile", json={"source": VALID}).get_json()
    assert body["success"] is True
    assert body["asm_text"] == compile_source(VALID).asm_text
    assert body["peephole"]["summary"].startswith("mirilla:")
    assert set(body["peephole"]["applied"]) == {"R1", "R2", "R3", "R4", "R5", "R6"}


@pytest.mark.parametrize("source", [
    "@ let x: integer = 1;",                 # lexico
    "let x: integer = ;",                    # sintactico
    "let x: integer = \"texto\";",           # semantico
])
def test_api_con_cualquier_error_no_devuelve_tac_ni_asm(client, source):
    body = client.post("/api/compile", json={"source": source}).get_json()
    assert body["success"] is False
    assert body["tac_text"] is None and body["asm_text"] is None and body["peephole"] is None


def test_cliente_limpia_el_mips_ante_errores_y_nunca_muestra_uno_viejo():
    script = SCRIPT.read_text(encoding="utf-8")
    assert "renderAsm(data.success ? data.asm_text : null, data.peephole, ASM_NOT_GENERATED)" in script
    assert script.count("renderAsm(null, null, ASM_NOT_GENERATED)") >= 2   # error del servidor y de red
    assert "asmCodeEl.replaceChildren()" in script


def test_cliente_copia_y_descarga_exactamente_el_asm_mostrado():
    script = SCRIPT.read_text(encoding="utf-8")
    assert "navigator.clipboard.writeText(currentAsm)" in script
    assert "downloadText(currentAsm, asmFileName())" in script
    render = script[script.index("function renderAsm"):script.index("async function copyAsm")]
    assert "innerHTML" not in render and "createTextNode" in render
