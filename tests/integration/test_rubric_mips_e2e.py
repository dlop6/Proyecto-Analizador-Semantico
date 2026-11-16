"""
pruebas de punta a punta por cada fila de la rubrica del proyecto 03 (generacion de
ensamblador, 30 pts). cada caso entra por la misma puerta que la gui (POST /api/compile del
ide flask), toma el .asm que se mostraria en la pagina y lo ejecuta en MARS 4.5: se
verifica el comportamiento observable, no solo que el texto "se vea bien". nada mockeado.
"""
from pathlib import Path

import pytest

from ide.app import app

from tests.mips_base.mars_runner import run_mars

ROOT = Path(__file__).resolve().parents[2]
MAX_STEPS = 3_000_000


@pytest.fixture
def gui():
    app.config.update(TESTING=True)
    client = app.test_client()

    def _compile(source: str) -> dict:
        response = client.post("/api/compile", json={"source": source})
        assert response.status_code == 200
        body = response.get_json()
        assert body["success"] is True, body["diagnostics"]
        assert body["tac_text"] and body["asm_text"]
        return body

    return _compile


def _run(body: dict) -> list[str]:
    result = run_mars(body["asm_text"], max_steps=MAX_STEPS)
    assert result.ok, result.raw
    return result.stdout.splitlines()


# ---------- seleccion de registros (4 pts) ----------

def test_seleccion_de_registros_con_mas_de_ocho_temporales_vivos(gui):
    # suma asociada a la derecha: los 10 productos quedan vivos a la vez y $t0-$t7 no
    # alcanzan, asi que hay spill a su home y recarga
    expression = "(a * 10)"
    for i in range(9, 0, -1):
        expression = f"(a * {i}) + ({expression})"
    body = gui(f"let a: integer = 3;\nprint({expression});\n")
    asm = body["asm_text"]
    assert "# guarda t" in asm and "# recarga t" in asm
    assert "$s0" not in asm   # el generador solo reparte $t0-$t7
    assert _run(body) == [str(3 * sum(range(1, 11)))]


# ---------- registros y arboles de activacion (5 pts) ----------

def test_registros_de_activacion_recursion_y_funciones_anidadas(gui):
    body = gui("""
    function externa(n: integer): integer {
        let base: integer = 100;
        function interna(k: integer): integer {
            if (k == 0) { return base; }
            return interna(k - 1) + 1;
        }
        return interna(n);
    }
    print(externa(3));
    print(externa(0));
    """)
    asm = body["asm_text"]
    assert "sw $ra, 4($sp)" in asm and "sw $fp, 0($sp)" in asm   # prologo: ra y fp viejo
    assert "# static link" in asm                                # captura no local por static link
    assert _run(body) == ["103", "100"]


# ---------- variables y constantes (1 pt) ----------

def test_variables_y_constantes(gui):
    body = gui("""
    let a: integer = 5;
    const SALUDO: string = "hola";
    var activo: boolean = true;
    a = a + 2;
    print(a);
    print(SALUDO);
    print(activo);
    """)
    assert _run(body) == ["7", "hola", "true"]


# ---------- expresiones aritmeticas (1 pt) ----------

def test_expresiones_aritmeticas(gui):
    body = gui("""
    let a: integer = 17;
    let b: integer = 5;
    print(a + b * 2);
    print((a - b) / 4);
    print(a % b);
    print(-a);
    print("total: " + (a + b));
    """)
    assert _run(body) == ["27", "3", "2", "-17", "total: 22"]


# ---------- expresiones logicas (1 pt) ----------

def test_expresiones_logicas_con_cortocircuito(gui):
    body = gui("""
    let v: integer[] = [1];
    let x: integer = 3;
    print(x > 2 && x < 5);
    print(x == 4 || !(x != 3));
    print(false && v[9] == 1);
    print(true || v[9] == 1);
    """)
    # si && / || no cortocircuitaran, v[9] seria un error de runtime
    assert _run(body) == ["true", "true", "false", "true"]


# ---------- arreglos (1 pt) ----------

def test_arreglos(gui):
    body = gui("""
    let v: integer[] = [4, 8, 15];
    v[0] = v[1] + v[2];
    let m: integer[][] = [[1, 2], [3, 4]];
    m[1][0] = 30;
    print(v[0]);
    print(m[1][0] + m[0][1]);
    try { print(v[3]); } catch (e) { print(e); }
    """)
    asm = body["asm_text"]
    assert "jal rt_alloc" in asm and "jal rt_check_bounds" in asm
    assert _run(body) == ["23", "32", "indice fuera de rango"]


# ---------- sentencias de control (3 pts) ----------

