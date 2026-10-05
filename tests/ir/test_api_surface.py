"""
api congelada que consumen persona 2 y persona 3 (gate A del pdf). si alguien cambia un
nombre o una firma publica, este test se rompe antes que el codigo de los demas.
"""
import inspect

import pytest

from compiler import extended_semantics
from compiler.ir import builder, serializer
from compiler.runtime import runtime_layout, scoped_visitor


def params(fn):
    return list(inspect.signature(fn).parameters)


def test_semantic_result_es_el_resultado_semantico_final():
    assert extended_semantics.SemanticResult is extended_semantics.ExtendedSemanticResult


@pytest.mark.parametrize("fn,expected", [
    (runtime_layout.prepare, ["result"]),
    (runtime_layout.require_semantic_success, ["result"]),
    (runtime_layout.RuntimeLayout.scope_of, ["self", "node"]),
    (runtime_layout.RuntimeLayout.enclosing_function, ["self", "fn"]),
    (runtime_layout.RuntimeLayout.ref_for, ["self", "symbol", "from_function"]),
    (runtime_layout.RuntimeLayout.link_hops, ["self", "caller", "callee"]),
    (builder.IRBuilder.__init__, ["self", "layout"]),
    (builder.IRBuilder.new_temp, ["self", "type_"]),
    (builder.IRBuilder.release_temp, ["self", "temp"]),
    (builder.IRBuilder.new_label, ["self", "prefix"]),
    (builder.IRBuilder.mark_label, ["self", "label"]),
    (builder.IRBuilder.begin_function, ["self", "fn"]),
    (builder.IRBuilder.end_function, ["self"]),
    (builder.IRBuilder.emit, ["self", "opcode", "result", "arg1", "arg2", "metadata"]),
    (builder.IRBuilder.build, ["self"]),
    (serializer.serialize, ["program"]),
    (scoped_visitor.ScopedVisitor.__init__, ["self", "symbols"]),
    (scoped_visitor.ScopedVisitor.enter, ["self", "node"]),
    (scoped_visitor.ScopedVisitor.resolve, ["self", "name"]),
])
def test_firmas_publicas(fn, expected):
    assert params(fn) == expected


@pytest.mark.parametrize("name", ["labels", "globals_count", "functions", "records", "class_layouts"])
def test_propiedades_del_runtime_layout(name):
    assert isinstance(inspect.getattr_static(runtime_layout.RuntimeLayout, name), property)


@pytest.mark.parametrize("name", ["current_scope", "current_function"])
def test_propiedades_del_scoped_visitor(name):
    assert isinstance(inspect.getattr_static(scoped_visitor.ScopedVisitor, name), property)
