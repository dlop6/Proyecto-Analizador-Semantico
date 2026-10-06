"""
pruebas de punta a punta por cada fila de la rubrica de generacion de codigo intermedio
(25 pts). cada caso entra por la misma puerta que la gui (POST /api/compile del ide flask)
y verifica el tac que se mostraria en la pagina. nada mockeado.
"""
import re

import pytest

from ide.app import app


@pytest.fixture
def compile_tac():
    app.config.update(TESTING=True)
    client = app.test_client()

    def _compile(source: str) -> dict:
        response = client.post("/api/compile", json={"source": source})
        assert response.status_code == 200
        return response.get_json()

    return _compile


def _tac(body: dict) -> list[str]:
    assert body["success"] is True, body["diagnostics"]
    return [line.strip() for line in body["tac_text"].splitlines() if line.strip()]


# ---------- diseno del codigo intermedio (3 pts) ----------

def test_diseno_del_ir_usa_solo_opcodes_del_contrato_y_formato_estable(compile_tac):
    allowed = {
        "MOV", "BIN", "UN", "PRINT", "LABEL", "GOTO", "IF_TRUE", "IF_FALSE", "FUNC_BEGIN", "FUNC_END",
        "ARG", "CALL", "RETURN", "NEW_ARR", "ARR_GET", "ARR_SET", "LEN", "NEW_OBJ", "GET_FIELD",
        "SET_FIELD", "CALL_METHOD", "TRY_BEGIN", "TRY_END", "CATCH",
    }
    source = """
    class A { let v: integer = 1; function m(): integer { return this.v; } }
    function f(n: integer): integer { if (n <= 0) { return 0; } return f(n - 1); }
    let a: A = new A();
    let xs: integer[] = [1, 2];
    foreach (x in xs) { print(x + a.m() + f(x)); }
    try { print(xs[9]); } catch (e) { print(e); }
    """
    for line in _tac(compile_tac(source)):
        opcode = line.split(" = ")[1].split()[0] if " = " in line.split(",")[0] else line.split()[0]
        assert opcode in allowed, line


# ---------- variables y constantes (1 pt) ----------

def test_variables_y_constantes(compile_tac):
    lines = _tac(compile_tac("let a: integer = 5; const B: string = \"hola\"; var c: boolean = true; a = 7;"))
    assert lines == [
        "MOV a@global[0], 5",
        'MOV B@global[1], "hola"',
        "MOV c@global[2], true",
        "MOV a@global[0], 7",
    ]


# ---------- expresiones aritmeticas (1 pt) ----------

def test_expresiones_aritmeticas_con_precedencia(compile_tac):
    lines = _tac(compile_tac("let a: integer = 1; let x: integer = a + 2 * 3 - -a % 4;"))
    assert lines[1:] == [
        "t0 = BIN *, 2, 3",
        "t1 = BIN +, a@global[0], t0",
        "t0 = UN -, a@global[0]",
        "t2 = BIN %, t0, 4",
        "t0 = BIN -, t1, t2",
        "MOV x@global[1], t0",
    ]


# ---------- expresiones logicas (1 pt) ----------

def test_expresiones_logicas_con_cortocircuito(compile_tac):
    lines = _tac(compile_tac("let p: boolean = true; let q: boolean = false; let r: boolean = p && !q || p;"))
    assert not any(line.startswith(("t", "BIN")) and ("&&" in line or "||" in line) for line in lines)
    assert any(line.startswith("IF_FALSE") and "L_and_end" in line for line in lines)
    assert any(line.startswith("IF_TRUE") and "L_or_end" in line for line in lines)


# ---------- arreglos (1 pt) ----------

def test_arreglos(compile_tac):
    lines = _tac(compile_tac("let m: integer[][] = [[1, 2], [3]]; m[1][0] = m[0][1];"))
    assert lines[0] == "t0 = NEW_ARR 2"
    assert "ARR_SET t0, 0, t1" in lines
    assert any(line.endswith("= ARR_GET m@global[0], 1") for line in lines)
    assert lines[-1].startswith("ARR_SET ")


# ---------- control de flujo: if/else/while/do-while/for/foreach/switch (3 pts) ----------

def test_control_de_flujo_completo(compile_tac):
    source = """
    let n: integer = 3;
    if (n > 1) { print(1); } else { print(2); }
    while (n > 0) { n = n - 1; if (n == 1) { continue; } }
    do { n = n + 1; } while (n < 2);
    for (let i: integer = 0; i < 2; i = i + 1) { if (i == 1) { break; } }
    let xs: integer[] = [1];
    foreach (x in xs) { print(x); }
    switch (n) { case 1: print("uno"); default: print("otro"); }
    """
    labels = {re.sub(r"_\d+$", "", line.split()[1]) for line in _tac(compile_tac(source)) if line.startswith("LABEL")}
    assert labels >= {
        "L_if_else", "L_if_end", "L_while_cond", "L_while_end", "L_do_body", "L_do_cond", "L_do_end",
        "L_for_cond", "L_for_step", "L_for_end", "L_foreach_cond", "L_foreach_step", "L_foreach_end",
        "L_switch_case", "L_switch_default", "L_switch_end",
    }


# ---------- funciones y parametros (2 pts) ----------

def test_funciones_y_parametros(compile_tac):
    body = compile_tac("function suma(a: integer, b: integer): integer { return a + b; } print(suma(1, 2));")
    text = body["tac_text"]
    assert "FUNC_BEGIN fn::suma, frame=2" in text
    assert "t0 = BIN +, a@frame[0], b@frame[1]" in text
    assert "ARG 1\n  ARG 2\n  CALL t0, fn::suma, argc=2" in text


# ---------- recursividad (2 pts) ----------