def test_sentencias_de_control(gui):
    body = gui("""
    let x: integer = 7;
    if (x > 5) { print("mayor"); } else { print("menor"); }
    let i: integer = 0;
    while (i < 3) { i = i + 1; }
    print(i);
    do { i = i - 1; } while (i > 0);
    print(i);
    let s: integer = 0;
    for (let j: integer = 0; j < 10; j = j + 1) {
        if (j == 2) { continue; }
        if (j == 5) { break; }
        s = s + j;
    }
    print(s);
    foreach (n in [10, 20, 30]) { s = s + n; }
    print(s);
    switch (x) {
        case 1: print("uno");
        case 7: print("siete");
        default: print("otro");
    }
    """)
    assert _run(body) == ["mayor", "3", "0", "8", "68", "siete"]


# ---------- funciones y parametros (2 pts) ----------

def test_funciones_y_parametros(gui):
    body = gui("""
    function concatenar(a: string, b: string, n: integer, ok: boolean, extra: integer): string {
        if (ok) { return a + b + (n + extra); }
        return "no";
    }
    function saludar() { print("hola"); }
    saludar();
    print(concatenar("x", "y", 1, true, 2));
    print(concatenar("x", "y", 1, false, 2));
    """)
    assert _run(body) == ["hola", "xy3", "no"]


# ---------- recursividad (2 pts) ----------

def test_recursividad_factorial_y_fibonacci(gui):
    body = gui("""
    function factorial(n: integer): integer { if (n <= 1) { return 1; } return n * factorial(n - 1); }
    function fib(n: integer): integer { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); }
    print(factorial(10));
    print(fib(15));
    """)
    assert _run(body) == ["3628800", "610"]


# ---------- clases y objetos (2 pts) ----------

def test_clases_y_objetos(gui):
    body = gui("""
    class Punto {
        let x: integer = 0;
        let y: integer = 0;
        function constructor(x: integer, y: integer) { this.x = x; this.y = y; }
        function mover(dx: integer) { this.x = this.x + dx; }
        function texto(): string { return "(" + this.x + ", " + this.y + ")"; }
    }
    let p: Punto = new Punto(1, 2);
    p.mover(5);
    p.y = 9;
    print(p.texto());
    """)
    asm = body["asm_text"]
    assert "vt_Punto: .word" in asm and "jalr $t9" in asm
    assert _run(body) == ["(6, 9)"]


# ---------- herencia (2 pts) ----------

def test_herencia_vtable_override_y_campos_heredados(gui):
    body = gui("""
    class Empleado {
        let nombre: string;
        let base: integer = 1000;
        function constructor(nombre: string) { this.nombre = nombre; }
        function sueldo(): integer { return this.base; }
        function ficha(): string { return this.nombre + ": " + this.sueldo(); }
    }
    class Gerente : Empleado {
        let bono: integer = 500;
        function sueldo(): integer { return this.base + this.bono; }
    }
    let lista: Empleado[] = [new Empleado("ana"), new Gerente("luis")];
    foreach (e in lista) { print(e.ficha()); }
    """)
    asm = body["asm_text"]
    assert "vt_Gerente: .word fn_Gerente_dsueldo, fn_Empleado_dficha" in asm   # override reusa el slot
    assert _run(body) == ["ana: 1000", "luis: 1500"]


# ---------- try / catch (2 pts) ----------

def test_try_catch_local_anidado_y_entre_llamadas(gui):
    body = gui("""
    let v: integer[] = [1, 2];
    function leer(i: integer): integer { return v[i]; }
    function dividir(a: integer, b: integer): integer { return a / b; }
    try { print(leer(1)); print(leer(5)); } catch (e) { print("1: " + e); }
    try {
        try { print(dividir(4, 0)); } catch (e) { print("2: " + e); print(v[-3]); }
    } catch (e) { print("3: " + e); }
    print("fin");
    """)
    assert _run(body) == ["2", "1: indice fuera de rango", "2: division entre cero", "3: indice fuera de rango", "fin"]


# ---------- optimizacion por mirilla (3 pts) ----------

def test_optimizacion_por_mirilla_sobre_el_programa_compilado(gui):
    body = gui("""
    let x: integer = 4;
    let y: integer = x + 0;
    switch (y) { case 4: print("cuatro"); default: print("otro"); }
    """)
    report = body["peephole"]
    assert report["applied"]["R3"] >= 1 and report["applied"]["R6"] >= 1
    assert report["after"] < report["before"]
    assert _run(body) == ["cuatro"]


# ---------- ensamblador / simulador compatible (1 pt) ----------

def test_el_asm_de_la_gui_ensambla_y_corre_en_mars_4_5(gui):
    fetch = (ROOT / "tools" / "fetch_mars.sh").read_text(encoding="utf-8")
    assert "Mars4_5.jar" in fetch and "EXPECTED_SHA256" in fetch    # version fija y verificada
    body = gui('print("hola MARS");')
    result = run_mars(body["asm_text"])
    assert not result.assembly_error and not result.runtime_error, result.raw
    assert result.stdout.splitlines() == ["hola MARS"]
