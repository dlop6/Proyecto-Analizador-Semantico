"""herencia: campos heredados primero, override reutiliza el slot del padre."""
from .conftest import entry_lines, tac_for

SOURCE = """
class Animal {
  let nombre: string = "animal";
  function hablar(): string { return "..."; }
  function comer(): string { return "come"; }
}
class Perro : Animal {
  let raza: string = "mestizo";
  function hablar(): string { return "guau"; }
  function jugar(): string { return "juega"; }
}
"""


def test_los_campos_heredados_van_primero_en_el_objeto_de_la_subclase():
    assert entry_lines(SOURCE + "let p: Perro = new Perro();")[:3] == [
        "t0 = NEW_OBJ Perro, fields=2",
        'SET_FIELD t0, nombre@field[0], "animal"',
        'SET_FIELD t0, raza@field[1], "mestizo"',
    ]


def test_override_reutiliza_el_slot_del_padre_y_los_metodos_nuevos_van_al_final():
    lines = entry_lines(SOURCE + """
    let p: Perro = new Perro();
    print(p.hablar());
    print(p.comer());
    print(p.jugar());
    """)
    assert [line for line in lines if line.startswith("CALL_METHOD")] == [
        "CALL_METHOD t1, p@global[0], hablar[0], argc=0",
        "CALL_METHOD t1, p@global[0], comer[1], argc=0",
        "CALL_METHOD t1, p@global[0], jugar[2], argc=0",
    ]


def test_receptor_de_tipo_padre_despacha_por_el_mismo_slot():
    lines = entry_lines(SOURCE + "let a: Animal = new Perro(); print(a.hablar());")
    assert "CALL_METHOD t1, a@global[0], hablar[0], argc=0" in lines


def test_cada_clase_emite_su_propia_implementacion_y_el_heredado_no_se_duplica():
    text = tac_for(SOURCE)
    assert "FUNC_BEGIN fn::Animal.hablar, frame=1" in text
    assert "FUNC_BEGIN fn::Perro.hablar, frame=1" in text
    assert "fn::Perro.comer" not in text


def test_atributo_heredado_accedido_desde_la_subclase_usa_el_slot_del_padre():
    source = SOURCE.replace('function jugar(): string { return "juega"; }',
                            "function jugar(): string { return this.nombre; }")
    assert "GET_FIELD this@frame[0], nombre@field[0]" in tac_for(source)


def test_constructor_propio_de_la_subclase():
    source = """
    class A { let x: integer; function constructor(x: integer) { this.x = x; } }
    class B : A { function constructor(y: integer) { this.x = y * 2; } }
    let b: B = new B(5);
    """
    assert entry_lines(source) == [
        "t0 = NEW_OBJ B, fields=1",
        "ARG t0",
        "ARG 5",
        "CALL fn::B.constructor, argc=2",
        "MOV b@global[0], t0",
    ]


def test_subclase_sin_constructor_llama_al_constructor_heredado():
    source = """
    class Animal { let nombre: string; function constructor(n: string) { this.nombre = n; } }
    class Perro : Animal { function hablar(): string { return "guau"; } }
    let p: Perro = new Perro("Rex");
    """
    assert entry_lines(source) == [
        "t0 = NEW_OBJ Perro, fields=1",
        "ARG t0",
        'ARG "Rex"',
        "CALL fn::Animal.constructor, argc=2",
        "MOV p@global[0], t0",
    ]


def test_el_constructor_heredado_es_el_del_ancestro_mas_cercano():
    source = """
    class A { function constructor() {} }
    class B : A { function constructor(x: integer) {} }
    class C : B {}
    let c: C = new C(1);
    """
    assert "CALL fn::B.constructor, argc=2" in entry_lines(source)
