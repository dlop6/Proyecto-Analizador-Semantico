"""docs/BACKEND_MIPS.md no puede mentir: sus ejemplos se regeneran con el codigo real y se buscan literales."""
from pathlib import Path

import pytest

from compiler.backend.mips.helpers import HELPERS
from compiler.backend.mips.operands import T
from compiler.ir.model import Const, Temp
from compiler.types import INTEGER

from .mini_lowerer import uncaught_stub
from .test_abi import harness
from .pipeline import function_named

DOC = (Path(__file__).resolve().parents[2] / "docs" / "BACKEND_MIPS.md").read_text(encoding="utf-8")

SOURCE = """
function outer(x: integer): integer {
    function inner(y: integer): integer { return x + y; }
    return inner(2);
}
function f(a: integer, b: integer): integer { let c: integer = a + b; return c; }
print(f(1, 2));
"""


def _generated() -> str:
    program, builder, alloc, em = harness(SOURCE)
    em.begin_entry()
    for value in (1, 2):
        with alloc.instruction():
            em.emit_arg(Const(value, INTEGER))
    em.emit_call("fn::f", 2, None, Temp(0, INTEGER, 0), on_error=em.error_target())
    em.end_entry()
    em.begin_function(function_named(program, "fn::f"))
    em.end_function()
    inner = function_named(program, "fn::outer.inner")
    em.begin_function(inner)
    with alloc.instruction():
        em.load_value(inner.instructions[1].arg1, T[8])      # x desde inner: nonlocal
    em.end_function()
    em.begin_function(function_named(program, "fn::outer"))
    with alloc.instruction():
        em.emit_arg(Const(2, INTEGER))
    em.emit_call("fn::outer.inner", 1, 0, None, on_error=em.error_target())
    em.end_function()
    uncaught_stub(builder)
    return builder.render()


def _code_blocks() -> list[str]:
    parts = DOC.split("```")
    return [parts[i].strip("\n") for i in range(1, len(parts), 2)]


GENERATED = _generated()


@pytest.mark.parametrize("block", [b for b in _code_blocks() if not b.startswith("mayor")])
def test_cada_ejemplo_del_doc_sale_tal_cual_del_codigo(block):
    assert block in GENERATED, f"el ejemplo ya no coincide con lo que genera el backend:\n{block}"


def test_hay_ejemplos_de_prologo_llamada_y_static_link():
    blocks = _code_blocks()
    assert any(b.startswith("fn_f:") for b in blocks)
    assert any(b.startswith("main:") for b in blocks)
    assert any("static link" in b for b in blocks)


@pytest.mark.parametrize("heading", [
    "Target y cómo se ensambla", "Registros", "ABI y convención de pila", "prólogo y epílogo",
    "Llamadas y argumentos pendientes", "Static link", "Variables", "Selección de registros", "Datos",
    "Errores y helpers de runtime", "Etiquetas", "API para los lowerers", "Supuestos y diferencias con el PDF",
])
def test_secciones_que_pide_el_pdf(heading):
    assert heading in DOC


def test_todos_los_helpers_estan_documentados():
    for name in HELPERS:
        assert f"`{name}`" in DOC, name
