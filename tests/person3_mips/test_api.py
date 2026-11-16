"""
contrato del backend extendido: baja TODOS los opcodes del ir, conserva la api del core y,
igual que el core, rechaza el ir que no puede bajar entero sin emitir nada.
"""
import pytest

from compiler.backend.mips.core_backend import CoreMipsBackend, IRContractError
from compiler.backend.mips.extended_backend import ExtendedMipsBackend
from compiler.backend.mips.model import AssemblyProgram
from compiler.frontend import analyze_source
from compiler.ir.model import ClassRef, Const, IRFragment, IRProgram, Label, TACInstruction, Temp
from compiler.ir.opcodes import Opcode
from compiler.types import INTEGER, ArrayType

from tests.mips_base.pipeline import ir_for

from .support import assemble


class _LayoutVacio:
    globals_count = 0
    functions = ()
    records = {}
    class_layouts = {}


def _entry_only(*instructions, temps=0) -> IRProgram:
    return IRProgram(IRFragment(tuple(instructions), temps, temps), ())


@pytest.mark.parametrize("opcode", sorted(Opcode, key=lambda o: o.value), ids=lambda o: o.value)
def test_hay_handler_para_cada_opcode_del_contrato(opcode):
    assert ExtendedMipsBackend.supports(opcode)


def test_es_un_core_mips_backend_con_la_misma_api():
    assert issubclass(ExtendedMipsBackend, CoreMipsBackend)
    program, layout = ir_for("let v: integer[] = [1]; print(v[0]);")
    assert isinstance(ExtendedMipsBackend.generate(program, layout), AssemblyProgram)


def test_no_acepta_un_ast_ni_texto_tac():
    ast = analyze_source("print(1);").ast
    for not_ir in (ast, "  PRINT 1\n", None):
        with pytest.raises(IRContractError, match="IRProgram"):
            ExtendedMipsBackend(not_ir, _LayoutVacio())


def test_try_sin_cerrar_rechaza_el_programa_entero():
    program = _entry_only(
        TACInstruction(Opcode.TRY_BEGIN, arg1=Label("L_try_handler_0")),
        TACInstruction(Opcode.PRINT, arg1=Const(1, INTEGER)),
        TACInstruction(Opcode.LABEL, arg1=Label("L_try_handler_0")),
    )
    with pytest.raises(IRContractError, match="TRY_BEGIN sin TRY_END"):
        ExtendedMipsBackend.generate(program, _LayoutVacio())


def test_try_end_sin_try_begin_rechaza_el_programa():
    program = _entry_only(TACInstruction(Opcode.TRY_END))
    with pytest.raises(IRContractError, match="TRY_END sin TRY_BEGIN"):
        ExtendedMipsBackend.generate(program, _LayoutVacio())


@pytest.mark.parametrize("length", [Const(-1, INTEGER), Temp(0, INTEGER), Const(10**7, INTEGER)])
def test_new_arr_solo_con_longitud_constante_razonable(length):
    program = _entry_only(TACInstruction(Opcode.NEW_ARR, Temp(1, ArrayType(INTEGER)), length), temps=2)
    with pytest.raises(IRContractError, match="NEW_ARR"):
        ExtendedMipsBackend.generate(program, _LayoutVacio())


def test_new_obj_de_una_clase_sin_layout_se_rechaza():
    program = _entry_only(
        TACInstruction(Opcode.NEW_OBJ, Temp(0, INTEGER), ClassRef("Fantasma"), metadata=(("fields", 0),)), temps=1,
    )
    with pytest.raises(IRContractError, match="Fantasma"):
        ExtendedMipsBackend.generate(program, _LayoutVacio())


def test_salida_determinista():
    source = """
    class A { let x: integer = 1; function m(): integer { return this.x; } }
    let a: A = new A();
    let v: integer[] = [a.m(), 2];
    try { print(v[5]); } catch (e) { print(e); }
    """
    assert assemble(source) == assemble(source)


def test_vtables_solo_de_clases_instanciadas_y_en_orden_de_slot():
    asm = assemble("""
    class A { function uno(): integer { return 1; } function dos(): integer { return 2; } }
    class B : A { function dos(): integer { return 22; } function tres(): integer { return 3; } }
    class NuncaInstanciada { function m(): integer { return 0; } }
    class Vacia {}
    let b: A = new B();
    let v: Vacia = new Vacia();
    print(b.dos());
    """)
    assert "vt_B: .word fn_A_duno, fn_B_ddos, fn_B_dtres" in asm
    assert "vt_Vacia: .word 0" in asm
    assert "vt_A:" not in asm and "vt_NuncaInstanciada" not in asm


def test_los_chequeos_solo_se_emiten_si_se_usan():
    assert "rt_check_bounds" not in assemble("print(1);")
    assert "rt_check_bounds:" in assemble("let v: integer[] = [1]; print(v[0]);")
    # this nunca es null: un metodo que solo lee sus campos no necesita rt_check_null
    asm = assemble("class A { let x: integer = 1; function m(): integer { return this.x; } }")
    assert "rt_check_null" not in asm
