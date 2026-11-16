"""
contrato del backend core: consume solo ir estructurado, despacha cada opcode core a su
handler, rechaza el ir que no sabe bajar sin emitir nada y es determinista.
"""
import pytest

from compiler.backend.mips.core_backend import CoreMipsBackend, IRContractError
from compiler.backend.mips.model import AssemblyProgram
from compiler.frontend import analyze_source
from compiler.ir.model import ClassRef, Const, IRFragment, IRFunction, IRProgram, Label, TACInstruction, Temp
from compiler.ir.opcodes import Opcode
from compiler.types import BOOLEAN, INTEGER, STRING

from tests.mips_base.mars_runner import run_mars

from .support import assemble, backend_for, ir_for

CORE_OPCODES = {
    Opcode.MOV, Opcode.BIN, Opcode.UN, Opcode.PRINT,
    Opcode.LABEL, Opcode.GOTO, Opcode.IF_TRUE, Opcode.IF_FALSE,
    Opcode.FUNC_BEGIN, Opcode.FUNC_END, Opcode.ARG, Opcode.CALL, Opcode.RETURN,
}
EXTENDED_OPCODES = set(Opcode) - CORE_OPCODES


class _LayoutSinFunciones:
    """lo minimo que el backend lee del layout para un programa sin funciones ni variables."""
    globals_count = 0
    functions = ()
    records = {}


def _entry_only(*instructions, temps=0) -> IRProgram:
    return IRProgram(IRFragment(tuple(instructions), temps, temps), ())


def test_hay_un_handler_por_cada_opcode_core():
    assert all(CoreMipsBackend.supports(op) for op in CORE_OPCODES)


@pytest.mark.parametrize("opcode", sorted(EXTENDED_OPCODES, key=lambda o: o.value), ids=lambda o: o.value)
def test_los_opcodes_extendidos_no_tienen_handler_en_el_core(opcode):
    # arreglos, objetos y try/catch son del backend extendido: no se tratan como MOV ni se ignoran
    assert not CoreMipsBackend.supports(opcode)


def test_generate_devuelve_un_programa_de_ensamblador():
    program, layout = ir_for("print(1);")
    assert isinstance(CoreMipsBackend.generate(program, layout), AssemblyProgram)


def test_tac_construido_a_mano_sin_ast_ni_antlr_corre_en_mars():
    # prueba negativa del camino ast -> asm: el backend solo necesita objetos TACInstruction
    t0, t1 = Temp(0, INTEGER), Temp(1, BOOLEAN)
    end = Label("L_if_end_0")
    program = _entry_only(
        TACInstruction(Opcode.BIN, t0, Const(6, INTEGER), Const(7, INTEGER), (("op", "*"),)),
        TACInstruction(Opcode.PRINT, arg1=t0),
        TACInstruction(Opcode.BIN, t1, t0, Const(50, INTEGER), (("op", "<"),)),
        TACInstruction(Opcode.IF_FALSE, arg1=t1, arg2=end),
        TACInstruction(Opcode.PRINT, arg1=Const("menor que 50", STRING)),
        TACInstruction(Opcode.LABEL, arg1=end),
        temps=2,
    )
    asm = CoreMipsBackend.generate(program, _LayoutSinFunciones()).render()
    result = run_mars(asm)
    assert result.ok, result.raw
    assert result.stdout.splitlines() == ["42", "menor que 50"]


def test_no_acepta_un_ast_ni_texto_tac():
    ast = analyze_source("print(1);").ast
    for not_ir in (ast, "  PRINT 1\n", None):
        with pytest.raises(IRContractError, match="IRProgram"):
            CoreMipsBackend(not_ir, _LayoutSinFunciones())


def test_opcode_extendido_rechaza_el_programa_entero_sin_emitir_nada():
    program = _entry_only(
        TACInstruction(Opcode.PRINT, arg1=Const(1, INTEGER)),
        TACInstruction(Opcode.NEW_OBJ, Temp(0, INTEGER), ClassRef("A"), metadata=(("fields", 0),)),
        temps=1,
    )
    with pytest.raises(IRContractError, match="NEW_OBJ"):
        CoreMipsBackend.generate(program, _LayoutSinFunciones())


def test_programa_real_con_clases_y_arreglos_se_rechaza_listando_lo_que_falta():
    program, layout = ir_for("""
    class A { let x: integer; function get(): integer { return this.x; } }
    let a: A = new A();
    let v: integer[] = [1, 2];
    print(a.get() + v[0]);
    """)
    with pytest.raises(IRContractError) as error:
        CoreMipsBackend.generate(program, layout)
    for opcode in ("NEW_OBJ", "GET_FIELD", "CALL_METHOD", "NEW_ARR", "ARR_SET", "ARR_GET"):
        assert opcode in str(error.value)


def test_funcion_sin_func_begin_es_un_contrato_roto():
    broken = IRFunction("fn::f", (TACInstruction(Opcode.RETURN), TACInstruction(Opcode.FUNC_END, arg1=Label("fn::f"),
                                                                                 metadata=(("temps", 0),))), 0, 0)
    program = IRProgram(IRFragment((), 0, 0), (broken,))
    with pytest.raises(IRContractError, match="FUNC_BEGIN"):
        CoreMipsBackend.generate(program, _LayoutSinFunciones())


def test_el_codigo_global_no_puede_abrir_funciones():
    program = _entry_only(TACInstruction(Opcode.FUNC_BEGIN, arg1=Label("fn::f"), metadata=(("frame", 0),)))
    with pytest.raises(IRContractError, match="codigo global"):
        CoreMipsBackend.generate(program, _LayoutSinFunciones())


def test_cada_backend_genera_un_solo_programa():
    backend = backend_for("print(1);")
    backend.build()
    with pytest.raises(RuntimeError):
        backend.build()


def test_salida_determinista():
    source = """
    function fib(n: integer): integer { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); }
    let s: string = "x" + fib(5);
    print(s == "x5");
    """
    assert assemble(source) == assemble(source)


def test_main_va_primero_y_hay_seccion_de_datos_y_de_texto():
    asm = assemble("print(1);")
    lines = asm.splitlines()
    assert lines[0] == ".data"
    assert lines[lines.index(".text") + 1] == "main:"


def test_solo_se_emiten_los_helpers_que_se_usan():
    assert "rt_" not in assemble("let x: integer = 2; print(x * 3);")
    asm = assemble("let x: integer = 2; print(10 / x);")
    assert "rt_check_divisor:" in asm and "rt_concat:" not in asm
    asm = assemble('print("n = " + 3);')
    assert "rt_int_to_string:" in asm and "rt_concat:" in asm and "rt_check_divisor:" not in asm


def test_division_por_constante_distinta_de_cero_no_se_chequea():
    assert "rt_check_divisor" not in assemble("let x: integer = 9; print(x / 3); print(x % 2);")
    assert "rt_check_divisor" in assemble("let x: integer = 9; print(x / 0);")
