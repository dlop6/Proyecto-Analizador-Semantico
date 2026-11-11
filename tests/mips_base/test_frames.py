import pytest

from compiler.backend.mips.frame_planner import FramePlanner, max_pending_args
from compiler.ir.model import TACInstruction
from compiler.ir.opcodes import Opcode
from compiler.runtime.storage import StorageKind

from .pipeline import function_named, ir_for

SOURCE = """
function suma(a: integer, b: integer): integer {
    let c: integer = a + b;
    let d: integer = c * 2;
    return d;
}
function outer(x: integer): integer {
    function inner(): integer { return x + 1; }
    return inner();
}
function f(a: integer, b: integer): integer { return a + b; }
function g(a: integer): integer { return a; }
class Punto {
    let x: integer;
    function constructor(x: integer) { this.x = x; }
    function mover(dx: integer): integer { return this.x + dx; }
}
let r: integer = f(1, g(2));
let p: Punto = new Punto(3);
print(p.mover(4));
"""


@pytest.fixture(scope="module")
def compiled():
    return ir_for(SOURCE)


def plan(compiled, label):
    program, layout = compiled
    return FramePlanner.plan(function_named(program, label), layout)


def test_funcion_simple_parametros_locales_y_temporales(compiled):
    p = plan(compiled, "fn::suma")
    assert p.static_link is None and p.receiver is None
    assert p.param_offsets == {0: 8, 1: 12}          # args desde 8($fp), en orden
    assert p.local_offsets == {2: -4, 3: -8}         # locales bajo $fp
    assert p.incoming_bytes == 8
    # homes de temporales despues de los locales, sin pisarse con nada
    assert all(off <= -12 for off in p.temp_offsets.values())


def test_todos_los_offsets_son_distintos_y_alineados(compiled):
    program, layout = compiled
    for fn in program.functions:
        p = FramePlanner.plan(fn, layout)
        below = [*p.local_offsets.values(), *p.temp_offsets.values(), *p.arg_stash]
        assert len(below) == len(set(below)), fn.label
        assert all(o < 0 and o % 4 == 0 for o in below)
        assert p.size == 4 * len(below)
        above = [o for o in (p.static_link, p.receiver, *p.param_offsets.values()) if o is not None]
        assert len(above) == len(set(above)) and all(o >= 8 and o % 4 == 0 for o in above)


def test_metodo_tiene_this_en_8_y_params_despues(compiled):
    p = plan(compiled, "fn::Punto.mover")
    assert p.receiver == 8
    assert p.param_offsets == {1: 12}
    assert p.static_link is None
    assert p.offset_of(StorageKind.THIS, 0) == 8


def test_constructor_tambien_recibe_this(compiled):
    p = plan(compiled, "fn::Punto.constructor")
    assert p.receiver == 8 and p.param_offsets == {1: 12}


def test_funcion_anidada_con_static_link_lo_recibe_primero(compiled):
    program, layout = compiled
    inner = layout.records["fn::outer.inner"]
    assert inner.static_link
    p = plan(compiled, "fn::outer.inner")
    assert p.static_link == 8 and p.incoming_bytes == 4
    # outer no necesita link: x es suyo
    assert plan(compiled, "fn::outer").static_link is None


def test_args_pendientes_con_llamada_anidada(compiled):
    program, _ = compiled
    # f(1, g(2)) -> ARG 1; ARG 2; CALL g; ARG t; CALL f: hay hasta 2 pendientes a la vez
    assert max_pending_args(program.entry.instructions) >= 2
    p = FramePlanner.plan_entry(program.entry)
    assert len(p.arg_stash) == max_pending_args(program.entry.instructions)


def test_entry_no_tiene_entrantes_ni_locales(compiled):
    program, _ = compiled
    p = FramePlanner.plan_entry(program.entry)
    assert p.label == "main" and p.incoming_bytes == 0 and not p.local_offsets
    assert p.static_link is None and p.receiver is None


def test_plan_es_determinista_y_no_depende_de_otras_funciones(compiled):
    program, layout = compiled
    first = [FramePlanner.plan(fn, layout) for fn in program.functions]
    second = [FramePlanner.plan(fn, layout) for fn in reversed(program.functions)][::-1]
    assert first == second


def test_offset_of_con_kind_o_slot_invalido_falla(compiled):
    p = plan(compiled, "fn::suma")
    with pytest.raises(ValueError):
        p.offset_of(StorageKind.THIS, 0)
    with pytest.raises(ValueError):
        p.offset_of(StorageKind.PARAM, 9)
    with pytest.raises(ValueError):
        p.offset_of(StorageKind.GLOBAL, 0)
    with pytest.raises(ValueError):
        p.temp_offset(999)


def _call(op, argc):
    return TACInstruction(op, metadata=(("argc", argc),))


def test_max_pending_args_valida_el_flujo_de_arg_y_call():
    arg = TACInstruction(Opcode.ARG)
    assert max_pending_args((arg, arg, _call(Opcode.CALL, 2))) == 2
    assert max_pending_args((arg, _call(Opcode.CALL_METHOD, 1), arg, arg, _call(Opcode.CALL, 2))) == 2
    with pytest.raises(ValueError):
        max_pending_args((_call(Opcode.CALL, 1),))      # consume mas de lo que hay
    with pytest.raises(ValueError):
        max_pending_args((arg,))                         # ARG sin CALL
