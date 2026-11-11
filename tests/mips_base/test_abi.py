"""abi y emisor de activacion: contrato de helpers, validaciones, errores y despacho de metodos."""
import pytest

from compiler.backend.mips.abi import (
    ARRAY_FIRST_ELEMENT_OFFSET, FIRST_ARG_OFFSET, OLD_FP_OFFSET, RA_OFFSET, array_size, field_offset,
    incoming_arg_offset, local_area_offset, object_size,
)
from compiler.backend.mips.activation import ActivationEmitter
from compiler.backend.mips.builder import MipsBuilder
from compiler.backend.mips.frame_planner import ENTRY_LABEL, plan_program
from compiler.backend.mips.helpers import HELPERS
from compiler.backend.mips.operands import A0, RA, SP, T, V0, V1, ZERO, Imm, LabelRef, Mem
from compiler.backend.mips.register_allocator import RegisterAllocator
from compiler.ir.model import Const, Temp
from compiler.runtime.storage import StorageKind, StorageRef
from compiler.types import INTEGER

from .mars_runner import run_mars
from .mini_lowerer import uncaught_stub
from .pipeline import function_named, ir_for


def harness(source):
    program, layout = ir_for(source)
    builder = MipsBuilder()
    plans = plan_program(program, layout)
    allocator = RegisterAllocator(builder, plans[ENTRY_LABEL])
    return program, builder, allocator, ActivationEmitter(builder, allocator, layout, plans)


def const(value):
    return Const(value, INTEGER)


# ---------- constantes del abi ----------

def test_offsets_fijados_por_el_pdf():
    assert (OLD_FP_OFFSET, RA_OFFSET, FIRST_ARG_OFFSET) == (0, 4, 8)
    assert [incoming_arg_offset(i) for i in range(3)] == [8, 12, 16]
    assert [local_area_offset(i) for i in range(3)] == [-4, -8, -12]


def test_layout_de_datos():
    assert field_offset(0) == 4 and field_offset(2) == 12
    assert object_size(3) == 16 and array_size(5) == 24 and ARRAY_FIRST_ELEMENT_OFFSET == 4


@pytest.mark.parametrize("call", [incoming_arg_offset, local_area_offset, field_offset])
def test_indices_negativos_fallan(call):
    with pytest.raises(ValueError):
        call(-1)


# ---------- contrato de helpers ----------

def test_tabla_de_helpers_es_consistente():
    assert all(name == contract.name and contract.params >= 0 for name, contract in HELPERS.items())
    assert {"rt_alloc", "rt_check_null", "rt_check_bounds", "rt_concat", "rt_string_equals",
            "rt_uncaught_error"} <= set(HELPERS)
    assert HELPERS["rt_alloc"].returns and not HELPERS["rt_alloc"].can_fail
    assert HELPERS["rt_check_bounds"].can_fail and HELPERS["rt_check_bounds"].params == 2


def test_helper_mal_llamado_falla():
    _, _, _, em = harness("print(1);")
    em.begin_entry()
    with pytest.raises(ValueError, match="desconocido"):
        em.emit_helper_call("rt_nada")
    with pytest.raises(ValueError, match="argumentos"):
        em.emit_helper_call("rt_concat", (const(1),))
    with pytest.raises(ValueError, match="on_error"):
        em.emit_helper_call("rt_check_divisor", (const(1),))
    with pytest.raises(ValueError, match="no devuelve"):
        em.emit_helper_call("rt_print_boolean", (const(1),), Temp(0, INTEGER))


# ---------- ciclo de vida del emisor ----------

def test_no_se_puede_emitir_sin_funcion_abierta_ni_abrir_dos():
    _, _, _, em = harness("print(1);")
    with pytest.raises(RuntimeError):
        em.emit_return(None)
    em.begin_entry()
    with pytest.raises(RuntimeError, match="sigue abierta"):
        em.begin_entry()


def test_arg_sin_consumir_al_cerrar_falla():
    _, _, alloc, em = harness("function f(a: integer): integer { return a; } print(f(1));")
    em.begin_entry()
    with alloc.instruction():
        em.emit_arg(const(1))
    with pytest.raises(ValueError, match="sin consumir"):
        em.end_entry()


def test_call_que_consume_mas_de_lo_pendiente_falla():
    _, _, _, em = harness("function f(a: integer): integer { return a; } print(f(1));")
    em.begin_entry()
    with pytest.raises(ValueError, match="pendientes"):
        em.emit_call("fn::f", 1, None, None, on_error=em.error_target())


def test_accesos_imposibles_fallan():
    _, _, _, em = harness("function f(a: integer): integer { return a; } print(f(1));")
    em.begin_entry()
    nonlocal_ref = StorageRef(StorageKind.NONLOCAL, 0, lexical_depth=1, name="x")
    with pytest.raises(ValueError, match="static link"):
        em.load_value(nonlocal_ref, T[8])
    with pytest.raises(ValueError, match="campo"):
        em.load_value(StorageRef(StorageKind.FIELD, 0, name="f"), T[8])
    with pytest.raises(ValueError):
        em.load_value(object(), T[8])
    with pytest.raises(ValueError, match="mismo registro"):
        em.store_storage(T[9], nonlocal_ref, via=T[9])


