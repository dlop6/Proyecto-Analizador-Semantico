import pytest

from compiler.backend.mips.builder import MipsBuilder
from compiler.backend.mips.operands import A0, SP, T, V0, Imm, LabelMem, LabelRef, Mem
from tests.mips_base.mars_runner import run_mars


def _hello() -> MipsBuilder:
    b = MipsBuilder()
    label = b.add_string("hola\n")
    b.mark("main")
    b.emit("la", A0, LabelRef(label))
    b.emit("li", V0, Imm(4))
    b.emit("syscall")
    b.emit("li", V0, Imm(10))
    b.emit("syscall")
    return b


def test_render_corre_en_mars():
    result = run_mars(_hello().render())
    assert result.ok and result.stdout == "hola\n"


def test_render_es_determinista_byte_a_byte():
    assert _hello().render() == _hello().render()


def test_strings_se_deduplican_por_primera_aparicion():
    b = MipsBuilder()
    assert b.add_string("a") == "str_0"
    assert b.add_string("b") == "str_1"
    assert b.add_string("a") == "str_0"


def test_etiqueta_repetida_falla():
    b = MipsBuilder()
    b.mark("main")
    with pytest.raises(ValueError):
        b.mark("main")
    with pytest.raises(ValueError):
        b.add_data("main", "word", 0)


def test_salto_huerfano_falla_al_construir():
    b = MipsBuilder()
    b.mark("main")
    b.emit_branch("j", LabelRef("nada"))
    with pytest.raises(ValueError, match="inexistente"):
        b.render()


def test_referencia_de_datos_huerfana_falla():
    b = MipsBuilder()
    b.add_data("vt", "word", ("fn_nada",))
    b.mark("main")
    with pytest.raises(ValueError, match="inexistente"):
        b.render()


def test_emit_branch_rechaza_opcodes_que_no_saltan():
    b = MipsBuilder()
    with pytest.raises(ValueError):
        b.emit_branch("li", T[0], Imm(1))


def test_instruccion_invalida_falla_al_emitir():
    b = MipsBuilder()
    with pytest.raises(ValueError):
        b.emit("lw", T[0], T[1])


def test_la_entrada_tiene_que_ser_lo_primero():
    b = MipsBuilder()
    b.mark("otra")
    b.mark("main")
    with pytest.raises(ValueError, match="entrada"):
        b.render()
    with pytest.raises(ValueError, match="entrada"):
        MipsBuilder().render()


def test_referencias_a_datos_con_offset_resuelven_en_mars():
    b = MipsBuilder()
    b.add_data("__globals", "space", 8)
    b.mark("main")
    b.emit("li", T[0], Imm(9))
    b.emit("sw", T[0], LabelMem("__globals", 4))
    b.emit("lw", T[1], Mem(0, SP))
    b.emit("li", V0, Imm(10))
    b.emit("syscall")
    assert run_mars(b.render()).ok
