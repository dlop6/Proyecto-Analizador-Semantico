"""tests de compiler/symbols.py: clases de simbolo, herencia, constructor por identidad."""
import pytest

from compiler.symbols import ClassSymbol, CONSTRUCTOR_NAME, FunctionSymbol, Symbol, VariableSymbol


def test_symbol_base_defaults():
    s = Symbol(name="x", line=1, column=1)
    assert s.type is None
    assert s.scope_name == ""


def test_variable_symbol_defaults():
    v = VariableSymbol(name="x", line=1, column=1)
    assert v.is_const is False
    assert v.is_param is False
    assert v.is_field is False
    assert v.is_implicit is False
    assert v.is_iteration_var is False
    assert v.initialized is False


def test_function_symbol_arity():
    fn = FunctionSymbol(
        name="suma", line=1, column=1,
        params=[VariableSymbol(name="a", line=1, column=1), VariableSymbol(name="b", line=1, column=1)],
    )
    assert fn.arity == 2


def test_class_symbol_lookup_member_tres_niveles():
    abuelo = ClassSymbol(name="Ser", line=1, column=1)
    abuelo.fields["vivo"] = VariableSymbol(name="vivo", line=1, column=1)

    padre = ClassSymbol(name="Animal", line=2, column=1, parent_name="Ser", parent=abuelo)
    padre.fields["nombre"] = VariableSymbol(name="nombre", line=2, column=1)

    hijo = ClassSymbol(name="Perro", line=3, column=1, parent_name="Animal", parent=padre)
    hijo.methods["ladrar"] = FunctionSymbol(name="ladrar", line=3, column=1)

    assert hijo.lookup_member("ladrar") is hijo.methods["ladrar"]
    assert hijo.lookup_member("nombre") is padre.fields["nombre"]
    assert hijo.lookup_member("vivo") is abuelo.fields["vivo"]


def test_class_symbol_lookup_member_inexistente_da_none():
    cls = ClassSymbol(name="Solo", line=1, column=1)
    assert cls.lookup_member("no_existe") is None


def test_constructor_es_el_mismo_objeto_que_methods():
    cls = ClassSymbol(name="A", line=1, column=1)
    ctor = FunctionSymbol(name=CONSTRUCTOR_NAME, line=1, column=1, is_constructor=True)
    cls.methods[CONSTRUCTOR_NAME] = ctor
    cls.constructor = ctor
    assert cls.constructor is cls.methods[CONSTRUCTOR_NAME]
