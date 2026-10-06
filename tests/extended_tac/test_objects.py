"""clases y objetos: new, constructor, this, atributos y metodos."""
from compiler.ir.opcodes import Opcode

from .conftest import entry_lines, function_named, opcodes, program_for, tac_for

CLASS = """
class Punto {
  let x: integer;
  let y: integer = 7;
  function constructor(x: integer) { this.x = x; }
  function suma(): integer { return this.x + this.y; }
  function reset() { this.x = 0; }
}
"""


def test_la_declaracion_de_clase_no_emite_codigo_en_la_entrada():
    program = program_for(CLASS)
    assert len(program.entry.instructions) == 0
    assert [fn.label for fn in program.functions] == ["fn::Punto.constructor", "fn::Punto.suma", "fn::Punto.reset"]


def test_metodos_y_constructor_tienen_this_en_el_slot_cero():
    text = tac_for(CLASS)
    assert "FUNC_BEGIN fn::Punto.constructor, frame=2" in text
    assert "SET_FIELD this@frame[0], x@field[0], x@frame[1]" in text
    assert "t0 = GET_FIELD this@frame[0], x@field[0]" in text


def test_new_crea_el_objeto_inicializa_atributos_y_llama_al_constructor():
    assert entry_lines(CLASS + "let p: Punto = new Punto(3);") == [
        "t0 = NEW_OBJ Punto, fields=2",
        "SET_FIELD t0, y@field[1], 7",
        "ARG t0",
        "ARG 3",
        "CALL fn::Punto.constructor, argc=2",
        "MOV p@global[0], t0",
    ]


def test_new_sin_constructor_solo_crea_el_objeto():
    assert entry_lines("class Vacio {} let v: Vacio = new Vacio();") == [
        "t0 = NEW_OBJ Vacio, fields=0",
        "MOV v@global[0], t0",
    ]


def test_lectura_y_escritura_de_atributos():
    lines = entry_lines(CLASS + "let p: Punto = new Punto(1); p.y = p.x + 1;")
    assert lines[-3:] == [
        "t1 = GET_FIELD p@global[0], x@field[0]",
        "t2 = BIN +, t1, 1",
        "SET_FIELD p@global[0], y@field[1], t2",
    ]


def test_llamada_a_metodo_usa_call_method_con_el_slot_y_sin_contar_al_receptor():
    lines = entry_lines(CLASS + "let p: Punto = new Punto(1); let s: integer = p.suma();")
    assert lines[-2:] == ["CALL_METHOD t1, p@global[0], suma[0], argc=0", "MOV s@global[1], t1"]


def test_metodo_usado_como_sentencia_no_pide_temporal():
    lines = entry_lines(CLASS + "let p: Punto = new Punto(1); p.reset(); p.suma();")
    assert lines[-2:] == ["CALL_METHOD p@global[0], reset[1], argc=0", "CALL_METHOD p@global[0], suma[0], argc=0"]


def test_argumentos_del_metodo_van_de_izquierda_a_derecha():
    source = """
    class C { function f(a: integer, b: integer): integer { return a - b; } }
    let c: C = new C();
    let r: integer = c.f(1, 2);
    """
    assert entry_lines(source)[-4:] == ["ARG 1", "ARG 2", "CALL_METHOD t1, c@global[0], f[0], argc=2", "MOV r@global[1], t1"]


def test_llamada_a_metodo_sobre_this_dentro_de_otro_metodo():
    source = """
    class C {
      function a(): integer { return 1; }
      function b(): integer { return this.a() + 1; }
    }
    """
    body = function_named(program_for(source), "fn::C.b").instructions
    assert opcodes(body)[:3] == [Opcode.FUNC_BEGIN, Opcode.CALL_METHOD, Opcode.BIN]


def test_this_desde_funcion_anidada_es_un_acceso_nonlocal():
    source = """
    class S {
      let t: string = "x";
      function m(): string { function g(): string { return this.t; } return g(); }
    }
    """
    text = tac_for(source)
    assert "GET_FIELD this@frame^1[0], t@field[0]" in text
    assert "CALL t0, fn::S.m.g, argc=0, link=0" in text


def test_receptor_resultado_de_new():
    lines = entry_lines(CLASS + "print(new Punto(2).suma());")
    assert lines[-2:] == ["CALL_METHOD t1, t0, suma[0], argc=0", "PRINT t1"]


def test_metodo_void_usado_como_valor_da_null():
    source = CLASS + "let p: Punto = new Punto(1); print(p.reset());"
    assert entry_lines(source)[-2:] == ["CALL_METHOD p@global[0], reset[1], argc=0", "PRINT null"]


def test_concatenacion_de_string_con_entero_es_un_bin_suma():
    lines = entry_lines('let n: integer = 3; print("n = " + n);')
    assert lines[-2:] == ['t0 = BIN +, "n = ", n@global[0]', "PRINT t0"]
