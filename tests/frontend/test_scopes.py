"""
tests de compiler/scopes.py: Scope (pasivo) y SymbolTable (cursor + arbol).
cubre H (mecanica de scopes) y J (separacion Scope vs SymbolTable) del plan.
"""
import pytest

from compiler.scopes import Scope, ScopeKind, SymbolTable
from compiler.symbols import VariableSymbol


def test_declare_duplicado_local_da_false():
    scope = Scope(ScopeKind.GLOBAL, "global", parent=None)
    assert scope.declare(VariableSymbol(name="x", line=1, column=1)) is True
    assert scope.declare(VariableSymbol(name="x", line=2, column=1)) is False


def test_lookup_local_vs_lookup():
    parent = Scope(ScopeKind.GLOBAL, "global", parent=None)
    parent.declare(VariableSymbol(name="g", line=1, column=1))
    child = Scope(ScopeKind.BLOCK, "block", parent=parent)

    assert child.lookup_local("g") is None       # no esta en ESTE scope
    assert child.lookup("g") is not None          # pero lookup sube y lo encuentra


def test_lookup_sube_n_niveles():
    root = Scope(ScopeKind.GLOBAL, "global", parent=None)
    root.declare(VariableSymbol(name="g", line=1, column=1))
    a = Scope(ScopeKind.BLOCK, "a", parent=root)
    b = Scope(ScopeKind.BLOCK, "b", parent=a)
    c = Scope(ScopeKind.BLOCK, "c", parent=b)
    assert c.lookup("g") is not None


def test_lookup_no_encontrado_da_none():
    root = Scope(ScopeKind.GLOBAL, "global", parent=None)
    assert root.lookup("no_existe") is None


def test_shadowing_variable_del_padre():
    root = Scope(ScopeKind.GLOBAL, "global", parent=None)
    root.declare(VariableSymbol(name="x", line=1, column=1, type=None))
    child = Scope(ScopeKind.BLOCK, "block", parent=root)
    inner = VariableSymbol(name="x", line=2, column=1)
    child.declare(inner)  # sombrea al de arriba, no es duplicado (scopes distintos)
    assert child.lookup("x") is inner


def test_lookup_no_baja_a_hijos():
    root = Scope(ScopeKind.GLOBAL, "global", parent=None)
    child = Scope(ScopeKind.BLOCK, "block", parent=root)
    child.declare(VariableSymbol(name="solo_en_hijo", line=1, column=1))
    assert root.lookup("solo_en_hijo") is None  # cubre "padre de scope incorrecto" de Gate A


def test_enclosing_class_y_function():
    root = Scope(ScopeKind.GLOBAL, "global", parent=None)
    cls_scope = Scope(ScopeKind.CLASS, "class:A", parent=root)
    fn_scope = Scope(ScopeKind.FUNCTION, "function:m", parent=cls_scope)
    block_scope = Scope(ScopeKind.BLOCK, "block", parent=fn_scope)

    assert block_scope.enclosing_function() is fn_scope
    assert block_scope.enclosing_class() is cls_scope
    assert root.enclosing_class() is None


# ---------- SymbolTable ----------

def test_symbol_table_push_es_context_manager_y_restaura_current():
    table = SymbolTable()
    assert table.current is table.global_scope
    with table.push(ScopeKind.BLOCK, "b") as scope:
        assert table.current is scope
        assert scope.parent is table.global_scope
    assert table.current is table.global_scope


def test_symbol_table_push_restaura_current_ante_excepcion():
    table = SymbolTable()
    with pytest.raises(ValueError):
        with table.push(ScopeKind.BLOCK, "boom"):
            raise ValueError("boom")
    assert table.current is table.global_scope


def test_symbol_table_declare_y_lookup():
    table = SymbolTable()
    assert table.declare(VariableSymbol(name="g", line=1, column=1)) is not None
    with table.push(ScopeKind.BLOCK, "b"):
        assert table.lookup("g") is not None  # sube al global


def test_symbol_table_declare_duplicado_da_none():
    table = SymbolTable()
    table.declare(VariableSymbol(name="x", line=1, column=1))
    assert table.declare(VariableSymbol(name="x", line=2, column=1)) is None


def test_all_scopes_orden_preorder_determinista():
    table = SymbolTable()
    with table.push(ScopeKind.BLOCK, "a"):
        with table.push(ScopeKind.BLOCK, "a1"):
            pass
        with table.push(ScopeKind.BLOCK, "a2"):
            pass
    names = [s.name for s in table.all_scopes()]
    assert names == ["global", "a", "a1", "a2"]
