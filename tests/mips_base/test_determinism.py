"""mismo programa -> mismo ensamblador, byte a byte, sin importar cuantas veces se compile."""
from compiler.backend.mips.frame_planner import plan_program

from .mini_lowerer import lower
from .pipeline import ir_for

SOURCE = """
let g: integer = 3;
function fib(n: integer): integer { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); }
function a(x: integer): integer {
    function b(y: integer): integer { return x + y + g; }
    return b(2);
}
print(fib(6));
print(a(1));
"""


def test_el_ensamblador_es_identico_en_dos_compilaciones():
    first = lower(*ir_for(SOURCE))
    second = lower(*ir_for(SOURCE))
    assert first == second


def test_los_planes_de_frame_son_identicos_en_dos_compilaciones():
    assert plan_program(*ir_for(SOURCE)) == plan_program(*ir_for(SOURCE))
