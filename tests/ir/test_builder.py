"""
tests de compiler/ir/builder.py: el builder rechaza todo lo que viole el contrato del
ir y arma unidades independientes por funcion.
"""
import pytest

from compiler.ir.builder import IRBuilder, IRError
from compiler.ir.model import ClassRef, Const, Label, MethodRef
from compiler.ir.opcodes import Opcode
from compiler.runtime.storage import StorageKind, StorageRef
from compiler.types import BOOLEAN, INTEGER, STRING, ClassType

from .conftest import function_named, layout_for, variable

SOURCE = (
    "let g: integer = 1;\n"
    "function f(a: integer): integer {\n"
    "  let x: integer = a;\n"
    "  function h(): integer { return x; }\n"
    "  function p(n: integer): integer { return n; }\n"
    "  return h();\n"
    "}\n"
    "class A { let v: integer; function m(): integer { return this.v; } }\n"
)


@pytest.fixture
def ctx():
    result, layout = layout_for(SOURCE)
    return result, layout, IRBuilder(layout)


def g_ref(result, layout):
    return layout.ref_for(variable(result, "global", "g"), None)


# ---------- construccion ----------

def test_sin_layout_no_hay_builder():
    with pytest.raises(IRError):
        IRBuilder(None)  # type: ignore[arg-type]


def test_programa_vacio():
    _, layout = layout_for("let g: integer = 1;")
    program = IRBuilder(layout).build()
    assert program.entry.instructions == ()
    assert program.functions == ()


# ---------- firmas y roles ----------

def test_falta_un_operando_obligatorio(ctx):
    _, _, b = ctx
    with pytest.raises(IRError):
        b.emit(Opcode.PRINT)


def test_sobra_un_operando(ctx):
    _, _, b = ctx
    with pytest.raises(IRError):
        b.emit(Opcode.PRINT, Const(1, INTEGER), Const(1, INTEGER))


def test_constante_no_puede_ser_destino(ctx):
    _, _, b = ctx
    with pytest.raises(IRError):
        b.emit(Opcode.MOV, Const(1, INTEGER), Const(2, INTEGER))


def test_etiqueta_no_es_un_valor(ctx):
    _, _, b = ctx
    with pytest.raises(IRError):
        b.emit(Opcode.PRINT, arg1=b.new_label("x"))


def test_campo_solo_se_toca_con_get_y_set_field(ctx):
    _, _, b = ctx
    field = StorageRef(StorageKind.FIELD, 0, name="v")
    with pytest.raises(IRError):
        b.emit(Opcode.PRINT, arg1=field)


def test_bin_logico_se_rechaza(ctx):
    result, layout, b = ctx
    t = b.new_temp(BOOLEAN)
    with pytest.raises(IRError):
        b.emit(Opcode.BIN, t, Const(True, BOOLEAN), Const(False, BOOLEAN), op="&&")


def test_metadata_desconocida_o_faltante(ctx):
    result, layout, b = ctx
    t = b.new_temp(INTEGER)
    with pytest.raises(IRError):
        b.emit(Opcode.BIN, t, Const(1, INTEGER), Const(2, INTEGER), op="+", extra=1)
    with pytest.raises(IRError):
        b.emit(Opcode.BIN, t, Const(1, INTEGER), Const(2, INTEGER))


@pytest.mark.parametrize("argc", [-1, True, "1"])
def test_argc_tiene_que_ser_entero_no_negativo(ctx, argc):
    result, layout, b = ctx
    b.begin_function(function_named(layout, "fn::A.m"))
    with pytest.raises(IRError):
        b.emit(Opcode.CALL, arg1=Label("fn::f"), argc=argc)


def test_opcodes_estructurales_no_se_emiten_a_mano(ctx):
    _, _, b = ctx
    with pytest.raises(IRError):
        b.emit(Opcode.LABEL, arg1=b.new_label("x"))
    with pytest.raises(IRError):
        b.emit(Opcode.FUNC_BEGIN, arg1=Label("fn::f"), frame=1)


# ---------- temporales ----------

def test_temporal_liberado_no_se_puede_usar(ctx):
    _, _, b = ctx
    t = b.new_temp(INTEGER)
    b.release_temp(t)
    with pytest.raises(IRError):
        b.emit(Opcode.PRINT, arg1=t)


def test_quedar_con_temporales_vivos_falla_al_construir(ctx):
    _, _, b = ctx
    b.new_temp(INTEGER)
    with pytest.raises(IRError):
        b.build()


def test_cada_funcion_arranca_en_t0_y_no_comparte_temporales(ctx):
    result, layout, b = ctx
    entry_temp = b.new_temp(INTEGER)
    b.begin_function(function_named(layout, "fn::A.m"))
    assert b.new_temp(INTEGER).name == "t0"
    with pytest.raises(IRError):
        b.emit(Opcode.PRINT, arg1=entry_temp)  # vive en otra unidad


# ---------- etiquetas ----------

def test_etiqueta_ajena_se_rechaza(ctx):
    _, _, b = ctx
    with pytest.raises(IRError):
        b.emit(Opcode.GOTO, arg1=Label("L_inventada_9"))


def test_etiqueta_marcada_dos_veces_se_rechaza(ctx):
    _, _, b = ctx
    label = b.new_label("if_end")
    b.mark_label(label)
    with pytest.raises(IRError):
        b.mark_label(label)


def test_salto_a_etiqueta_nunca_marcada_falla_al_construir(ctx):
    _, _, b = ctx
    b.emit(Opcode.GOTO, arg1=b.new_label("while_end"))
    with pytest.raises(IRError):
        b.build()


