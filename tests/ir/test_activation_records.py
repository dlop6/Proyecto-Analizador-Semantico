"""tests de compiler/runtime/activation_records.py: invariantes de frames y layouts."""
import pytest

from compiler.runtime.activation_records import (
    ActivationRecord, ClassLayout, FieldEntry, FrameSlot, MethodEntry,
)
from compiler.runtime.storage import StorageKind

THIS, PARAM, LOCAL = StorageKind.THIS, StorageKind.PARAM, StorageKind.LOCAL


def record(slots, *, is_method=False, depth=0, link=False):
    return ActivationRecord(
        label="fn::f", lexical_depth=depth, static_link=link, is_method=is_method,
        owner_class="C" if is_method else None, slots=tuple(slots),
    )


# ---------- ActivationRecord ----------

def test_frame_de_metodo_this_params_y_locales():
    ar = record([FrameSlot(0, "this", THIS), FrameSlot(1, "a", PARAM), FrameSlot(2, "x", LOCAL)], is_method=True)
    assert ar.param_count == 1
    assert ar.frame_size == 3


def test_frame_vacio_de_funcion_es_valido():
    assert record([]).frame_size == 0


def test_slots_con_huecos_se_rechazan():
    with pytest.raises(ValueError):
        record([FrameSlot(0, "a", PARAM), FrameSlot(2, "x", LOCAL)])


def test_local_antes_que_param_se_rechaza():
    with pytest.raises(ValueError):
        record([FrameSlot(0, "x", LOCAL), FrameSlot(1, "a", PARAM)])


def test_metodo_sin_this_se_rechaza():
    with pytest.raises(ValueError):
        record([FrameSlot(0, "a", PARAM)], is_method=True)


def test_funcion_con_this_se_rechaza():
    with pytest.raises(ValueError):
        record([FrameSlot(0, "this", THIS)], is_method=False)


def test_static_link_sin_funcion_que_la_encierre_se_rechaza():
    with pytest.raises(ValueError):
        record([], depth=0, link=True)


def test_static_link_en_funcion_anidada_es_valido():
    assert record([], depth=1, link=True).static_link is True


def test_kind_que_no_es_de_frame_se_rechaza():
    with pytest.raises(ValueError):
        record([FrameSlot(0, "g", StorageKind.GLOBAL)])


# ---------- ClassLayout ----------

def layout(fields, methods):
    return ClassLayout(class_name="Perro", parent_name="Animal", fields=tuple(fields),
                       methods=tuple(methods), constructor_label=None)


def test_campo_ocultado_resuelve_al_mas_derivado():
    lay = layout(
        [FieldEntry(0, "x", "Animal"), FieldEntry(1, "x", "Perro")],
        [MethodEntry("hablar", 0, "fn::Perro.hablar", "Perro")],
    )
    assert lay.field_named("x").owner_class == "Perro"
    assert lay.field_named("nada") is None
    assert lay.size == 2


def test_tabla_de_despacho_por_nombre_y_por_slot():
    lay = layout([], [MethodEntry("a", 0, "fn::Animal.a", "Animal"), MethodEntry("b", 1, "fn::Perro.b", "Perro")])
    assert lay.method_named("b").slot == 1
    assert lay.method_at(0).impl_label == "fn::Animal.a"
    assert lay.method_named("zzz") is None


def test_slots_de_campos_con_huecos_se_rechazan():
    with pytest.raises(ValueError):
        layout([FieldEntry(1, "x", "Perro")], [])


def test_metodo_repetido_en_la_tabla_se_rechaza():
    with pytest.raises(ValueError):
        layout([], [MethodEntry("a", 0, "fn::X.a", "X"), MethodEntry("a", 1, "fn::Y.a", "Y")])
