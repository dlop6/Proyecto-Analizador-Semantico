"""registros de activacion y llamadas: IR real -> mips con las piezas de la base -> mars."""
import pytest

from compiler.backend.mips.frame_planner import ENTRY_LABEL, plan_program

from .mars_runner import run_mars
from .mini_lowerer import lower
from .pipeline import ir_for

INITIAL_SP = 0x7FFFEFFC


def run(source, trace=False, registers=()):
    program, layout = ir_for(source)
    asm = lower(program, layout, trace=trace)
    return run_mars(asm, registers=registers, max_steps=500_000), program, layout


def printed(source):
    result, *_ = run(source)
    assert result.ok, result.raw
    return result.stdout.split()


def test_factorial_recursivo():
    out = printed("""
    function fact(n: integer): integer { if (n <= 1) { return 1; } return n * fact(n - 1); }
    print(fact(5)); print(fact(10));
    """)
    assert out == ["120", "3628800"]


def test_fibonacci_conserva_un_temporal_a_traves_de_una_llamada():
    # fib(n-1) + fib(n-2): el resultado de la primera llamada vive en un temporal mientras corre la segunda
    out = printed("""
    function fib(n: integer): integer { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); }
    print(fib(10));
    """)
    assert out == ["55"]


@pytest.mark.parametrize("arity, expected", [(0, "7"), (1, "11"), (4, "10"), (5, "15")])
def test_aridades(arity, expected):
    source = {
        0: "function f(): integer { return 7; } print(f());",
        1: "function f(a: integer): integer { return a + 10; } print(f(1));",
        4: "function f(a: integer, b: integer, c: integer, d: integer): integer { return a + b + c + d; } print(f(1, 2, 3, 4));",
        5: ("function f(a: integer, b: integer, c: integer, d: integer, e: integer): integer "
            "{ return a + b + c + d + e; } print(f(1, 2, 3, 4, 5));"),
    }[arity]
    assert printed(source) == [expected]


def test_argumentos_con_llamadas_anidadas_y_temporales_reusados():
    out = printed("""
    function f(p: integer, q: integer): integer { return p * 10 + q; }
    function g(x: integer): integer { return x + 1; }
    print(f(1, g(2)));
    print(f(g(1), g(g(2))));
    print(f(f(1, 2), f(3, 4)));
    """)
    assert out == ["13", "24", "154"]


def test_anidadas_con_static_link_de_profundidad_dos():
    out = printed("""
    function a(x: integer): integer {
        function b(y: integer): integer {
            function c(z: integer): integer { return x * 100 + y * 10 + z; }
            return c(3);
        }
        return b(2);
    }
    print(a(1));
    """)
    assert out == ["123"]


def test_escritura_a_una_variable_de_un_frame_que_encierra():
    out = printed("""
    function a(): integer {
        let x: integer = 1;
        function b(): integer { x = x + 41; return x; }
        b();
        return x;
    }
    print(a());
    """)
    assert out == ["42"]


def test_recursion_de_una_anidada_con_static_link():
    out = printed("""
    function outer(n: integer): integer {
        function count(k: integer): integer { if (k <= 0) { return n; } return count(k - 1) + 1; }
        return count(3);
    }
    print(outer(10));
    """)
    assert out == ["13"]


def test_locales_arrancan_en_cero():
    out = printed("function f(): integer { let x: integer; let y: integer; return x + y; } print(f());")
    assert out == ["0"]


def test_variables_globales():
    out = printed("let g: integer = 5; function f(): integer { g = g + 1; return g; } print(f()); print(g);")
    assert out == ["6", "6"]


def test_sp_y_fp_quedan_balanceados_despues_de_llamadas_anidadas():
    source = """
    function f(p: integer, q: integer): integer { return p + q; }
    function g(x: integer): integer { return f(x, f(x, x)); }
    print(g(2));
    """
    result, program, layout = run(source, registers=("$sp", "$fp"))
    assert result.ok and result.stdout.split() == ["6"]
    main = plan_program(program, layout)[ENTRY_LABEL]
    assert result.registers["$fp"] == INITIAL_SP               # main nunca perdio su fp
    assert result.registers["$sp"] == INITIAL_SP - main.size   # y la pila quedo como la dejo su prologo


def test_arbol_de_activacion_desde_una_ejecucion_real():
    result, *_ = run(
        "function fib(n: integer): integer { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); } print(fib(3));",
        trace=True,
    )
    assert result.ok, result.raw
    events = [line for line in result.stdout.splitlines() if line.startswith(("enter", "exit"))]
    assert _tree(events) == ("main", [("fn::fib", [("fn::fib", [("fn::fib", []), ("fn::fib", [])]), ("fn::fib", [])])])


def _tree(events):
    root = ("main", [])
    stack = [root]
    for event in events[1:-1]:                      # sin el enter/exit de main
        kind, name = event.split()
        if kind == "enter":
            node = (name, [])
            stack[-1][1].append(node)
            stack.append(node)
        else:
            assert stack[-1][0] == name, f"exit de {name} con {stack[-1][0]} abierto"
            stack.pop()
    assert stack == [root]
    return root