# ---------- prologo y epilogo ----------

def test_prologo_y_epilogo_siguen_la_secuencia_del_pdf():
    program, builder, _, em = harness(
        "function f(a: integer): integer { let b: integer = a; return b; } print(f(1));"
    )
    em.begin_entry()
    em.end_entry()
    em.begin_function(function_named(program, "fn::f"))
    em.end_function()
    text = builder.build().render()
    assert "fn_f:\n    addi $sp, $sp, -8\n    sw $ra, 4($sp)\n    sw $fp, 0($sp)\n    move $fp, $sp" in text
    assert ("fn_f_exit:\n    lw $ra, 4($fp)\n    move $sp, $fp\n    lw $fp, 0($sp)\n"
            "    addi $sp, $sp, 8\n    jr $ra") in text
    assert "sw $zero, -4($fp)" in text          # la local arranca en cero


# ---------- errores entre frames (mars) ----------

def _failing_helper(builder):
    # cuerpo de juguete de rt_check_divisor: falla si el argumento es cero
    builder.mark("rt_check_divisor")
    builder.emit("lw", T[0], Mem(0, SP))
    builder.emit("beq", T[0], ZERO, LabelRef("div_fail"))
    builder.emit("li", V0, Imm(0))
    builder.emit("li", V1, Imm(0))
    builder.emit("jr", RA)
    builder.mark("div_fail")
    builder.emit("la", V0, LabelRef(builder.add_string("division por cero")))
    builder.emit("li", V1, Imm(1))
    builder.emit("jr", RA)


def _error_program(divisor):
    program, builder, _, em = harness(
        "function g(): integer { return 1; } function f(): integer { return g(); } print(f());"
    )
    em.begin_entry()
    em.emit_call("fn::f", 0, None, None, on_error=em.error_target())
    builder.emit("la", A0, LabelRef(builder.add_string("main siguio\n")))
    builder.emit("li", V0, Imm(4))
    builder.emit("syscall")
    em.end_entry()
    em.begin_function(function_named(program, "fn::f"))
    em.emit_call("fn::g", 0, None, None, on_error=em.error_target())
    em.emit_return(const(1))
    em.end_function()
    em.begin_function(function_named(program, "fn::g"))
    em.emit_helper_call("rt_check_divisor", (const(divisor),), on_error=em.error_target())
    em.emit_return(const(2))
    em.end_function()
    _failing_helper(builder)
    uncaught_stub(builder)
    return run_mars(builder.render())


def test_un_error_se_propaga_por_dos_frames_hasta_el_programa():
    result = _error_program(0)
    assert result.ok, result.raw
    assert result.stdout == "division por cero"       # llego el mensaje de $v0 y main no siguio


def test_sin_error_el_flujo_sigue_normal():
    result = _error_program(5)
    assert result.ok and result.stdout == "main siguio\n"


# ---------- despacho de metodos por vtable (mars) ----------

def test_llamada_a_metodo_por_tabla_de_despacho():
    program, builder, alloc, em = harness("""
    class P {
        let x: integer;
        function constructor(x: integer) { this.x = x; }
        function get(d: integer): integer { return this.x + d; }
    }
    let p: P = new P(1);
    print(p.get(1));
    """)
    builder.add_data("obj", "word", ("vt_P", 40))         # objeto estatico: [vtable][x]
    builder.add_data("vt_P", "word", ("fn_P_dget",))       # tabla de despacho: slot 0 = get
    receiver, result = Temp(0, INTEGER, 0), Temp(1, INTEGER, 0)
    em.begin_entry()
    with alloc.instruction():
        reg = alloc.get_reg(receiver, load=False)
        builder.emit("la", reg, LabelRef("obj"))
        alloc.mark_dirty(receiver)
        em.emit_arg(const(2))
    em.emit_method_call(receiver, 0, 1, result, on_error=em.error_target())
    with alloc.instruction():
        em.load_value(result, A0)
    builder.emit("li", V0, Imm(1))
    builder.emit("syscall")
    em.end_entry()
    # cuerpo a mano del metodo: this.x + d
    em.begin_function(function_named(program, "fn::P.get"))
    total = Temp(0, INTEGER, 1)
    with alloc.instruction():
        em.load_value(StorageRef(StorageKind.THIS, 0, name="this"), T[8])
        em.load_field(T[8], T[8], 0)
        em.load_value(StorageRef(StorageKind.PARAM, 1, name="d"), T[9])
        reg = alloc.get_reg(total, load=False)
        builder.emit("add", reg, T[8], T[9])
        alloc.mark_dirty(total)
        em.emit_return(total)
    em.end_function()
    uncaught_stub(builder)
    run = run_mars(builder.render())
    assert run.ok, run.raw
    assert run.stdout == "42"
