"""
tests de compiler/types.py: las 4 funciones que exige el pdf (same_type, is_assignable,
numeric_result, common_type) mas las invariantes que deben cumplirse entre ellas.
"""
import pytest

from compiler.types import (
    INTEGER, STRING, BOOLEAN, NULL, ERROR, VOID, EMPTY_ARRAY,
    ArrayType, ClassType, PrimitiveType,
    same_type, is_assignable, numeric_result, common_type,
)


class _FakeHierarchy:
    """jerarquia minima para tests: Perro y Gato heredan de Animal."""
    _edges = {("Perro", "Animal"), ("Gato", "Animal")}

    def is_subclass(self, sub_name: str, super_name: str) -> bool:
        if sub_name == super_name:
            return True
        return (sub_name, super_name) in self._edges


@pytest.fixture
def hierarchy():
    return _FakeHierarchy()


# ---------- same_type ----------

def test_same_type_reflexiva_y_simetrica():
    assert same_type(INTEGER, INTEGER)
    assert same_type(STRING, STRING) and same_type(STRING, STRING)


def test_same_type_primitivos_distintos():
    assert not same_type(INTEGER, STRING)
    assert not same_type(BOOLEAN, INTEGER)


def test_same_type_arrays_anidados():
    assert same_type(ArrayType(ArrayType(INTEGER)), ArrayType(ArrayType(INTEGER)))
    assert not same_type(ArrayType(INTEGER), ArrayType(STRING))


def test_same_type_class_por_nombre():
    assert same_type(ClassType("Animal"), ClassType("Animal"))
    assert not same_type(ClassType("Animal"), ClassType("Perro"))


# ---------- is_assignable ----------

def test_is_assignable_identidad():
    assert is_assignable(INTEGER, INTEGER)
    assert is_assignable(ArrayType(STRING), ArrayType(STRING))


def test_is_assignable_null_a_referencia_si_a_primitivo_no():
    assert is_assignable(ClassType("Animal"), NULL)
    assert is_assignable(ArrayType(INTEGER), NULL)
    assert not is_assignable(INTEGER, NULL)
    assert not is_assignable(BOOLEAN, NULL)
    assert not is_assignable(STRING, NULL)


def test_is_assignable_subtipado_con_jerarquia(hierarchy):
    assert is_assignable(ClassType("Animal"), ClassType("Perro"), hierarchy)
    assert not is_assignable(ClassType("Perro"), ClassType("Animal"), hierarchy)  # rechaza padre->subclase
    assert not is_assignable(ClassType("Perro"), ClassType("Gato"), hierarchy)


def test_is_assignable_sin_jerarquia_solo_vale_igualdad():
    assert not is_assignable(ClassType("Animal"), ClassType("Perro"))  # sin hierarchy no hay subtipado


def test_is_assignable_arrays_son_invariantes(hierarchy):
    # Array[Perro] NO es asignable a Array[Animal], aunque Perro sea subclase de Animal
    assert not is_assignable(ArrayType(ClassType("Animal")), ArrayType(ClassType("Perro")), hierarchy)


def test_is_assignable_empty_array_a_cualquier_array():
    assert is_assignable(ArrayType(INTEGER), EMPTY_ARRAY)
    assert is_assignable(ArrayType(ClassType("Animal")), EMPTY_ARRAY)


def test_is_assignable_absorbe_error_type():
    assert is_assignable(ERROR, INTEGER)
    assert is_assignable(INTEGER, ERROR)


# ---------- numeric_result ----------

def test_numeric_result_integer_integer():
    assert numeric_result(INTEGER, INTEGER) is INTEGER


def test_numeric_result_no_numerico_da_none():
    assert numeric_result(INTEGER, STRING) is None
    assert numeric_result(BOOLEAN, BOOLEAN) is None
    assert numeric_result(STRING, STRING) is None  # concatenacion no es cosa de numeric_result


def test_numeric_result_absorbe_error():
    assert numeric_result(ERROR, INTEGER) == ERROR
    assert numeric_result(INTEGER, ERROR) == ERROR


def test_numeric_result_documenta_que_no_hay_float():
    # no existe PrimitiveType("float") en el modulo -> si alguien lo agrega sin querer, esto avisa
    from compiler import types as types_mod
    assert not hasattr(types_mod, "FLOAT")


# ---------- common_type ----------

def test_common_type_iguales_retorna_el_mismo():
    assert common_type(INTEGER, INTEGER) is INTEGER


def test_common_type_null_con_clase():
    assert common_type(NULL, ClassType("Animal")) == ClassType("Animal")
    assert common_type(ClassType("Animal"), NULL) == ClassType("Animal")


def test_common_type_ancestro_comun(hierarchy):
    assert common_type(ClassType("Perro"), ClassType("Animal"), hierarchy) == ClassType("Animal")


def test_common_type_sin_relacion_da_none():
    assert common_type(INTEGER, STRING) is None
    assert common_type(BOOLEAN, ClassType("Animal")) is None


def test_common_type_empty_array_con_array():
    assert common_type(EMPTY_ARRAY, ArrayType(INTEGER)) == ArrayType(INTEGER)
    assert common_type(ArrayType(INTEGER), EMPTY_ARRAY) == ArrayType(INTEGER)


def test_str_de_tipos_es_estable():
    assert str(INTEGER) == "integer"
    assert str(ArrayType(ArrayType(INTEGER))) == "integer[][]"
    assert str(ClassType("Animal")) == "Animal"
    assert str(NULL) == "null"


# ---------- invariantes (property tests con lista enumerada, sin agregar hypothesis) ----------

_TIPOS = [INTEGER, STRING, BOOLEAN, NULL, ERROR, VOID, EMPTY_ARRAY,
          ArrayType(INTEGER), ArrayType(STRING), ClassType("Animal"), ClassType("Perro")]


@pytest.mark.parametrize("a", _TIPOS)
@pytest.mark.parametrize("b", _TIPOS)
def test_invariante_same_type_implica_is_assignable_ambos_lados(a, b, hierarchy):
    if same_type(a, b):
        assert is_assignable(a, b, hierarchy)
        assert is_assignable(b, a, hierarchy)


@pytest.mark.parametrize("a", _TIPOS)
@pytest.mark.parametrize("b", _TIPOS)
def test_invariante_common_type_es_supertipo_de_ambos(a, b, hierarchy):
    c = common_type(a, b, hierarchy)
    if c is not None:
        assert is_assignable(c, a, hierarchy)
        assert is_assignable(c, b, hierarchy)


@pytest.mark.parametrize("a", _TIPOS)
@pytest.mark.parametrize("b", _TIPOS)
def test_invariante_numeric_result_implica_operandos_numericos(a, b):
    nr = numeric_result(a, b)
    if nr is not None and nr != ERROR:
        assert a is INTEGER and b is INTEGER
