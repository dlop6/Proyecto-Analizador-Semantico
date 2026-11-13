"""contratos de datos: offsets de campos, tamaño de objeto y orden de vtable salen de ClassLayout."""
import pytest

from compiler.backend.mips.abi import field_offset, object_size, vtable_entries
from compiler.backend.mips.operands import mangle_label

from .pipeline import ir_for

SOURCE = """
class Animal {
    let name: string;
    let edad: integer;
    function constructor(name: string) { this.name = name; }
    function hablar(): string { return this.name; }
    function comer(): integer { return 1; }
}
class Perro : Animal {
    let raza: string;
    function hablar(): string { return "guau"; }
    function ladrar(): integer { return 2; }
}
class Vacia {}
"""


@pytest.fixture(scope="module")
def layouts():
    _, layout = ir_for(SOURCE)
    return layout.class_layouts


def test_campos_heredados_primero_y_con_offsets_contiguos(layouts):
    perro = layouts["Perro"]
    assert [f.name for f in perro.fields] == ["name", "edad", "raza"]
    assert [field_offset(f.slot) for f in perro.fields] == [4, 8, 12]


def test_tamaño_de_objeto_incluye_la_palabra_de_la_vtable(layouts):
    assert object_size(layouts["Animal"].size) == 12
    assert object_size(layouts["Perro"].size) == 16
    assert object_size(layouts["Vacia"].size) == 4


def test_override_conserva_el_slot_del_padre_y_apunta_a_la_implementacion_del_hijo(layouts):
    animal, perro = vtable_entries(layouts["Animal"]), vtable_entries(layouts["Perro"])
    hablar = layouts["Animal"].method_named("hablar").slot
    assert animal[hablar] == "fn_Animal_dhablar"
    assert perro[hablar] == "fn_Perro_dhablar"
    assert layouts["Perro"].method_named("hablar").slot == hablar


def test_metodo_heredado_sin_override_apunta_al_del_ancestro(layouts):
    comer = layouts["Animal"].method_named("comer").slot
    assert vtable_entries(layouts["Perro"])[comer] == "fn_Animal_dcomer"


def test_metodos_nuevos_van_despues_y_el_orden_es_el_de_slot(layouts):
    perro = layouts["Perro"]
    entries = vtable_entries(perro)
    assert len(entries) == len(perro.methods)
    assert entries == tuple(mangle_label(m.impl_label) for m in sorted(perro.methods, key=lambda m: m.slot))
    assert perro.method_named("ladrar").slot == len(layouts["Animal"].methods)


def test_el_constructor_no_esta_en_la_vtable_y_el_heredado_sale_de_constructor_label(layouts):
    assert not any("constructor" in label for label in vtable_entries(layouts["Perro"]))
    assert layouts["Perro"].constructor_label == layouts["Animal"].constructor_label == "fn::Animal.constructor"
    assert layouts["Vacia"].constructor_label is None


def test_clase_sin_metodos_tiene_vtable_vacia(layouts):
    assert vtable_entries(layouts["Vacia"]) == ()
