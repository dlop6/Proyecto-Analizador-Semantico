"""
tests de compiler/runtime/scoped_visitor.py: cada identificador se resuelve al mismo
simbolo que declaro el collector. los casos con sombra son los que delatan un orden de
recorrido distinto al del collector.
"""
import pytest

from compiler.ast_nodes import Identifier, ThisExpr
from compiler.frontend import analyze_source
from compiler.runtime.scoped_visitor import ScopedVisitor, all_functions, index_scopes
from compiler.symbols import THIS_NAME


class _Recorder(ScopedVisitor):
    """anota (nombre, scope donde vive el simbolo, funcion activa) por cada uso."""

    def __init__(self, symbols):
        super().__init__(symbols)
        self.uses = []

    def _record(self, name):
        symbol = self.resolve(name)
        fn = self.current_function
        self.uses.append((name, symbol.scope_name if symbol else None, fn.name if fn else None))

    def visit_Identifier(self, node: Identifier):
        self._record(node.name)

    def visit_ThisExpr(self, node: ThisExpr):
        self._record(THIS_NAME)


def uses(source):
    result = analyze_source(source)
    assert result.ast is not None, result.diagnostics
    recorder = _Recorder(result.symbols)
    recorder.visit(result.ast)
    return recorder.uses


def test_condicion_de_while_se_resuelve_fuera_del_loop():
    found = uses("let y: integer = 1; while (y > 0) { let y: integer = 0; print(y); }")
    assert found == [("y", "global", None), ("y", "loop", None)]


def test_condicion_de_do_while_se_resuelve_fuera_del_loop():
    found = uses("let y: integer = 1; do { let y: integer = 0; print(y); } while (y > 0);")
    assert found == [("y", "loop", None), ("y", "global", None)]


def test_iterable_de_foreach_se_resuelve_fuera_del_loop():
    found = uses("let x: integer[] = [1]; foreach (x in x) { print(x); }")
    assert found == [("x", "global", None), ("x", "loop", None)]


def test_sujeto_de_switch_se_resuelve_fuera_del_switch():
    found = uses("let s: integer = 1; switch (s) { case 1: let s: integer = 2; print(s); }")
    assert found == [("s", "global", None), ("s", "switch", None)]


def test_try_usa_bloque_propio_y_catch_su_scope():
    found = uses('let e: string = "a"; try { print(e); } catch (e) { print(e); }')
    assert found == [("e", "global", None), ("e", "catch", None)]


def test_cabecera_de_for_en_loop_y_cuerpo_en_bloque():
    found = uses("for (let i: integer = 0; i < 3; i = i + 1) { let i: integer = 5; print(i); }")
    assert found == [("i", "loop", None), ("i", "loop", None), ("i", "loop", None), ("i", "block", None)]


def test_funcion_activa_en_anidadas_y_metodos():
    found = uses(
        "function f(a: integer) { function g() { print(a); } print(a); }\n"
        "class C { function m() { print(this); } }"
    )
    assert found == [("a", "function:f", "g"), ("a", "function:f", "f"), ("this", "function:m", "m")]


def test_codigo_global_no_tiene_funcion_activa():
    assert uses("let z: integer = 1; print(z);") == [("z", "global", None)]


def test_indice_y_funciones_cubren_metodos_y_anidadas():
    result = analyze_source("function f() { function g() {} } class C { function constructor() {} function m() {} }")
    names = sorted(fn.name for fn in all_functions(result.symbols))
    assert names == ["constructor", "f", "g", "m"]
    assert len(index_scopes(result.symbols)) == sum(1 for _ in result.symbols.all_scopes()) - 1


def test_dos_scopes_en_la_misma_posicion_es_error_interno():
    result = analyze_source("function f() {}")
    scope = next(s for s in result.symbols.all_scopes() if s.name == "function:f")
    from compiler.scopes import Scope, ScopeKind
    Scope(ScopeKind.BLOCK, "intruso", parent=scope, line=scope.line, column=scope.column)
    with pytest.raises(RuntimeError):
        index_scopes(result.symbols)
