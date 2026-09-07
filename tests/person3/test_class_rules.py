"""tests de compiler/class_rules.py: funciones puras, sin ast ni scopes."""
from compiler.class_rules import check_method_call, check_new_call, check_override, check_property_access
from compiler.symbols import ClassSymbol, FunctionSymbol, VariableSymbol
from compiler.types import ClassType, ERROR, INTEGER, STRING


class _FakeHierarchy:
    """Perro hereda de Animal, igual que tests/frontend/test_types.py."""
    _edges = {("Perro", "Animal")}

    def is_subclass(self, sub_name: str, super_name: str) -> bool:
        if sub_name == super_name:
            return True
        return (sub_name, super_name) in self._edges


def _field(name, type_):
    return VariableSymbol(name=name, line=1, column=1, type=type_, is_field=True)


def _method(name, params=None, return_type=None):
    return FunctionSymbol(name=name, line=1, column=1, params=params or [], return_type=return_type, is_method=True)


def _param(name, type_):
    return VariableSymbol(name=name, line=1, column=1, type=type_, is_param=True, initialized=True)


def _class(name, fields=None, methods=None, constructor=None, parent=None):
    cls = ClassSymbol(name=name, line=1, column=1, type=ClassType(name), parent=parent)
    for f in fields or []:
        cls.fields[f.name] = f
    for m in methods or []:
        cls.methods[m.name] = m
    if constructor is not None:
        cls.methods["constructor"] = constructor
        cls.constructor = constructor
    return cls


# ---------- check_property_access ----------

def test_acceso_a_atributo_existente_da_su_tipo():
    animal = _class("Animal", fields=[_field("name", STRING)])
    result, code, detail = check_property_access(ClassType("Animal"), "name", {"Animal": animal})
    assert result == STRING
    assert code is None


def test_acceso_a_atributo_heredado():
    animal = _class("Animal", fields=[_field("name", STRING)])
    perro = _class("Perro", parent=animal)
    result, code, detail = check_property_access(ClassType("Perro"), "name", {"Animal": animal, "Perro": perro})
    assert result == STRING
    assert code is None


def test_acceso_a_miembro_inexistente_reporta_cps200():
    animal = _class("Animal")
    result, code, detail = check_property_access(ClassType("Animal"), "edad", {"Animal": animal})
    assert code == "CPS-200"
    assert result == ERROR


def test_acceso_a_metodo_sin_invocarlo_reporta_cps215():
    animal = _class("Animal", methods=[_method("hablar", return_type=STRING)])
    result, code, detail = check_property_access(ClassType("Animal"), "hablar", {"Animal": animal})
    assert code == "CPS-215"
    assert result == ERROR


def test_acceso_sobre_algo_que_no_es_objeto_reporta_cps208():
    result, code, detail = check_property_access(INTEGER, "x", {})
    assert code == "CPS-208"


def test_error_en_el_objeto_no_cascadea():
    result, code, detail = check_property_access(ERROR, "x", {})
    assert code is None
    assert result == ERROR


# ---------- check_method_call ----------

def test_llamada_a_metodo_con_aridad_y_tipos_correctos():
    animal = _class("Animal", methods=[_method("hablar", params=[_param("n", INTEGER)], return_type=STRING)])
    result, code, detail = check_method_call(ClassType("Animal"), "hablar", [INTEGER], {"Animal": animal})
    assert result == STRING
    assert code is None


def test_llamada_a_metodo_con_aridad_incorrecta_reporta_cps212():
    animal = _class("Animal", methods=[_method("hablar", params=[_param("n", INTEGER)], return_type=STRING)])
    result, code, detail = check_method_call(ClassType("Animal"), "hablar", [], {"Animal": animal})
    assert code == "CPS-212"


def test_llamada_a_metodo_con_tipo_de_argumento_incompatible_reporta_cps213():
    animal = _class("Animal", methods=[_method("hablar", params=[_param("n", INTEGER)], return_type=STRING)])
    result, code, detail = check_method_call(ClassType("Animal"), "hablar", [STRING], {"Animal": animal})
    assert code == "CPS-213"