def test_salto_a_etiqueta_de_otra_unidad_falla_al_construir(ctx):
    _, layout, b = ctx
    label = b.new_label("x")
    b.emit(Opcode.GOTO, arg1=label)
    b.begin_function(function_named(layout, "fn::A.m"))
    b.mark_label(label)
    b.end_function()
    with pytest.raises(IRError):
        b.build()


# ---------- funciones ----------

def test_begin_y_end_function_emiten_frame_y_pico(ctx):
    result, layout, b = ctx
    m = function_named(layout, "fn::A.m")
    b.begin_function(m)
    t = b.new_temp(INTEGER)
    b.release_temp(t)
    function = b.end_function()
    assert function.instructions[0].opcode is Opcode.FUNC_BEGIN
    assert function.instructions[0].meta("frame") == 1
    assert function.instructions[-1].meta("temps") == 1
    assert (function.peak_temps, function.created_temps) == (1, 1)


def test_anidada_no_interrumpe_el_codigo_de_la_exterior(ctx):
    result, layout, b = ctx
    f, p = function_named(layout, "fn::f"), function_named(layout, "fn::f.p")
    b.begin_function(f)
    b.emit(Opcode.PRINT, arg1=Const(1, INTEGER))
    b.begin_function(p)
    b.emit(Opcode.PRINT, arg1=Const(2, INTEGER))
    b.end_function()
    b.emit(Opcode.PRINT, arg1=Const(3, INTEGER))
    b.end_function()
    program = b.build()
    outer = next(fn for fn in program.functions if fn.label == "fn::f")
    printed = [i.arg1.value for i in outer.instructions if i.opcode is Opcode.PRINT]
    assert printed == [1, 3]
    assert [fn.label for fn in program.functions] == ["fn::f.p", "fn::f"]


def test_funcion_emitida_dos_veces_se_rechaza(ctx):
    _, layout, b = ctx
    m = function_named(layout, "fn::A.m")
    b.begin_function(m)
    b.end_function()
    with pytest.raises(IRError):
        b.begin_function(m)


def test_end_function_sin_funcion_abierta(ctx):
    _, _, b = ctx
    with pytest.raises(IRError):
        b.end_function()


def test_construir_con_una_funcion_abierta_falla(ctx):
    _, layout, b = ctx
    b.begin_function(function_named(layout, "fn::A.m"))
    with pytest.raises(IRError):
        b.build()


def test_call_a_funcion_que_nunca_se_emitio_falla_al_construir(ctx):
    _, _, b = ctx
    b.emit(Opcode.CALL, arg1=Label("fn::f"), argc=0)
    with pytest.raises(IRError):
        b.build()


def test_call_con_link_y_sin_resultado(ctx):
    result, layout, b = ctx
    f, h = function_named(layout, "fn::f"), function_named(layout, "fn::f.h")
    b.begin_function(f)
    b.emit(Opcode.CALL, arg1=Label(h.label), argc=0, link=layout.link_hops(f, h))
    b.emit(Opcode.RETURN)
    b.end_function()
    b.begin_function(h)
    b.end_function()
    call = next(i for fn in b.build().functions for i in fn.instructions if i.opcode is Opcode.CALL)
    assert call.metadata == (("argc", 0), ("link", 0))


# ---------- visibilidad de StorageRef ----------

def test_variable_de_frame_en_codigo_global_se_rechaza(ctx):
    _, _, b = ctx
    with pytest.raises(IRError):
        b.emit(Opcode.PRINT, arg1=StorageRef(StorageKind.LOCAL, 0, name="x"))


def test_slot_global_inexistente_se_rechaza(ctx):
    _, _, b = ctx
    with pytest.raises(IRError):
        b.emit(Opcode.PRINT, arg1=StorageRef(StorageKind.GLOBAL, 5, name="zz"))


def test_this_fuera_de_metodo_se_rechaza(ctx):
    _, layout, b = ctx
    b.begin_function(function_named(layout, "fn::f"))
    with pytest.raises(IRError):
        b.emit(Opcode.PRINT, arg1=StorageRef(StorageKind.THIS, 0, name="this"))


def test_nonlocal_requiere_static_link(ctx):
    result, layout, b = ctx
    x = variable(result, "function:f", "x")
    p = function_named(layout, "fn::f.p")  # sin static link
    b.begin_function(p)
    with pytest.raises(IRError):
        b.emit(Opcode.PRINT, arg1=StorageRef(StorageKind.NONLOCAL, x.slot, 1, "x"))


def test_nonlocal_valido_con_static_link(ctx):
    result, layout, b = ctx
    h = function_named(layout, "fn::f.h")
    b.begin_function(h)
    b.emit(Opcode.RETURN, arg1=layout.ref_for(variable(result, "function:f", "x"), h))
    assert b.end_function().instructions[1].arg1.kind is StorageKind.NONLOCAL


def test_objetos_y_arreglos_con_operandos_correctos(ctx):
    result, layout, b = ctx
    obj = b.new_temp(ClassType("A"))
    b.emit(Opcode.NEW_OBJ, obj, ClassRef("A"), fields=1)
    b.emit(Opcode.SET_FIELD, obj, StorageRef(StorageKind.FIELD, 0, name="v"), Const(1, INTEGER))
    b.emit(Opcode.CALL_METHOD, None, obj, MethodRef("m", 0), argc=0)
    b.release_temp(obj)
    assert len(b.build().entry.instructions) == 3


def test_string_como_valor_constante(ctx):
    _, _, b = ctx
    b.emit(Opcode.PRINT, arg1=Const("hola", STRING))
    assert b.build().entry.instructions[0].arg1.value == "hola"
