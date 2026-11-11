import pytest

from compiler.backend.mips.operands import (
    CALLER_SAVED, POOL, RESERVED, SCRATCH, T, Imm, LabelMem, LabelRef, Mem, Reg, SP, mangle_label,
    string_label, vtable_label,
)


def test_reg_valido_e_invalido():
    assert str(Reg("$t3")) == "$t3"
    with pytest.raises(ValueError):
        Reg("$t10")
    with pytest.raises(ValueError):
        Reg("t0")


def test_conjuntos_de_registros_no_se_pisan():
    assert len(POOL) == 8 and len(SCRATCH) == 2
    assert not set(POOL) & set(SCRATCH)
    assert not set(POOL + SCRATCH) & set(RESERVED)
    assert CALLER_SAVED == T


def test_imm_rango_de_32_bits():
    assert str(Imm(-5)) == "-5"
    Imm(2**31 - 1)
    Imm(-(2**31))
    for bad in (2**31, -(2**31) - 1, True, "3"):
        with pytest.raises(ValueError):
            Imm(bad)


def test_mem_y_labelmem_se_renderizan():
    assert str(Mem(-8, SP)) == "-8($sp)"
    assert str(LabelMem("__globals", 12)) == "__globals+12"
    assert str(LabelMem("__globals")) == "__globals"


def test_mem_offset_fuera_de_16_bits_falla():
    with pytest.raises(ValueError):
        Mem(40000, SP)
    with pytest.raises(ValueError):
        LabelMem("x", -4)


@pytest.mark.parametrize("bad", ["", "1abc", "a b", "fn::x", "a#b", "a-b"])
def test_etiqueta_invalida(bad):
    with pytest.raises(ValueError):
        LabelRef(bad)


def test_mangling_de_funciones_y_control():
    assert mangle_label("fn::factorial") == "fn_factorial"
    assert mangle_label("fn::A.m") == "fn_A_dm"
    assert mangle_label("fn::f.g#2") == "fn_f_dg_h2"
    assert mangle_label("fn::my_fn") == "fn_my_ufn"
    assert mangle_label("L_if_else_0") == "L_if_else_0"


def test_mangling_es_inyectivo():
    labels = ["fn::a_d", "fn::a.d", "fn::a_u", "fn::a.u", "fn::a#2", "fn::a_h2", "fn::a", "fn::_", "fn::__"]
    mangled = [mangle_label(label) for label in labels]
    assert len(set(mangled)) == len(labels)


def test_mangling_rechaza_etiquetas_ajenas():
    with pytest.raises(ValueError):
        mangle_label("main")
    with pytest.raises(ValueError):
        mangle_label("L_If_0")


def test_etiquetas_auxiliares():
    assert string_label(3) == "str_3"
    assert vtable_label("Perro") == "vt_Perro"
    with pytest.raises(ValueError):
        vtable_label("a b")
