"""
MOV, BIN, UN y PRINT ejecutados en mars: se compara lo que imprime el programa, no el texto
del ensamblador.
"""
import pytest

from .support import assemble, output


# ----------------------------------------------------------------------
# variables y constantes
# ----------------------------------------------------------------------

def test_globales_constantes_y_asignacion_encadenada():
    assert output("""
    const LIMITE: integer = 10;
    let a: integer = 3;
    var b: integer = a;
    let c: integer;
    a = b = LIMITE;
    print(a); print(b); print(c);
    """) == ["10", "10", "0"]


def test_locales_parametros_y_variables_sin_inicializar():
    assert output("""
    function f(p: integer): integer {
        let x: integer;
        let y: integer = p * 2;
        x = y + 1;
        return x;
    }
    print(f(20));
    """) == ["41"]


def test_literales_boolean_null_y_string():
    assert output("""
    let t: boolean = true;
    let f: boolean = false;
    let s: string = "texto con espacios";
    print(t); print(f); print(s); print(null);
    """) == ["true", "false", "texto con espacios", "null"]


def test_string_sin_inicializar_se_imprime_como_null():
    assert output("let s: string; print(s);") == ["null"]


# ----------------------------------------------------------------------
# aritmetica
# ----------------------------------------------------------------------

@pytest.mark.parametrize("expr, expected", [
    ("2 + 3 * 4", "14"),
    ("(2 + 3) * 4", "20"),
    ("20 - 3 - 2", "15"),
    ("100 / 7", "14"),
    ("100 % 7", "2"),
    ("-7 / 2", "-3"),          # trunca hacia cero
    ("-7 % 2", "-1"),          # el resto lleva el signo del dividendo
    ("7 % -2", "1"),
    ("-(3 - 10)", "7"),
    ("--5", "5"),
    ("2147483647 + 1", "-2147483648"),   # 32 bits, desborda dando la vuelta (sin trap)
    ("-2147483647 - 2", "2147483647"),
    ("65536 * 65536", "0"),
    ("40000 + 40000", "80000"),          # constante fuera de 16 bits: no puede ir como inmediato
    ("1 - -32768", "32769"),
])
def test_aritmetica(expr, expected):
    assert output(f"let x: integer = {expr}; print(x);") == [expected]


def test_aritmetica_con_variables_y_temporales():
    assert output("""
    let a: integer = 17;
    let b: integer = 5;
    print(a + b); print(a - b); print(a * b); print(a / b); print(a % b);
    print((a + b) * (a - b) / (b % 3));
    """) == ["22", "12", "85", "3", "2", "132"]


def test_division_por_cero_sin_capturar_termina_con_mensaje():
    result = output("""
    let cero: integer = 0;
    print("antes");
    print(10 / cero);
    print("despues");
    """)
    assert result == ["antes", "Error no capturado: division entre cero"]


def test_modulo_por_cero_tambien_es_error():
    assert output("let z: integer = 0; print(5 % z);") == ["Error no capturado: division entre cero"]


# ----------------------------------------------------------------------
# comparaciones y logica
# ----------------------------------------------------------------------

@pytest.mark.parametrize("op, expected", [
    ("==", ["false", "true", "false"]),
    ("!=", ["true", "false", "true"]),
    ("<", ["true", "false", "false"]),
    ("<=", ["true", "true", "false"]),
    (">", ["false", "false", "true"]),
    (">=", ["false", "true", "true"]),
])
def test_comparaciones(op, expected):
    assert output(f"""
    let a: integer = 5;
    print(a {op} 6); print(a {op} 5); print(a {op} -4);
    """) == expected


def test_not_y_comparacion_de_booleanos():
    assert output("""
    let p: boolean = true;
    print(!p); print(!!p); print(p == true); print(p != false); print(!(3 > 2) == false);
    """) == ["false", "true", "true", "true", "true"]


def test_and_or_con_cortocircuito_no_evalua_el_lado_derecho():
    assert output("""
    function marca(v: boolean): boolean { print("evaluado"); return v; }
    print(false && marca(true));
    print(true || marca(false));
    print(true && marca(false));
    print(false || marca(true));
    """) == ["false", "true", "evaluado", "false", "evaluado", "true"]


def test_expresion_logica_mixta():
    assert output("""
    let x: integer = 5;
    let p: boolean = true;
    let q: boolean = false;
    print(x > 0 && x < 10 || !p);
    print((p || q) && (x == 5 || q));
    print(p && q || q && p);
    """) == ["true", "true", "false"]


def test_ternario():
    assert output("""
    let n: integer = 7;
    print(n % 2 == 0 ? "par" : "impar");
    print(n > 5 ? n * 10 : n);
    """) == ["impar", "70"]


# ----------------------------------------------------------------------
# strings
# ----------------------------------------------------------------------

def test_concatenacion_con_integer_y_boolean_en_ambos_lados():
    assert output("""
    let n: integer = -42;
    let ok: boolean = false;
    print("n = " + n);
    print(n + " es n");
    print("ok: " + ok);
    print(true + "!");
    print("a" + "b" + "c" + 1 + 2);
    print("" + 0);
    print("min " + (-2147483647 - 1));
    """) == ["n = -42", "-42 es n", "ok: false", "true!", "abc12", "0", "min -2147483648"]


def test_igualdad_de_strings_compara_contenido():
    assert output("""
    let a: string = "ab";
    let b: string = "a" + "b";
    let c: string = "abc";
    print(a == b); print(a != b); print(a == c); print(a != c); print(b == "ab");
    """) == ["true", "false", "false", "true", "true"]


def test_string_null_en_concatenacion_e_igualdad():
    assert output("""
    let s: string;
    let t: string;
    print("valor: " + s);
    print(s == t);
    print(s == "null");
    """) == ["valor: null", "true", "false"]


# ----------------------------------------------------------------------
# forma del ensamblador
# ----------------------------------------------------------------------

def test_suma_con_constante_chica_usa_inmediato_sin_trap():
    asm = assemble("let x: integer = 1; x = x + 1; x = 5 + x; x = x - 3;")
    assert asm.count("addiu") == 3 and "addu" not in asm and "add " not in asm


def test_resta_y_negacion_no_hacen_trap_por_overflow():
    asm = assemble("let a: integer = 1; let b: integer = 2; print(a - b); print(-a);")
    assert "subu" in asm and "sub " not in asm and "neg " not in asm
