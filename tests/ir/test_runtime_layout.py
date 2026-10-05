"""
tests de compiler/runtime/runtime_layout.py: slots globales, frames, static links,
labels, refs de almacenamiento y la regla de no generar nada con errores.
"""
import pytest

from compiler.runtime.runtime_layout import prepare, require_semantic_success
from compiler.runtime.storage import StorageKind, StorageRef

from .conftest import function_named, layout_for, semantic, variable

GLOBAL, LOCAL, PARAM, THIS, NONLOCAL, FIELD = (
    StorageKind.GLOBAL, StorageKind.LOCAL, StorageKind.PARAM, StorageKind.THIS,
    StorageKind.NONLOCAL, StorageKind.FIELD,
)


def frame(layout, label):
    return [(s.slot, s.name, s.kind) for s in layout.records[label].slots]


# ---------- con errores no hay layout ----------

def test_error_semantico_bloquea_el_layout():
    with pytest.raises(ValueError):
        prepare(semantic('let x: integer = "no";'))


def test_error_de_sintaxis_bloquea_el_layout():
    result = semantic("let x: integer = ;")
    assert result.ast is None
    with pytest.raises(ValueError):
        require_semantic_success(result)


def test_warnings_no_bloquean_el_layout():
    result = semantic("function f(): integer { return 1; print(2); }")
    assert [d.code for d in result.diagnostics] == ["CPS-117"]
    assert "fn::f" in prepare(result).records


# ---------- globales ----------

def test_globales_en_preorden_incluye_bloques_top_level():
    result, layout = layout_for(
        "let a: integer = 1; { let b: integer = 2; } "
        "for (let i: integer = 0; i < 1; i = i + 1) { let c: integer = 3; }"
    )
    assert layout.globals_count == 4
    slots = {name: variable(result, scope, name).slot for scope, name in
             [("global", "a"), ("block", "b"), ("loop", "i")]}
    assert slots == {"a": 0, "b": 1, "i": 2}
    assert variable(result, "global", "a").storage_kind is GLOBAL
    assert variable(result, "global", "a").owner is None


# ---------- frames ----------

def test_frame_params_primero_y_locales_en_preorden():
    _, layout = layout_for(
        "function f(a: integer, b: integer) {\n"
        "  let x: integer = 1;\n"
        "  if (a > b) { let y: integer = 2; } else { let z: integer = 3; }\n"
        "  foreach (n in [1, 2]) { print(n); }\n"
        '  try { let t: integer = 4; } catch (e) { print(e); }\n'
        "}"
    )
    assert frame(layout, "fn::f") == [
        (0, "a", PARAM), (1, "b", PARAM), (2, "x", LOCAL), (3, "y", LOCAL), (4, "z", LOCAL),
        (5, "n", LOCAL), (6, "t", LOCAL), (7, "e", LOCAL),
    ]
    assert layout.records["fn::f"].param_count == 2
    assert layout.records["fn::f"].frame_size == 8


def test_locales_de_una_anidada_no_entran_al_frame_de_afuera():
    _, layout = layout_for("function f() { let x: integer = 1; function g() { let y: integer = 2; } }")
    assert frame(layout, "fn::f") == [(0, "x", LOCAL)]
    assert frame(layout, "fn::f.g") == [(0, "y", LOCAL)]


def test_metodo_lleva_this_en_el_slot_cero():
    _, layout = layout_for("class A { function m(k: integer) { let v: integer = k; } }")
    assert frame(layout, "fn::A.m") == [(0, "this", THIS), (1, "k", PARAM), (2, "v", LOCAL)]
    assert layout.records["fn::A.m"].is_method is True
    assert layout.records["fn::A.m"].owner_class == "A"


def test_simbolos_quedan_escritos_en_la_tabla():
    result, layout = layout_for("function f(a: integer) { let x: integer = a; }")
    fn = function_named(layout, "fn::f")
    x = variable(result, "function:f", "x")
    assert fn.activation_record is layout.records["fn::f"]
    assert (x.storage_kind, x.slot, x.owner) == (LOCAL, 1, "fn::f")


# ---------- static link: solo cuando hay captura ----------

def test_anidada_sin_captura_no_tiene_static_link():
    _, layout = layout_for("let g: integer = 1; function f() { function h(n: integer): integer { return n + g; } }")
    record = layout.records["fn::f.h"]
    assert record.lexical_depth == 1
    assert record.static_link is False


def test_anidada_que_captura_tiene_static_link():
    _, layout = layout_for("function f(a: integer) { function h(): integer { return a; } }")
    assert layout.records["fn::f.h"].static_link is True
    assert layout.records["fn::f"].static_link is False


def test_this_desde_una_anidada_es_captura():
    _, layout = layout_for(
        "class A { let v: integer; function m(): integer { function h(): integer { return this.v; } return h(); } }"
    )
    assert layout.records["fn::A.m.h"].static_link is True


def test_captura_profunda_marca_toda_la_cadena():
    _, layout = layout_for(
        "function f() { let x: integer = 1; function g() { function h(): integer { return x; } } }"
    )
    assert layout.records["fn::f.g"].static_link is True
    assert layout.records["fn::f.g.h"].static_link is True
    assert layout.records["fn::f.g.h"].lexical_depth == 2


