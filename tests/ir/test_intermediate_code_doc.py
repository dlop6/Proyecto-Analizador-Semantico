"""
docs/INTERMEDIATE_CODE.md no puede desincronizarse del codigo: cada ejemplo del
documento se arma aca con el IRBuilder real y su texto serializado tiene que aparecer
literalmente en el .md. si se cambia el formato, el doc falla hasta que se actualice.

los ejemplos muestran ademas las convenciones de lowering que van a seguir persona 2
y persona 3 (cortocircuito, static link, constructores, metodos, try/catch).
"""
from pathlib import Path

import pytest

from compiler.ir.builder import IRBuilder
from compiler.ir.model import ClassRef, Const, Label, MethodRef
from compiler.ir.opcodes import Opcode
from compiler.ir.serializer import serialize
from compiler.types import BOOLEAN, INTEGER, STRING, ArrayType, ClassType

from .conftest import function_named, layout_for, variable

DOC = Path(__file__).resolve().parents[2] / "docs" / "INTERMEDIATE_CODE.md"


def _global(result, layout, name):
    return layout.ref_for(variable(result, "global", name), None)


def example_aritmetica_y_reciclaje():
    result, layout = layout_for(
        "let a: integer = 1; let b: integer = 2; let c: integer = 3;\n"
        "let x: integer = 0; let y: integer = 0;\n"
        "x = a + b * c;\ny = b - c;"
    )
    g = lambda name: _global(result, layout, name)  # noqa: E731
    b = IRBuilder(layout)
    t0 = b.new_temp(INTEGER)
    b.emit(Opcode.BIN, t0, g("b"), g("c"), op="*")
    t1 = b.new_temp(INTEGER)
    b.emit(Opcode.BIN, t1, g("a"), t0, op="+")
    b.release_temp(t0)
    b.emit(Opcode.MOV, g("x"), t1)
    b.release_temp(t1)
    t = b.new_temp(INTEGER)  # reusa t0
    b.emit(Opcode.BIN, t, g("b"), g("c"), op="-")
    b.emit(Opcode.MOV, g("y"), t)
    b.release_temp(t)
    return serialize(b.build())


def example_cortocircuito():
    result, layout = layout_for("let p: boolean = true; let q: boolean = false; let r: boolean = p && q;")
    g = lambda name: _global(result, layout, name)  # noqa: E731
    b = IRBuilder(layout)
    t = b.new_temp(BOOLEAN)
    end = b.new_label("and_end")
    b.emit(Opcode.MOV, t, g("p"))
    b.emit(Opcode.IF_FALSE, None, t, end)
    b.emit(Opcode.MOV, t, g("q"))
    b.mark_label(end)
    b.emit(Opcode.MOV, g("r"), t)
    b.release_temp(t)
    return serialize(b.build())


def example_recursion():
    result, layout = layout_for(
        "function factorial(n: integer): integer {\n"
        "  if (n <= 1) { return 1; }\n"
        "  return n * factorial(n - 1);\n"
        "}"
    )
    f = function_named(layout, "fn::factorial")
    n = layout.ref_for(variable(result, "function:factorial", "n"), f)
    b = IRBuilder(layout)
    b.begin_function(f)
    cond = b.new_temp(BOOLEAN)
    b.emit(Opcode.BIN, cond, n, Const(1, INTEGER), op="<=")
    else_ = b.new_label("if_end")
    b.emit(Opcode.IF_FALSE, None, cond, else_)
    b.release_temp(cond)
    b.emit(Opcode.RETURN, arg1=Const(1, INTEGER))
    b.mark_label(else_)
    arg = b.new_temp(INTEGER)
    b.emit(Opcode.BIN, arg, n, Const(1, INTEGER), op="-")
    b.emit(Opcode.ARG, arg1=arg)
    b.release_temp(arg)
    call = b.new_temp(INTEGER)
    b.emit(Opcode.CALL, call, Label(f.label), argc=1)
    product = b.new_temp(INTEGER)
    b.emit(Opcode.BIN, product, n, call, op="*")
    b.release_temp(call)
    b.emit(Opcode.RETURN, arg1=product)
    b.release_temp(product)
    b.end_function()
    return serialize(b.build())


def example_funcion_anidada():
    result, layout = layout_for(
        "function contador(): integer {\n"
        "  let total: integer = 10;\n"
        "  function sumar(n: integer): integer { return total + n; }\n"
        "  return sumar(5);\n"
        "}"
    )
    outer, inner = function_named(layout, "fn::contador"), function_named(layout, "fn::contador.sumar")
    total = variable(result, "function:contador", "total")
    b = IRBuilder(layout)
    b.begin_function(outer)
    b.emit(Opcode.MOV, layout.ref_for(total, outer), Const(10, INTEGER))
    b.begin_function(inner)
    s = b.new_temp(INTEGER)
    b.emit(Opcode.BIN, s, layout.ref_for(total, inner),
           layout.ref_for(variable(result, "function:sumar", "n"), inner), op="+")
    b.emit(Opcode.RETURN, arg1=s)
    b.release_temp(s)
    b.end_function()
    b.emit(Opcode.ARG, arg1=Const(5, INTEGER))
    r = b.new_temp(INTEGER)
    b.emit(Opcode.CALL, r, Label(inner.label), argc=1, link=layout.link_hops(outer, inner))
    b.emit(Opcode.RETURN, arg1=r)
    b.release_temp(r)
    b.end_function()
    return serialize(b.build())


