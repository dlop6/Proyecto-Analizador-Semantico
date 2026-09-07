"""
tests end-to-end de la semantica extendida sobre clases: herencia, 'this', 'new',
acceso a miembros, llamadas a metodo y override -- corriendo el pipeline real
(frontend -> core -> extended), no mocks.
"""
from compiler.types import ClassType

from .conftest import analyze_full, codes_of


# ---------- fixture valida completa ----------

def test_fixture_valida_de_clases_y_arreglos_cero_diagnosticos(cps_fixture):
    source = cps_fixture("valid/classes_and_arrays.cps")
    result = analyze_full(source)
    assert result.diagnostics == []
    assert result.ok is True


# ---------- fixture invalida: se acumulan todos los codigos esperados ----------

def test_fixture_invalida_de_clases_acumula_todos_los_codigos(cps_fixture):
    source = cps_fixture("invalid/class_errors.cps")
    result = analyze_full(source)
    codes = codes_of(result)
    for expected in ("CPS-200", "CPS-201", "CPS-202", "CPS-203", "CPS-208",
                     "CPS-210", "CPS-211", "CPS-212", "CPS-213"):
        assert expected in codes, f"faltó {expected} en {codes}"


# ---------- 'this' y 'new' quedan tipados ----------

def test_this_dentro_de_un_metodo_queda_tipado_como_la_clase():
    source = """
    class A {
        function id(): A { return this; }
    }
    """
    result = analyze_full(source)
    assert result.diagnostics == []
    class_decl = result.ast.statements[0]
    method_body = class_decl.members[0].body
    return_stmt = method_body.statements[0]
    assert return_stmt.value.inferred_type == ClassType("A")


def test_new_de_clase_valida_da_class_type():
    source = "class A {}\nlet a: A = new A();"
    result = analyze_full(source)
    assert result.diagnostics == []
    var_decl = result.ast.statements[1]
    assert var_decl.initializer.inferred_type == ClassType("A")


def test_property_access_de_atributo_queda_tipado():
    source = """
    class A { let x: string; function constructor(x: string) { this.x = x; } }
    let a: A = new A("hola");
    print(a.x);
    """
    result = analyze_full(source)
    assert result.diagnostics == []


# ---------- subclase asignable a la clase padre, no al reves ----------

def test_subclase_asignable_a_variable_de_tipo_padre():
    source = """
    class Animal {}
    class Perro : Animal {}
    let a: Animal = new Perro();
    """
    result = analyze_full(source)
    assert result.diagnostics == []


def test_padre_no_asignable_a_variable_de_tipo_subclase():
    source = """
    class Animal {}
    class Perro : Animal {}
    let p: Perro = new Animal();
    """
    result = analyze_full(source)
    # CPS-100 (core) NO puede detectar esto: en el momento en que la core visita este
    # VarDecl, NewExpr.inferred_type todavia es None (limitacion documentada de la
    # arquitectura de dos pasadas). lo cierra esta etapa con su propio codigo, CPS-209
    # (ver docstring de extended_semantic_visitor.py).
    assert "CPS-209" in codes_of(result)


# ---------- hueco de la arquitectura de dos pasadas: declaracion y reasignacion ----------

def test_declaracion_con_tipo_incompatible_via_new_reporta_cps209():
    source = "class A {}\nclass B {}\nlet a: A = new B();"
    result = analyze_full(source)
    assert "CPS-209" in codes_of(result)


def test_reasignacion_con_tipo_incompatible_via_new_reporta_cps209():
    source = "class A {}\nclass B {}\nlet a: A = new A();\na = new B();"
    result = analyze_full(source)
    assert "CPS-209" in codes_of(result)


def test_declaracion_con_tipo_compatible_via_new_no_reporta_nada():
    source = "class Animal {}\nclass Perro : Animal {}\nlet a: Animal = new Perro();"
    result = analyze_full(source)
    assert result.diagnostics == []


def test_declaracion_de_arreglo_con_tipo_incompatible_reporta_cps209():
    source = "let a: string[] = [1, 2, 3];"
    result = analyze_full(source)
    assert "CPS-209" in codes_of(result)


# ---------- override valido no genera diagnostico ----------

def test_override_con_firma_identica_no_reporta_nada():
    source = """
    class Animal {
        function hablar(n: integer): string { return "..."; }
    }
    class Perro : Animal {
        function hablar(n: integer): string { return "guau"; }
    }
    """
    result = analyze_full(source)
    assert "CPS-202" not in codes_of(result)


# ---------- llamada a metodo heredado sin redefinir ----------

def test_llamada_a_metodo_heredado_sin_override():
    source = """
    class Animal {
        function hablar(): string { return "..."; }
    }
    class Perro : Animal {}
    let p: Animal = new Perro();
    print(p.hablar());
    """
    result = analyze_full(source)
    assert result.diagnostics == []
