"""
tests de compiler/ir/temp_manager.py: reciclaje real, nunca un temporal vivo entregado
dos veces, doble liberacion detectada, pico registrado y unidades independientes.
"""
import pytest

from compiler.ir.model import Temp
from compiler.ir.temp_manager import TempError, TempManager, temp_category
from compiler.types import BOOLEAN, ERROR, INTEGER, NULL, STRING, VOID, ArrayType, ClassType, EMPTY_ARRAY


def test_reciclaje_real_en_una_secuencia_de_expresiones():
    temps = TempManager()
    # a = b * c + d  ->  t0, t1;  despues e = f * g reusa t0 y t1
    t0 = temps.acquire(INTEGER)
    t1 = temps.acquire(INTEGER)
    temps.release(t0)
    temps.release(t1)
    again = [temps.acquire(INTEGER), temps.acquire(INTEGER)]
    assert [t.name for t in again] == ["t0", "t1"]
    assert temps.created == 2


def test_nunca_entrega_un_temporal_vivo():
    temps = TempManager()
    live = temps.acquire(INTEGER)
    other = temps.acquire(INTEGER)
    assert other.index != live.index


def test_reusa_el_indice_libre_mas_bajo():
    temps = TempManager()
    ts = [temps.acquire(INTEGER) for _ in range(3)]
    temps.release(ts[2])
    temps.release(ts[0])
    assert temps.acquire(INTEGER).name == "t0"
    assert temps.acquire(INTEGER).name == "t2"


def test_pool_por_categoria_no_mezcla_int_con_bool():
    temps = TempManager()
    temps.release(temps.acquire(INTEGER))
    assert temps.acquire(BOOLEAN).name == "t1"
    assert temps.acquire(INTEGER).name == "t0"


def test_referencias_comparten_pool_aunque_sean_de_tipos_distintos():
    temps = TempManager()
    temps.release(temps.acquire(ClassType("A")))
    assert temps.acquire(ArrayType(INTEGER)).name == "t0"


def test_doble_liberacion_se_detecta():
    temps = TempManager()
    t = temps.acquire(INTEGER)
    temps.release(t)
    with pytest.raises(TempError):
        temps.release(t)


def test_liberar_un_temporal_ajeno_se_detecta():
    with pytest.raises(TempError):
        TempManager().release(Temp(4, INTEGER))


def test_pico_de_temporales_vivos():
    temps = TempManager()
    a, b = temps.acquire(INTEGER), temps.acquire(INTEGER)
    temps.release(a)
    temps.release(b)
    temps.acquire(INTEGER)
    assert temps.peak == 2
    assert temps.live_count == 1
    assert temps.is_live(Temp(0, INTEGER))


def test_dos_unidades_no_comparten_estado():
    first, second = TempManager(unit=0), TempManager(unit=1)
    first.acquire(INTEGER)
    first.acquire(INTEGER)
    assert second.acquire(INTEGER).name == "t0"
    assert second.peak == 1


def test_el_t0_de_una_unidad_no_es_el_t0_de_otra():
    first, second = TempManager(unit=0), TempManager(unit=1)
    t = first.acquire(INTEGER)
    assert second.acquire(INTEGER) != t
    assert not second.is_live(t)
    with pytest.raises(TempError):
        second.release(t)


@pytest.mark.parametrize("type_,category", [
    (INTEGER, "int"), (BOOLEAN, "bool"), (STRING, "string"), (ClassType("A"), "ref"),
    (ArrayType(STRING), "ref"), (EMPTY_ARRAY, "ref"), (NULL, "ref"),
])
def test_categorias(type_, category):
    assert temp_category(type_) == category


@pytest.mark.parametrize("type_", [VOID, ERROR, None])
def test_tipos_sin_temporales(type_):
    with pytest.raises(TempError):
        TempManager().acquire(type_)
