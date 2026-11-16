"""
arbol de activacion reconstruido desde una ejecucion REAL en mars (no un dibujo del call
graph estatico). la traza la agrega TracingBackend (subclase de prueba): cada activacion
imprime sus argumentos y la direccion de su frame al entrar, y el que llama imprime el valor
devuelto. docs/ACTIVATION_TESTS.md muestra estos mismos arboles y este archivo verifica que
el documento no se desactualice.
"""
from pathlib import Path

import pytest

from .support import (
    INITIAL_SP, TracingBackend, activation_tree, count, max_depth, program_lines, render_tree, run,
)

DOC = Path(__file__).resolve().parents[2] / "docs" / "ACTIVATION_TESTS.md"

FIB = """
function fib(n: integer): integer {
    if (n < 2) { return n; }
    return fib(n - 1) + fib(n - 2);
}
print(fib(4));
"""

POTENCIA = """
function potencia(base: integer, exp: integer): integer {
    function paso(k: integer): integer {
        if (k == 0) { return 1; }
        return base * paso(k - 1);
    }
    return paso(exp);
}
print(potencia(2, 3));
"""

MIXTO = """
function cuadrado(x: integer): integer { return x * x; }
function sumaCuadrados(a: integer, b: integer): integer { return cuadrado(a) + cuadrado(b); }
function factorial(n: integer): integer { if (n <= 1) { return 1; } return n * factorial(n - 1); }
print(sumaCuadrados(3, 4));
print(factorial(3));
"""


def traced(source: str):
    result = run(source, registers=("$sp", "$fp"), backend_class=TracingBackend)
    assert result.ok, result.raw
    lines = result.stdout.splitlines()
    return activation_tree(lines), program_lines(lines), result.registers


def test_arbol_de_fibonacci():
    tree, printed, _ = traced(FIB)
    assert printed == ["3"]
    assert render_tree(tree) == [
        "main",
        "    fn::fib(4) -> 3",
        "        fn::fib(3) -> 2",
        "            fn::fib(2) -> 1",
        "                fn::fib(1) -> 1",
        "                fn::fib(0) -> 0",
        "            fn::fib(1) -> 1",
        "        fn::fib(2) -> 1",
        "            fn::fib(1) -> 1",
        "            fn::fib(0) -> 0",
    ]
    assert count(tree) - 1 == 9      # fib(4) hace 9 activaciones
    assert max_depth(tree) == 5      # main + 4 niveles de fib


def test_cada_activacion_tiene_su_propio_frame_y_los_hermanos_reusan_la_pila():
    tree, _, registers = traced(FIB)
    for node in tree.walk():
        for child in node.children:
            if node.fp is not None:
                assert child.fp < node.fp, "un hijo vive por debajo del frame de su padre"
        # dos llamadas hermanas arrancan con la misma $sp: su frame queda en la misma direccion
        assert len({child.fp for child in node.children}) <= 1
    assert registers["$fp"] == INITIAL_SP     # main recupero su frame al final


def test_static_link_apunta_al_frame_lexico_y_no_al_del_que_llama():
    tree, printed, _ = traced(POTENCIA)
    assert printed == ["8"]
    assert render_tree(tree) == [
        "main",
        "    fn::potencia(2, 3) -> 8",
        "        fn::potencia.paso(3) -> 8",
        "            fn::potencia.paso(2) -> 4",
        "                fn::potencia.paso(1) -> 2",
        "                    fn::potencia.paso(0) -> 1",
    ]
    potencia = tree.children[0]
    pasos = [node for node in potencia.walk() if node.name == "fn::potencia.paso"]
    assert len(pasos) == 4
    # paso(2) la llama paso(3), pero su static link es el frame de potencia: ahi vive `base`
    assert all(node.static_link == potencia.fp for node in pasos)
    assert potencia.static_link is None   # las funciones top-level no reciben static link


def test_arbol_con_varias_funciones_y_llamadas_en_secuencia():
    tree, printed, _ = traced(MIXTO)
    assert printed == ["25", "6"]
    assert render_tree(tree) == [
        "main",
        "    fn::sumaCuadrados(3, 4) -> 25",
        "        fn::cuadrado(3) -> 9",
        "        fn::cuadrado(4) -> 16",
        "    fn::factorial(3) -> 6",
        "        fn::factorial(2) -> 2",
        "            fn::factorial(1) -> 1",
    ]


@pytest.mark.parametrize("source", [FIB, POTENCIA], ids=["fib", "potencia"])
def test_las_direcciones_del_documento_son_las_de_la_ejecucion(source):
    tree, _, _ = traced(source)
    doc = DOC.read_text(encoding="utf-8")
    for node in tree.walk():
        for address in (node.fp, node.static_link):
            if address is not None:
                assert f"`0x{address:08x}`" in doc, f"falta {node.label} en 0x{address:08x}"


@pytest.mark.parametrize("source", [FIB, POTENCIA, MIXTO], ids=["fib", "potencia", "mixto"])
def test_el_documento_muestra_el_arbol_real(source):
    tree, _, _ = traced(source)
    doc = DOC.read_text(encoding="utf-8")
    assert "\n".join(render_tree(tree)) in doc, "docs/ACTIVATION_TESTS.md no coincide con la ejecucion"
