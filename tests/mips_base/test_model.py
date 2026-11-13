import pytest

from compiler.backend.mips.model import (
    BRANCH_OPCODES, SIGNATURES, AssemblyInstruction, DataItem, LabelDef,
)
from compiler.backend.mips.operands import T, Imm, LabelMem, LabelRef, Mem, SP


def test_instruccion_valida_se_renderiza():
    instr = AssemblyInstruction("lw", (T[0], Mem(8, SP)))
    assert instr.render() == "    lw $t0, 8($sp)"
    assert AssemblyInstruction("syscall").render() == "    syscall"
    assert AssemblyInstruction("li", (T[1], Imm(3)), "tres").render() == "    li $t1, 3    # tres"


@pytest.mark.parametrize("opcode, operands", [
    ("bogus", ()),                          # opcode fuera de la tabla
    ("li", (T[0], T[1])),                   # li no toma registro como segundo operando
    ("add", (T[0], T[1])),                  # faltan operandos
    ("lw", (T[0], Imm(1))),                 # lw necesita memoria
    ("j", (T[0],)),                         # j necesita etiqueta
    ("syscall", (T[0],)),                   # syscall no lleva operandos
])
def test_instruccion_invalida_falla(opcode, operands):
    with pytest.raises(ValueError):
        AssemblyInstruction(opcode, operands)


def test_lw_acepta_etiqueta_mas_offset():
    assert AssemblyInstruction("lw", (T[0], LabelMem("__globals", 4))).render().endswith("__globals+4")


def test_todas_las_firmas_tienen_al_menos_una_forma_y_los_saltos_existen():
    assert all(forms for forms in SIGNATURES.values())
    assert BRANCH_OPCODES <= set(SIGNATURES)


def test_etiqueta_def():
    assert LabelDef("main").render() == "main:"
    with pytest.raises(ValueError):
        LabelDef("fn::x")


def test_data_items_validos_y_su_texto():
    assert DataItem("s", "asciiz", 'a"b\n').render() == 's: .asciiz "a\\"b\\n"'
    assert DataItem("g", "space", 12).render() == "g: .space 12"
    assert DataItem("v", "word", ("fn_a", 0)).render() == "v: .word fn_a, 0"


@pytest.mark.parametrize("args", [
    ("s", "asciiz", 3), ("g", "space", 5), ("g", "space", -4), ("v", "word", ()),
    ("v", "word", (True,)), ("v", "byte", 1), ("a b", "word", 1),
])
def test_data_item_invalido_falla(args):
    with pytest.raises(ValueError):
        DataItem(*args)


def test_asciiz_rechaza_no_ascii():
    with pytest.raises(ValueError):
        DataItem("s", "asciiz", "ñandú").render()


def test_labelref_en_saltos():
    assert AssemblyInstruction("beq", (T[0], T[1], LabelRef("L_if_0"))).render() == "    beq $t0, $t1, L_if_0"
