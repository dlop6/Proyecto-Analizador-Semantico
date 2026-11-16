"""
FUNC_BEGIN, FUNC_END, ARG, CALL y RETURN en mars: parametros, retorno, recursion, funciones
anidadas con static link, propagacion de errores entre llamadas y pila restaurada.
"""
import pytest

from compiler.backend.mips.frame_planner import ENTRY_LABEL

from .support import INITIAL_SP, backend_for, output, run


@pytest.mark.parametrize("params, args, expected", [
    ("", "", "7"),
    ("a: integer", "5", "15"),
    ("a: integer, b: integer, c: integer, d: integer", "1, 2, 3, 4", "1234"),
    ("a: integer, b: integer, c: integer, d: integer, e: integer", "1, 2, 3, 4, 5", "12345"),
])
def test_aridades_y_orden_de_los_argumentos(params, args, expected):
    names = [p.split(":")[0].strip() for p in params.split(",") if p]
    body = " * 10 + ".join(names) if len(names) > 1 else (f"{names[0]} + 10" if names else "7")
    if len(names) > 1:
        # a*10^(n-1) + ... + z: el orden de los argumentos se ve en el resultado
        body = names[0]
        for name in names[1:]:
            body = f"({body}) * 10 + {name}"
    assert output(f"function f({params}): integer {{ return {body}; }} print(f({args}));") == [expected]


def test_funcion_void_retorno_sin_valor_y_llamada_como_sentencia():
    assert output("""
    let contador: integer = 0;
    function tick() { contador = contador + 1; }
    function salir(n: integer) { if (n > 0) { return; } print("no positivo"); }
    tick(); tick(); tick();
    salir(1); salir(-1);
    print(contador);
    """) == ["no positivo", "3"]


def test_parametros_de_tipos_distintos():
    assert output("""
    function describir(nombre: string, edad: integer, activo: boolean): string {
        return nombre + " (" + edad + ") " + activo;
    }
    print(describir("ana", 21, true));
    """) == ["ana (21) true"]


def test_argumentos_con_llamadas_anidadas():
    assert output("""
    function f(p: integer, q: integer): integer { return p * 10 + q; }
    function g(x: integer): integer { return x + 1; }
    print(f(1, g(2)));
    print(f(g(1), g(g(2))));
    print(f(f(1, 2), f(3, 4)));
    """) == ["13", "24", "154"]


def test_factorial_y_fibonacci_recursivos():
    assert output("""
    function factorial(n: integer): integer { if (n <= 1) { return 1; } return n * factorial(n - 1); }
    function fib(n: integer): integer { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); }
    print(factorial(1)); print(factorial(5)); print(factorial(12));
    print(fib(0)); print(fib(1)); print(fib(15));
    """) == ["1", "120", "479001600", "0", "1", "610"]


def test_recursion_mutua():
    assert output("""
    function esPar(n: integer): boolean { if (n == 0) { return true; } return esImpar(n - 1); }
    function esImpar(n: integer): boolean { if (n == 0) { return false; } return esPar(n - 1); }
    print(esPar(10)); print(esImpar(7)); print(esPar(7));
    """) == ["true", "true", "false"]


def test_recursion_profunda_no_corrompe_la_pila():
    assert output("""
    function suma(n: integer): integer { if (n == 0) { return 0; } return n + suma(n - 1); }
    print(suma(2000));
    """) == ["2001000"]


def test_ackermann_recursion_anidada_en_los_argumentos():
    assert output("""
    function ack(m: integer, n: integer): integer {
        if (m == 0) { return n + 1; }
        if (n == 0) { return ack(m - 1, 1); }
        return ack(m - 1, ack(m, n - 1));
    }
    print(ack(2, 3));
    """) == ["9"]


def test_anidadas_leen_y_escriben_variables_de_frames_que_las_encierran():
    assert output("""
    function externa(base: integer): integer {
        let acumulado: integer = 0;
        function sumar(n: integer): integer {
            acumulado = acumulado + n;
            function escalar(): integer { return acumulado * base; }
            return escalar();
        }
        function doble(n: integer): integer { return n * 2; }
        sumar(1);
        return sumar(doble(base));
    }
    print(externa(3));
    """) == ["21"]


def test_recursion_de_una_anidada_con_captura():
    assert output("""
    function potencia(base: integer, exp: integer): integer {
        function paso(k: integer): integer { if (k == 0) { return 1; } return base * paso(k - 1); }
        return paso(exp);
    }
    print(potencia(2, 10)); print(potencia(3, 4));
    """) == ["1024", "81"]


def test_static_link_de_profundidad_tres():
    assert output("""
    function a(x: integer): integer {
        function b(y: integer): integer {
            function c(z: integer): integer {
                function d(w: integer): integer { return x * 1000 + y * 100 + z * 10 + w; }
                return d(4);
            }
            return c(3);
        }
        return b(2);
    }
    print(a(1));
    """) == ["1234"]


def test_error_se_propaga_por_dos_funciones_y_corta_la_ejecucion():
    assert output("""
    function dividir(a: integer, b: integer): integer { return a / b; }
    function medio(a: integer, b: integer): integer {
        let r: integer = dividir(a, b);
        print("no se imprime si falla");
        return r;
    }
    print(medio(10, 2));
    print(medio(1, 0));
    print("tampoco");
    """) == ["no se imprime si falla", "5", "Error no capturado: division entre cero"]


def test_valores_vivos_se_conservan_a_traves_de_llamadas():
    assert output("""
    function id(v: integer): integer { return v; }
    let a: integer = 3;
    print(a * 100 + id(20) + id(a) * id(1) + (a + id(4)) * 1000);
    """) == ["7323"]


def test_sp_y_fp_quedan_como_los_dejo_el_prologo_de_main():
    source = """
    function f(p: integer, q: integer): integer { return p + q; }
    function g(x: integer): integer { if (x == 0) { return 0; } return f(x, g(x - 1)); }
    print(g(30));
    """
    result = run(source, registers=("$sp", "$fp", "$ra"))
    assert result.ok, result.raw
    assert result.stdout.splitlines() == ["465"]
    main = backend_for(source).plans[ENTRY_LABEL]
    assert result.registers["$fp"] == INITIAL_SP
    assert result.registers["$sp"] == INITIAL_SP - main.size