def test_hermana_que_llama_a_una_con_link_tambien_necesita_link():
    _, layout = layout_for(
        "function f() { let x: integer = 1;\n"
        "  function h(): integer { return x; }\n"
        "  function k(): integer { return h(); }\n"
        "}"
    )
    assert layout.records["fn::f.k"].static_link is True


def test_hermana_que_llama_a_una_sin_link_no_necesita_link():
    _, layout = layout_for(
        "function f() {\n"
        "  function h(n: integer): integer { return n; }\n"
        "  function k(): integer { return h(1); }\n"
        "}"
    )
    assert layout.records["fn::f.h"].static_link is False
    assert layout.records["fn::f.k"].static_link is False


# ---------- refs de almacenamiento ----------

def test_ref_local_param_y_global():
    result, layout = layout_for("let g: integer = 1; function f(a: integer) { let x: integer = a + g; }")
    f = function_named(layout, "fn::f")
    assert layout.ref_for(variable(result, "function:f", "x"), f) == StorageRef(LOCAL, 1, name="x")
    assert layout.ref_for(variable(result, "function:f", "a"), f) == StorageRef(PARAM, 0, name="a")
    assert layout.ref_for(variable(result, "global", "g"), f) == StorageRef(GLOBAL, 0, name="g")
    assert layout.ref_for(variable(result, "global", "g"), None) == StorageRef(GLOBAL, 0, name="g")


def test_ref_nonlocal_cuenta_los_saltos():
    result, layout = layout_for(
        "function f() { let x: integer = 1; function g() { function h(): integer { return x; } } }"
    )
    x = variable(result, "function:f", "x")
    assert layout.ref_for(x, function_named(layout, "fn::f.g")) == StorageRef(NONLOCAL, 0, 1, "x")
    assert layout.ref_for(x, function_named(layout, "fn::f.g.h")) == StorageRef(NONLOCAL, 0, 2, "x")


def test_ref_de_this_desde_una_anidada_es_nonlocal_slot_cero():
    result, layout = layout_for(
        "class A { let v: integer; function m(): integer { function h(): integer { return this.v; } return h(); } }"
    )
    this = variable(result, "function:m", "this")
    assert layout.ref_for(this, function_named(layout, "fn::A.m")) == StorageRef(THIS, 0, name="this")
    assert layout.ref_for(this, function_named(layout, "fn::A.m.h")) == StorageRef(NONLOCAL, 0, 1, "this")


def test_ref_de_campo():
    result, layout = layout_for("class A { let v: integer; let w: integer; }")
    w = result.symbols.global_scope.lookup("A").fields["w"]
    assert layout.ref_for(w, None) == StorageRef(FIELD, 1, name="w")


def test_ref_de_algo_sin_almacenamiento_se_rechaza():
    _, layout = layout_for("function f() {}")
    with pytest.raises(ValueError):
        layout.ref_for(function_named(layout, "fn::f"), None)


def test_variable_de_frame_desde_codigo_global_se_rechaza():
    result, layout = layout_for("function f() { let x: integer = 1; }")
    with pytest.raises(ValueError):
        layout.ref_for(variable(result, "function:f", "x"), None)


# ---------- static link en llamadas ----------

def test_link_hops_de_las_llamadas():
    _, layout = layout_for(
        "function f() { let x: integer = 1;\n"
        "  function h(): integer { return x; }\n"
        "  function k(): integer { return h(); }\n"
        "  function p(n: integer): integer { return n; }\n"
        "  h();\n"
        "}"
    )
    f, h, k, p = (function_named(layout, label) for label in ("fn::f", "fn::f.h", "fn::f.k", "fn::f.p"))
    assert layout.link_hops(f, h) == 0   # el padre pasa su propio frame
    assert layout.link_hops(k, h) == 1   # la hermana sube uno para encontrarlo
    assert layout.link_hops(h, h) == 1   # recursion: pasa su propio static link
    assert layout.link_hops(f, p) is None
    assert layout.enclosing_function(h) is f


# ---------- labels ----------

def test_labels_de_funciones_metodos_y_constructores():
    _, layout = layout_for(
        "function f() { function g() {} }\n"
        "class A { function constructor() {} function m() { function h() {} } }"
    )
    assert set(layout.records) == {"fn::f", "fn::f.g", "fn::A.constructor", "fn::A.m", "fn::A.m.h"}


def test_anidadas_homonimas_en_bloques_hermanos_no_chocan():
    _, layout = layout_for("function f() { { function g() {} } { function g() {} } }")
    assert {"fn::f.g", "fn::f.g#2"} <= set(layout.records)


# ---------- determinismo ----------

SOURCE = (
    "let g: integer = 1;\n"
    "function f(a: integer): integer { let x: integer = a; function h(): integer { return x + g; } return h(); }\n"
    "class A { let v: integer; function m(): integer { return this.v; } }\n"
    "class B : A { function m(): integer { return 2; } }\n"
)


def _snapshot(layout):
    return (layout.globals_count, dict(layout.records), dict(layout.class_layouts))


def test_mismo_programa_da_el_mismo_layout():
    _, first = layout_for(SOURCE)
    _, second = layout_for(SOURCE)
    assert _snapshot(first) == _snapshot(second)


def test_preparar_dos_veces_el_mismo_resultado_es_idempotente():
    result, first = layout_for(SOURCE)
    second = prepare(result)
    assert _snapshot(first) == _snapshot(second)
    assert first.labels is not second.labels  # cada compilacion trae su propio LabelManager
