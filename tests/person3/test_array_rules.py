"""tests de compiler/array_rules.py: funciones puras, sin ast ni scopes."""
from compiler.array_rules import check_array_literal, check_index_access, is_valid_index_type
from compiler.types import ArrayType, ClassType, EMPTY_ARRAY, ERROR, INTEGER, NULL, STRING


class _FakeHierarchy:
    """Perro y Gato heredan de Animal, igual que tests/frontend/test_types.py."""
    _edges = {("Perro", "Animal"), ("Gato", "Animal")}

    def is_subclass(self, sub_name: str, super_name: str) -> bool:
        if sub_name == super_name:
            return True
        return (sub_name, super_name) in self._edges


# ---------- check_array_literal ----------

def test_literal_vacio_da_empty_array():
    result, code = check_array_literal([])
    assert result is EMPTY_ARRAY
    assert code is None


def test_literal_homogeneo_da_array_de_ese_tipo():
    result, code = check_array_literal([INTEGER, INTEGER, INTEGER])
    assert result == ArrayType(INTEGER)
    assert code is None


def test_literal_heterogeneo_sin_tipo_comun_reporta_cps207():
    result, code = check_array_literal([INTEGER, STRING])
    assert code == "CPS-207"
    assert result == ERROR


def test_literal_con_null_y_clase_da_array_de_esa_clase():
    result, code = check_array_literal([NULL, ClassType("Animal")])
    assert result == ArrayType(ClassType("Animal"))
    assert code is None


def test_literal_con_subclase_y_padre_da_array_del_padre():
    # common_type solo resuelve el ancestro comun cuando uno es antepasado directo del
    # otro (types._closest_common_ancestor); dos hermanas sin relacion entre si, como
    # Perro y Gato, no tienen ancestro comun resoluble desde types.py (limitacion
    # documentada ahi mismo) y caen en CPS-207 -- se prueba aparte, mas abajo.
    hierarchy = _FakeHierarchy()
    result, code = check_array_literal([ClassType("Perro"), ClassType("Animal")], hierarchy)
    assert result == ArrayType(ClassType("Animal"))
    assert code is None


def test_literal_con_clases_hermanas_sin_ancestro_directo_reporta_cps207():
    hierarchy = _FakeHierarchy()
    result, code = check_array_literal([ClassType("Perro"), ClassType("Gato")], hierarchy)
    assert code == "CPS-207"


def test_literal_con_elemento_error_no_cascadea():
    result, code = check_array_literal([INTEGER, ERROR])
    assert code is None
    assert result == ERROR


def test_literal_anidado_homogeneo():
    result, code = check_array_literal([ArrayType(INTEGER), ArrayType(INTEGER)])
    assert result == ArrayType(ArrayType(INTEGER))
    assert code is None


def test_literal_anidado_con_arrays_de_distinto_tipo_reporta_cps207():
    # los arrays son invariantes: ArrayType(integer) y ArrayType(string) no tienen join
    result, code = check_array_literal([ArrayType(INTEGER), ArrayType(STRING)])
    assert code == "CPS-207"


# ---------- check_index_access ----------

def test_indexar_un_array_da_el_tipo_del_elemento():
    result, code = check_index_access(ArrayType(STRING))
    assert result == STRING
    assert code is None


def test_indexar_un_array_vacio_da_error_silencioso():
    result, code = check_index_access(EMPTY_ARRAY)
    assert code is None
    assert result == ERROR


def test_indexar_algo_que_no_es_array_reporta_cps206():
    result, code = check_index_access(INTEGER)
    assert code == "CPS-206"
    assert result == ERROR


def test_indexar_con_coleccion_error_no_cascadea():
    result, code = check_index_access(ERROR)
    assert code is None
    assert result == ERROR


# ---------- is_valid_index_type ----------

def test_indice_integer_es_valido():
    assert is_valid_index_type(INTEGER) is True


def test_indice_string_es_invalido():
    assert is_valid_index_type(STRING) is False


def test_indice_error_se_considera_valido_para_no_cascadear():
    assert is_valid_index_type(ERROR) is True
