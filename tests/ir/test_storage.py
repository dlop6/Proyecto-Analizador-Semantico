"""tests de compiler/runtime/storage.py: StorageRef valida su propia forma."""
import pytest

from compiler.runtime.storage import FRAME_KINDS, StorageKind, StorageRef


def test_storage_ref_valido_por_cada_tipo():
    assert StorageRef(StorageKind.GLOBAL, 0, name="x").lexical_depth == 0
    assert StorageRef(StorageKind.LOCAL, 3, name="y").slot == 3
    assert StorageRef(StorageKind.NONLOCAL, 2, lexical_depth=1, name="z").lexical_depth == 1


def test_storage_ref_es_inmutable_y_comparable():
    a = StorageRef(StorageKind.PARAM, 1, name="n")
    assert a == StorageRef(StorageKind.PARAM, 1, name="n")
    with pytest.raises(AttributeError):
        a.slot = 2  # type: ignore[misc]


@pytest.mark.parametrize("slot", [-1, 1.5, True, "0"])
def test_slot_invalido_se_rechaza(slot):
    with pytest.raises(ValueError):
        StorageRef(StorageKind.LOCAL, slot, name="x")  # type: ignore[arg-type]


def test_nonlocal_tiene_que_subir_al_menos_un_frame():
    with pytest.raises(ValueError):
        StorageRef(StorageKind.NONLOCAL, 0, lexical_depth=0, name="x")


def test_profundidad_solo_aplica_a_nonlocal():
    with pytest.raises(ValueError):
        StorageRef(StorageKind.LOCAL, 0, lexical_depth=1, name="x")


def test_sin_nombre_se_rechaza():
    with pytest.raises(ValueError):
        StorageRef(StorageKind.GLOBAL, 0)


def test_frame_kinds_son_this_param_y_local():
    assert FRAME_KINDS == {StorageKind.THIS, StorageKind.PARAM, StorageKind.LOCAL}