def example_objetos():
    result, layout = layout_for(
        "class Animal {\n"
        "  let nombre: string;\n"
        "  function constructor(n: string) { this.nombre = n; }\n"
        "  function hablar(): string { return this.nombre; }\n"
        "}\n"
        'let a: Animal = new Animal("Rex");\n'
        "print(a.hablar());"
    )
    ctor, hablar = function_named(layout, "fn::Animal.constructor"), function_named(layout, "fn::Animal.hablar")
    animal = layout.class_layouts["Animal"]
    nombre = result.symbols.global_scope.lookup("Animal").fields["nombre"]
    b = IRBuilder(layout)
    obj = b.new_temp(ClassType("Animal"))
    b.emit(Opcode.NEW_OBJ, obj, ClassRef("Animal"), fields=animal.size)
    b.emit(Opcode.ARG, arg1=obj)
    b.emit(Opcode.ARG, arg1=Const("Rex", STRING))
    b.emit(Opcode.CALL, None, Label(animal.constructor_label), argc=2)
    b.emit(Opcode.MOV, _global(result, layout, "a"), obj)
    b.release_temp(obj)
    said = b.new_temp(STRING)
    entry = animal.method_named("hablar")
    b.emit(Opcode.CALL_METHOD, said, _global(result, layout, "a"), MethodRef(entry.name, entry.slot), argc=0)
    b.emit(Opcode.PRINT, arg1=said)
    b.release_temp(said)

    b.begin_function(ctor)
    this = layout.ref_for(variable(result, "function:constructor", "this"), ctor)
    n = layout.ref_for(variable(result, "function:constructor", "n"), ctor)
    b.emit(Opcode.SET_FIELD, this, layout.ref_for(nombre, ctor), n)
    b.emit(Opcode.RETURN)
    b.end_function()

    b.begin_function(hablar)
    value = b.new_temp(STRING)
    b.emit(Opcode.GET_FIELD, value, layout.ref_for(variable(result, "function:hablar", "this"), hablar),
           layout.ref_for(nombre, hablar))
    b.emit(Opcode.RETURN, arg1=value)
    b.release_temp(value)
    b.end_function()
    return serialize(b.build())


def example_arreglo_y_try_catch():
    result, layout = layout_for(
        "let arr: integer[] = [1, 2];\n"
        "try { print(arr[5]); } catch (err) { print(err); }"
    )
    g = lambda name: _global(result, layout, name)  # noqa: E731
    b = IRBuilder(layout)
    array = b.new_temp(ArrayType(INTEGER))
    b.emit(Opcode.NEW_ARR, array, Const(2, INTEGER))
    b.emit(Opcode.ARR_SET, array, Const(0, INTEGER), Const(1, INTEGER))
    b.emit(Opcode.ARR_SET, array, Const(1, INTEGER), Const(2, INTEGER))
    b.emit(Opcode.MOV, g("arr"), array)
    b.release_temp(array)
    handler, end = b.new_label("try_handler"), b.new_label("try_end")
    b.emit(Opcode.TRY_BEGIN, arg1=handler)
    item = b.new_temp(INTEGER)
    b.emit(Opcode.ARR_GET, item, g("arr"), Const(5, INTEGER))
    b.emit(Opcode.PRINT, arg1=item)
    b.release_temp(item)
    b.emit(Opcode.TRY_END)
    b.emit(Opcode.GOTO, arg1=end)
    b.mark_label(handler)
    err = layout.ref_for(variable(result, "catch", "err"), None)
    b.emit(Opcode.CATCH, arg1=err)
    b.emit(Opcode.PRINT, arg1=err)
    b.mark_label(end)
    return serialize(b.build())


EXAMPLES = [
    example_aritmetica_y_reciclaje, example_cortocircuito, example_recursion,
    example_funcion_anidada, example_objetos, example_arreglo_y_try_catch,
]


@pytest.fixture(scope="module")
def doc_text():
    return DOC.read_text(encoding="utf-8")


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda f: f.__name__)
def test_ejemplo_del_documento_es_salida_real_del_builder(example, doc_text):
    text = example()
    assert text in doc_text, f"el ejemplo {example.__name__} no coincide con el documento:\n{text}"


def test_el_documento_explica_cada_opcode(doc_text):
    for opcode in Opcode:
        assert f"`{opcode.value}`" in doc_text, f"falta documentar {opcode.value}"