def test_llamada_a_metodo_heredado():
    animal = _class("Animal", methods=[_method("hablar", return_type=STRING)])
    perro = _class("Perro", parent=animal)
    result, code, detail = check_method_call(ClassType("Perro"), "hablar", [], {"Animal": animal, "Perro": perro})
    assert result == STRING
    assert code is None


def test_llamar_un_campo_como_metodo_reporta_cps201():
    animal = _class("Animal", fields=[_field("name", STRING)])
    result, code, detail = check_method_call(ClassType("Animal"), "name", [], {"Animal": animal})
    assert code == "CPS-201"


def test_llamada_a_metodo_inexistente_reporta_cps200():
    animal = _class("Animal")
    result, code, detail = check_method_call(ClassType("Animal"), "volar", [], {"Animal": animal})
    assert code == "CPS-200"


# ---------- check_new_call ----------

def test_new_sin_constructor_y_sin_argumentos_es_valido():
    animal = _class("Animal")
    result, code, detail = check_new_call("Animal", animal, [])
    assert result == ClassType("Animal")
    assert code is None


def test_new_sin_constructor_con_argumentos_reporta_cps210():
    animal = _class("Animal")
    result, code, detail = check_new_call("Animal", animal, [INTEGER])
    assert code == "CPS-210"
    assert result == ClassType("Animal")  # el tipo resultante sigue siendo la clase


def test_new_con_constructor_aridad_incorrecta_reporta_cps210():
    ctor = _method("constructor", params=[_param("n", STRING)])
    animal = _class("Animal", constructor=ctor)
    result, code, detail = check_new_call("Animal", animal, [])
    assert code == "CPS-210"


def test_new_con_constructor_tipo_incompatible_reporta_cps211():
    ctor = _method("constructor", params=[_param("n", STRING)])
    animal = _class("Animal", constructor=ctor)
    result, code, detail = check_new_call("Animal", animal, [INTEGER])
    assert code == "CPS-211"


def test_new_con_constructor_valido():
    ctor = _method("constructor", params=[_param("n", STRING)])
    animal = _class("Animal", constructor=ctor)
    result, code, detail = check_new_call("Animal", animal, [STRING])
    assert result == ClassType("Animal")
    assert code is None


def test_new_de_clase_no_declarada_da_error_silencioso():
    result, code, detail = check_new_call("Fantasma", None, [])
    assert code is None
    assert result == ERROR


def test_new_subclase_como_argumento_de_constructor_de_la_padre():
    hierarchy = _FakeHierarchy()
    ctor = _method("constructor", params=[_param("a", ClassType("Animal"))])
    contenedor = _class("Contenedor", constructor=ctor)
    result, code, detail = check_new_call("Contenedor", contenedor, [ClassType("Perro")], hierarchy)
    assert code is None


# ---------- check_override ----------

def test_override_con_firma_identica_es_valido():
    parent = _method("hablar", params=[_param("n", INTEGER)], return_type=STRING)
    sub = _method("hablar", params=[_param("n", INTEGER)], return_type=STRING)
    assert check_override(sub, parent) is None


def test_override_con_distinta_aridad_reporta_cps202():
    parent = _method("hablar", params=[_param("n", INTEGER)], return_type=STRING)
    sub = _method("hablar", params=[], return_type=STRING)
    assert check_override(sub, parent) == "CPS-202"


def test_override_con_distinto_tipo_de_parametro_reporta_cps202():
    parent = _method("hablar", params=[_param("n", INTEGER)], return_type=STRING)
    sub = _method("hablar", params=[_param("n", STRING)], return_type=STRING)
    assert check_override(sub, parent) == "CPS-202"


def test_override_con_distinto_tipo_de_retorno_reporta_cps202():
    parent = _method("hablar", params=[], return_type=STRING)
    sub = _method("hablar", params=[], return_type=INTEGER)
    assert check_override(sub, parent) == "CPS-202"
