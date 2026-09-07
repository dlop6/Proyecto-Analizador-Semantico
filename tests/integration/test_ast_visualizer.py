"""
tests de compiler/ast_visualizer.py: fuente DOT (siempre) y render SVG (si 'dot' esta
instalado en el entorno -- se saltea explicitamente si no, no se marca como fallo).
"""
import shutil

import pytest

from compiler.ast_visualizer import render_svg, to_dot
from compiler.frontend import analyze_source

_DOT_AVAILABLE = shutil.which("dot") is not None


def _ast_of(source: str):
    result = analyze_source(source)
    assert result.ast is not None
    return result.ast


def test_to_dot_no_requiere_el_binario_dot():
    dot_source = to_dot(_ast_of("let x: integer = 1;"))
    assert dot_source.startswith("digraph")
    assert "VarDecl" in dot_source
    assert "IntegerLiteral" in dot_source


def test_to_dot_incluye_nodos_de_clases_y_arreglos():
    source = """
    class Animal { let name: string; }
    let a: Animal = new Animal();
    let n: integer[] = [1, 2];
    """
    dot_source = to_dot(_ast_of(source))
    for expected in ("ClassDecl", "NewExpr", "ArrayLiteral"):
        assert expected in dot_source


@pytest.mark.skipif(not _DOT_AVAILABLE, reason="el binario 'dot' de graphviz no esta instalado en este entorno")
def test_render_svg_produce_un_documento_svg_valido():
    svg = render_svg(_ast_of("let x: integer = 1;\nprint(x);"))
    assert svg.strip().startswith("<?xml") or "<svg" in svg
    assert "</svg>" in svg
