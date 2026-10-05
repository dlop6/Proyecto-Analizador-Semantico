"""tests de compiler/ir/opcodes.py y compiler/ir/model.py: el contrato cerrado del ir."""
import pytest

from compiler.ir.model import Const, TACInstruction, Temp
from compiler.ir.opcodes import BINARY_OPERATORS, SIGNATURES, UNARY_OPERATORS, Opcode
from compiler.types import BOOLEAN, INTEGER, NULL, STRING, VOID

PDF_OPCODES = {
    "MOV", "BIN", "UN", "PRINT",
    "LABEL", "GOTO", "IF_TRUE", "IF_FALSE",
    "FUNC_BEGIN", "FUNC_END", "ARG", "CALL", "RETURN",
    "NEW_ARR", "ARR_GET", "ARR_SET", "LEN",
    "NEW_OBJ", "GET_FIELD", "SET_FIELD", "CALL_METHOD",
    "TRY_BEGIN", "TRY_END", "CATCH",
}


def test_opcodes_son_exactamente_los_24_del_pdf():
    assert {op.value for op in Opcode} == PDF_OPCODES
    assert len(Opcode) == 24


def test_cada_opcode_tiene_firma():
    assert set(SIGNATURES) == set(Opcode)
    assert all(sig.form in {"assign", "plain"} for sig in SIGNATURES.values())


def test_operadores_logicos_no_existen_como_bin():
    assert "&&" not in BINARY_OPERATORS and "||" not in BINARY_OPERATORS
    assert UNARY_OPERATORS == {"-", "!"}


@pytest.mark.parametrize("value,type_", [(3, INTEGER), ("hola", STRING), (True, BOOLEAN), (None, NULL)])
def test_constantes_validas(value, type_):
    assert Const(value, type_).value == value


@pytest.mark.parametrize("value,type_", [
    (True, INTEGER), ("3", INTEGER), (1, BOOLEAN), (1, STRING), (0, NULL), (None, VOID),
])
def test_constantes_invalidas_se_rechazan(value, type_):
    with pytest.raises(ValueError):
        Const(value, type_)


def test_temporal_y_su_nombre():
    assert Temp(3, INTEGER).name == "t3"


def test_instruccion_es_inmutable_y_expone_metadata():
    instruction = TACInstruction(Opcode.CALL, arg1=None, metadata=(("argc", 2),))
    assert instruction.meta("argc") == 2
    assert instruction.meta("link") is None
    with pytest.raises(AttributeError):
        instruction.opcode = Opcode.MOV  # type: ignore[misc]
