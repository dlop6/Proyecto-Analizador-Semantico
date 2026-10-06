"""
tests de los layouts de clase que arma runtime_layout.prepare: herencia de campos,
tabla de despacho, override y constructores.
"""
from compiler.runtime.storage import StorageKind

from .conftest import layout_for


def fields(layout, cls):
    return [(f.slot, f.name, f.owner_class) for f in layout.class_layouts[cls].fields]


def methods(layout, cls):
    return [(m.slot, m.name, m.impl_label) for m in layout.class_layouts[cls].methods]


HIERARCHY = (
    "class Animal { let nombre: string; function hablar(): string { return \"...\"; } function comer() {} }\n"
    "class Perro : Animal { let raza: string; function hablar(): string { return \"guau\"; } function ladrar() {} }\n"
    "class Cachorro : Perro { let edad: integer; function comer() {} }\n"
)


def test_campos_heredados_primero_y_propios_despues():
    _, layout = layout_for(HIERARCHY)
    assert fields(layout, "Perro") == [(0, "nombre", "Animal"), (1, "raza", "Perro")]
    assert fields(layout, "Cachorro") == [(0, "nombre", "Animal"), (1, "raza", "Perro"), (2, "edad", "Cachorro")]


def test_override_reusa_el_slot_y_lo_heredado_conserva_la_implementacion_del_padre():
    _, layout = layout_for(HIERARCHY)
    assert methods(layout, "Animal") == [(0, "hablar", "fn::Animal.hablar"), (1, "comer", "fn::Animal.comer")]
    assert methods(layout, "Perro") == [
        (0, "hablar", "fn::Perro.hablar"), (1, "comer", "fn::Animal.comer"), (2, "ladrar", "fn::Perro.ladrar"),
    ]
    assert methods(layout, "Cachorro") == [
        (0, "hablar", "fn::Perro.hablar"), (1, "comer", "fn::Cachorro.comer"), (2, "ladrar", "fn::Perro.ladrar"),
    ]


def test_method_slot_queda_escrito_en_el_simbolo():
    result, _ = layout_for(HIERARCHY)
    perro = result.symbols.global_scope.lookup("Perro")
    assert perro.methods["hablar"].method_slot == 0
    assert perro.methods["ladrar"].method_slot == 2


def test_clase_declarada_antes_que_su_padre():
    _, layout = layout_for("class B : A { let y: integer; } class A { let x: integer; }")
    assert fields(layout, "B") == [(0, "x", "A"), (1, "y", "B")]
    assert layout.class_layouts["B"].parent_name == "A"


def test_campo_que_oculta_uno_heredado_recibe_slot_nuevo():
    result, layout = layout_for("class A { let x: integer; } class B : A { let x: string; }")
    assert [d.code for d in result.diagnostics] == ["CPS-033"]  # warning, no bloquea
    assert fields(layout, "B") == [(0, "x", "A"), (1, "x", "B")]
    assert layout.class_layouts["B"].field_named("x").owner_class == "B"


def test_constructor_no_entra_a_la_tabla_de_despacho_y_se_hereda_si_falta():
    result, layout = layout_for(
        "class A { function constructor(n: integer) {} function m() {} } class B : A { function k() {} }"
    )
    a = result.symbols.global_scope.lookup("A")
    assert layout.class_layouts["A"].constructor_label == "fn::A.constructor"
    assert a.constructor.method_slot is None
    assert [m.name for m in layout.class_layouts["A"].methods] == ["m"]
    # B no declara constructor: usa el de A (ancestro mas cercano)
    assert layout.class_layouts["B"].constructor_label == "fn::A.constructor"
    assert [m.name for m in layout.class_layouts["B"].methods] == ["m", "k"]


def test_sin_constructor_en_toda_la_cadena_no_hay_etiqueta():
    _, layout = layout_for("class A { function m() {} } class B : A {}")
    assert layout.class_layouts["A"].constructor_label is None
    assert layout.class_layouts["B"].constructor_label is None


def test_constructor_propio_tiene_prioridad_sobre_el_heredado():
    _, layout = layout_for(
        "class A { function constructor() {} } class B : A {} class C : B { function constructor() {} }"
    )
    assert layout.class_layouts["B"].constructor_label == "fn::A.constructor"
    assert layout.class_layouts["C"].constructor_label == "fn::C.constructor"


def test_campos_quedan_como_field_con_su_clase():
    result, layout = layout_for("class A { let x: integer; } class B : A { let y: integer; }")
    y = result.symbols.global_scope.lookup("B").fields["y"]
    assert (y.storage_kind, y.slot, y.owner) == (StorageKind.FIELD, 1, "B")
    assert result.symbols.global_scope.lookup("B").layout is layout.class_layouts["B"]
