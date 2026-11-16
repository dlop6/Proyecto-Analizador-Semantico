"""cuerpos de los helpers de runtime: catalogo, emision a demanda y casos limite en mars."""
import pytest

from compiler.backend.mips.builder import MipsBuilder
from compiler.backend.mips.helpers import HELPERS
from compiler.backend.mips.runtime_helpers import CORE_RUNTIME, RuntimeLibrary

from .support import output


def test_todo_helper_del_catalogo_tiene_contrato():
    assert set(CORE_RUNTIME) <= set(HELPERS)


def test_un_cuerpo_sin_contrato_se_rechaza():
    with pytest.raises(ValueError, match="sin contrato"):
        RuntimeLibrary({"rt_inventado": lambda b: None})


def test_pedir_un_helper_que_no_esta_implementado_falla():
    with pytest.raises(ValueError, match="no implementa"):
        RuntimeLibrary().require("rt_check_bounds")   # es del backend extendido


def test_solo_emite_lo_pedido_y_en_orden_de_catalogo():
    library = RuntimeLibrary()
    library.require("rt_concat")
    library.require("rt_alloc")
    builder = MipsBuilder("rt_alloc")
    library.emit(builder)
    text = builder.render()
    assert text.index("rt_alloc:") < text.index("rt_concat:")
    assert "rt_int_to_string:" not in text


@pytest.mark.parametrize("value, text", [
    ("0", "0"), ("7", "7"), ("-1", "-1"), ("10", "10"), ("-10", "-10"),
    ("2147483647", "2147483647"), ("(-2147483647 - 1)", "-2147483648"),
])
def test_int_to_string_en_los_bordes(value, text):
    assert output(f'print("[" + {value} + "]");') == [f"[{text}]"]


def test_concatenaciones_largas_reservan_memoria_nueva_cada_vez():
    assert output("""
    let s: string = "";
    for (let i: integer = 0; i < 30; i = i + 1) { s = s + i % 10; }
    let t: string = s;
    s = s + "!";
    print(s); print(t);
    """) == ["012345678901234567890123456789!", "012345678901234567890123456789"]


def test_igualdad_de_prefijos_y_strings_vacios():
    assert output("""
    print("abc" == "ab"); print("ab" == "abc"); print("" == ""); print("" == "a");
    """) == ["false", "false", "true", "false"]