def test_recursividad_es_un_call_a_la_misma_etiqueta(compile_tac):
    source = "function fact(n: integer): integer { if (n <= 1) { return 1; } return n * fact(n - 1); } print(fact(5));"
    text = compile_tac(source)["tac_text"]
    function = text[text.index("FUNC_BEGIN fn::fact"):text.index("FUNC_END fn::fact")]
    assert "CALL t1, fn::fact, argc=1" in function


# ---------- clases y objetos (2 pts) ----------

def test_clases_y_objetos(compile_tac):
    source = """
    class Punto {
      let x: integer;
      function constructor(x: integer) { this.x = x; }
      function get(): integer { return this.x; }
    }
    let p: Punto = new Punto(4);
    p.x = 5;
    print(p.get());
    """
    lines = _tac(compile_tac(source))
    assert lines[:5] == [
        "t0 = NEW_OBJ Punto, fields=1", "ARG t0", "ARG 4", "CALL fn::Punto.constructor, argc=2", "MOV p@global[0], t0",
    ]
    assert "SET_FIELD p@global[0], x@field[0], 5" in lines
    assert "CALL_METHOD t1, p@global[0], get[0], argc=0" in lines
    assert "SET_FIELD this@frame[0], x@field[0], x@frame[1]" in lines


# ---------- herencia (2 pts) ----------

def test_herencia_campos_heredados_y_slot_de_override(compile_tac):
    source = """
    class A { let a: integer = 1; function m(): integer { return 1; } function n(): integer { return 2; } }
    class B : A { let b: integer = 2; function n(): integer { return 3; } function o(): integer { return 4; } }
    let x: A = new B();
    print(x.n());
    """
    lines = _tac(compile_tac(source))
    assert lines[:3] == ["t0 = NEW_OBJ B, fields=2", "SET_FIELD t0, a@field[0], 1", "SET_FIELD t0, b@field[1], 2"]
    assert "CALL_METHOD t1, x@global[0], n[1], argc=0" in lines  # override conserva el slot 1 de A.n
    assert "FUNC_BEGIN fn::B.n, frame=1" in lines


# ---------- try/catch (2 pts) ----------

def test_try_catch(compile_tac):
    lines = _tac(compile_tac("let xs: integer[] = [1]; try { print(xs[4]); } catch (e) { print(e); }"))
    assert lines[3:] == [
        "TRY_BEGIN L_try_handler_0", "t1 = ARR_GET xs@global[0], 4", "PRINT t1", "TRY_END", "GOTO L_try_end_1",
        "LABEL L_try_handler_0", "CATCH e@global[1]", "PRINT e@global[1]", "LABEL L_try_end_1",
    ]


# ---------- reciclaje de temporales (3 pts) ----------

def test_reciclaje_de_temporales(compile_tac):
    body = compile_tac("""
    let a: integer = 1;
    let x: integer = (a + 1) * (a + 2) * (a + 3) * (a + 4) * (a + 5) * (a + 6);
    function f(n: integer): integer { return (n + 1) * (n + 2) * (n + 3); }
    """)
    lines = _tac(body)
    temps = {match for line in lines for match in re.findall(r"\bt\d+\b", line)}
    assert len(temps) <= 3  # 11 operaciones con a lo sumo 3 nombres de temporal
    # pico por funcion (el resultado se pide antes de liberar operandos) y cada unidad arranca en t0
    assert "FUNC_END fn::f, temps=3" in lines
    assert "t0 = BIN +, n@frame[0], 1" in lines


# ---------- nuevas funcionalidades de la tabla de simbolos (2 pts) ----------

def test_tabla_de_simbolos_con_slots_etiquetas_frames_y_layouts(compile_tac):
    body = compile_tac("""
    class A { let v: integer = 1; function m(k: integer): integer { return k; } }
    function g(p: integer): integer { let q: integer = p; return q; }
    let a: A = new A();
    """)
    by_name = {s["name"]: s for s in body["symbols"]["symbols"]}
    assert by_name["a"]["runtime"] == "global[0]"
    assert by_name["g"]["runtime"] == "fn::g frame=2"
    assert by_name["A"]["runtime"] == "fields=1 metodos=1"
    assert by_name["A"]["methods"][0]["runtime"] == "fn::A.m frame=2 slot=0"
    assert by_name["A"]["fields"][0]["runtime"] == "field[0]"


# ---------- recuperacion de errores y bloqueo del ir ----------

def test_varios_errores_lexicos_y_sintacticos_en_una_corrida_sin_tac(compile_tac):
    body = compile_tac("@ let x: integer = 1;\n# let y: integer = ;\nlet z: string = ;")
    codes = [d["code"] for d in body["diagnostics"]]
    assert codes.count("CPS-000") >= 2
    assert codes.count("CPS-001") >= 1
    assert body["tac_text"] is None and body["success"] is False


def test_varios_errores_semanticos_en_una_corrida_sin_duplicados_ni_tac(compile_tac):
    source = """
    let a: integer = "x";
    let b: integer[] = [1];
    print(b["0"]);
    class C {}
    let c: C = new C();
    print(c.nada);
    foreach (v in 3) { print(v); }
    print(noDeclarado);
    """
    body = compile_tac(source)
    keys = [(d["code"], d["line"], d["column"]) for d in body["diagnostics"]]
    assert len(keys) == len(set(keys))  # sin duplicados
    assert {"CPS-100", "CPS-205", "CPS-200", "CPS-120", "CPS-103"} <= {k[0] for k in keys}
    assert body["tac_text"] is None and body["success"] is False


def test_un_programa_valido_nunca_reporta_diagnosticos_de_error(compile_tac):
    body = compile_tac("let x: integer = 1; print(x);")
    assert body["diagnostics"] == [] and body["tac_text"]
