"""
tests de compiler/ir/serializer.py: forma textual exacta de los 24 opcodes y de cada
tipo de operando. el texto es el contrato que lee el calificador en la gui.
"""
import pytest

from compiler.ir.model import (
    ClassRef, Const, IRFragment, IRFunction, IRProgram, Label, MethodRef, TACInstruction, Temp,
)
from compiler.ir.opcodes import Opcode
from compiler.ir.serializer import instruction_text, operand_text, serialize
from compiler.runtime.storage import StorageKind, StorageRef
from compiler.types import BOOLEAN, INTEGER, NULL, STRING, ClassType

t0, t1, t2 = Temp(0, INTEGER), Temp(1, INTEGER), Temp(2, ClassType("A"))
x = StorageRef(StorageKind.GLOBAL, 3, name="x")
n = StorageRef(StorageKind.PARAM, 0, name="n")
v = StorageRef(StorageKind.FIELD, 1, name="v")
e = StorageRef(StorageKind.LOCAL, 4, name="e")
L = Label("L_if_else_0")
F = Label("fn::factorial")


def I(opcode, result=None, arg1=None, arg2=None, **meta):
    return TACInstruction(opcode, result, arg1, arg2, tuple(meta.items()))


EXPECTED = [
    (I(Opcode.MOV, x, t1), "  MOV x@global[3], t1"),
    (I(Opcode.BIN, t0, x, n, op="*"), "  t0 = BIN *, x@global[3], n@frame[0]"),
    (I(Opcode.UN, t1, t0, op="-"), "  t1 = UN -, t0"),
    (I(Opcode.PRINT, arg1=Const("hola", STRING)), '  PRINT "hola"'),
    (I(Opcode.LABEL, arg1=L), "LABEL L_if_else_0"),
    (I(Opcode.GOTO, arg1=L), "  GOTO L_if_else_0"),
    (I(Opcode.IF_TRUE, arg1=t0, arg2=L), "  IF_TRUE t0, L_if_else_0"),
    (I(Opcode.IF_FALSE, arg1=t0, arg2=L), "  IF_FALSE t0, L_if_else_0"),
    (I(Opcode.FUNC_BEGIN, arg1=F, frame=1), "FUNC_BEGIN fn::factorial, frame=1"),
    (I(Opcode.FUNC_END, arg1=F, temps=2), "FUNC_END fn::factorial, temps=2"),
    (I(Opcode.ARG, arg1=t1), "  ARG t1"),
    (I(Opcode.CALL, t0, F, argc=1), "  CALL t0, fn::factorial, argc=1"),
    (I(Opcode.CALL, None, F, argc=0, link=1), "  CALL fn::factorial, argc=0, link=1"),
    (I(Opcode.RETURN, arg1=t0), "  RETURN t0"),
    (I(Opcode.RETURN), "  RETURN"),
    (I(Opcode.NEW_ARR, t2, Const(3, INTEGER)), "  t2 = NEW_ARR 3"),
    (I(Opcode.ARR_GET, t0, t2, Const(1, INTEGER)), "  t0 = ARR_GET t2, 1"),
    (I(Opcode.ARR_SET, t2, Const(0, INTEGER), t1), "  ARR_SET t2, 0, t1"),
    (I(Opcode.LEN, t0, t2), "  t0 = LEN t2"),
    (I(Opcode.NEW_OBJ, t2, ClassRef("Perro"), fields=2), "  t2 = NEW_OBJ Perro, fields=2"),
    (I(Opcode.GET_FIELD, t0, t2, v), "  t0 = GET_FIELD t2, v@field[1]"),
    (I(Opcode.SET_FIELD, t2, v, t1), "  SET_FIELD t2, v@field[1], t1"),
    (I(Opcode.CALL_METHOD, t0, t2, MethodRef("hablar", 0), argc=0), "  CALL_METHOD t0, t2, hablar[0], argc=0"),
    (I(Opcode.TRY_BEGIN, arg1=Label("L_try_handler_3")), "  TRY_BEGIN L_try_handler_3"),
    (I(Opcode.TRY_END), "  TRY_END"),
    (I(Opcode.CATCH, arg1=e), "  CATCH e@frame[4]"),
]


@pytest.mark.parametrize("instruction,text", EXPECTED, ids=[i.opcode.value for i, _ in EXPECTED])
def test_forma_textual_de_cada_opcode(instruction, text):
    assert instruction_text(instruction) == text


def test_los_24_opcodes_tienen_forma_probada():
    assert {i.opcode for i, _ in EXPECTED} == set(Opcode)


@pytest.mark.parametrize("value,text", [
    (Const(42, INTEGER), "42"),
    (Const(True, BOOLEAN), "true"),
    (Const(False, BOOLEAN), "false"),
    (Const(None, NULL), "null"),
    (Const('di "hola"\\n', STRING), '"di \\"hola\\"\\\\n"'),
    (Const("canción", STRING), '"canción"'),
    (StorageRef(StorageKind.THIS, 0, name="this"), "this@frame[0]"),
    (StorageRef(StorageKind.NONLOCAL, 2, lexical_depth=1, name="x"), "x@frame^1[2]"),
    (MethodRef("m", 3), "m[3]"),
])
def test_forma_de_operandos(value, text):
    assert operand_text(value) == text


def test_operando_desconocido_se_rechaza():
    with pytest.raises(TypeError):
        operand_text(object())  # type: ignore[arg-type]


def test_programa_completo_global_primero_y_funciones_separadas():
    program = IRProgram(
        entry=IRFragment((I(Opcode.PRINT, arg1=Const(1, INTEGER)),), 0, 0),
        functions=(
            IRFunction("fn::f", (I(Opcode.FUNC_BEGIN, arg1=Label("fn::f"), frame=0),
                                 I(Opcode.RETURN),
                                 I(Opcode.FUNC_END, arg1=Label("fn::f"), temps=0)), 0, 0),
        ),
    )
    assert serialize(program) == "  PRINT 1\n\nFUNC_BEGIN fn::f, frame=0\n  RETURN\nFUNC_END fn::f, temps=0\n"
    assert serialize(program) == serialize(program)


def test_programa_vacio_es_texto_vacio():
    assert serialize(IRProgram(IRFragment((), 0, 0), ())) == ""
