"""variables, constantes, literales, aritmetica, comparaciones, unarios, ternario y logica."""
import pytest

from compiler.ir.model import Const, Temp
from compiler.ir.opcodes import Opcode
from compiler.runtime.storage import StorageKind, StorageRef

from .conftest import entry_lines, function_named, program_for, tac_for

# ----------------------------------------------------------------------
# variables y constantes
# ----------------------------------------------------------------------


@pytest.mark.parametrize("keyword", ["let", "var", "const"])
def test_declaracion_con_inicializador_es_un_mov_directo(keyword):
    assert entry_lines(f"{keyword} x: integer = 5;") == ["MOV x@global[0], 5"]


def test_declaracion_sin_inicializador_no_emite_codigo():
    assert tac_for("let x: integer;") == ""


def test_literales_e_identificadores_no_crean_temporales():
    program = program_for('let a: integer = 1; let s: string = "hola"; let b: boolean = false; '
                          "let n: integer = a; let o = null; print(a); print(s);")
    assert program.entry.created_temps == 0
    movs = [i for i in program.entry.instructions if i.opcode is Opcode.MOV]
    assert movs[0].arg1 == Const(1, movs[0].arg1.type)
    assert isinstance(movs[3].arg1, StorageRef) and movs[3].arg1.name == "a"
    assert movs[4].arg1.value is None


def test_string_se_pasa_como_constante_entre_comillas():
    # la gramatica no tiene escapes: el valor es el texto crudo y el serializer lo cita
    assert entry_lines('print("hola mundo");') == ['PRINT "hola mundo"']


def test_asignacion_encadenada_reusa_la_variable_recien_escrita():
    assert entry_lines("let a: integer = 0; let b: integer = 0; a = b = 3;")[2:] == [
        "MOV b@global[1], 3",
        "MOV a@global[0], b@global[1]",
    ]


def test_variable_local_y_parametro_viven_en_el_frame():
    program = program_for("function f(p: integer): integer { let l: integer = p; return l; }")
    fn = function_named(program, "fn::f")
    mov = next(i for i in fn.instructions if i.opcode is Opcode.MOV)
    assert mov.result == StorageRef(StorageKind.LOCAL, 1, name="l")
    assert mov.arg1 == StorageRef(StorageKind.PARAM, 0, name="p")


def test_la_misma_variable_desde_global_y_desde_funcion_es_el_mismo_slot():
    text = tac_for("let g: integer = 1; function f(): integer { return g; } g = 2;")
    assert "MOV g@global[0], 2" in text and "RETURN g@global[0]" in text


def test_sombra_resuelve_igual_que_el_collector():
    # el print y el inicializador ven la x global: la local recien existe despues de su let
    fn = tac_for("let x: integer = 1; function f(): integer { print(x); let x: integer = x + 2; return x; }")
    assert "PRINT x@global[0]" in fn
    assert "t0 = BIN +, x@global[0], 2" in fn
    assert "MOV x@frame[0], t0" in fn and "RETURN x@frame[0]" in fn


def test_sombra_en_bloque_interno():
    lines = entry_lines("let x: integer = 1; { let x: integer = 2; print(x); } print(x);")
    assert lines == ["MOV x@global[0], 1", "MOV x@global[1], 2", "PRINT x@global[1]", "PRINT x@global[0]"]


# ----------------------------------------------------------------------
# aritmetica, comparaciones y unarios
# ----------------------------------------------------------------------


@pytest.mark.parametrize("op", ["+", "-", "*", "/", "%"])
def test_operador_aritmetico_es_un_bin(op):
    lines = entry_lines(f"let a: integer = 1; let b: integer = 2; let c: integer = a {op} b;")
    assert lines[2:] == [f"t0 = BIN {op}, a@global[0], b@global[1]", "MOV c@global[2], t0"]


@pytest.mark.parametrize("op", ["==", "!=", "<", "<=", ">", ">="])
def test_comparacion_es_un_bin_booleano(op):
    program = program_for(f"let a: integer = 1; let r: boolean = a {op} 2;")
    bin_ = next(i for i in program.entry.instructions if i.opcode is Opcode.BIN)
    assert bin_.meta("op") == op and bin_.result.type.name == "boolean"


def test_precedencia_la_fija_el_ast():
    lines = entry_lines("let a: integer = 1; let b: integer = 2; let c: integer = 3; let x: integer = a + b * c;")
    assert lines[3:5] == ["t0 = BIN *, b@global[1], c@global[2]", "t1 = BIN +, a@global[0], t0"]


def test_parentesis_cambian_el_orden():
    lines = entry_lines("let a: integer = 1; let b: integer = 2; let c: integer = 3; let x: integer = (a + b) * c;")
    assert lines[3:5] == ["t0 = BIN +, a@global[0], b@global[1]", "t1 = BIN *, t0, c@global[2]"]


@pytest.mark.parametrize("source,expected", [
    ("let a: integer = 1; let b: integer = -a;", "t0 = UN -, a@global[0]"),
    ("let p: boolean = true; let q: boolean = !p;", "t0 = UN !, p@global[0]"),
])
def test_unarios_son_un(source, expected):
    assert expected in entry_lines(source)


def test_concatenacion_de_strings():
    assert 't0 = BIN +, "a", "b"' in entry_lines('let s: string = "a" + "b";')


# ----------------------------------------------------------------------
# orden de evaluacion izquierda -> derecha
# ----------------------------------------------------------------------


def test_llamada_que_modifica_una_global_obliga_a_copiar_el_operando_izquierdo():
    lines = entry_lines("let g: integer = 1; function sube(): integer { g = g + 1; return g; } "
                        "let r: integer = g + sube();")
    assert lines[1:4] == ["MOV t0, g@global[0]", "CALL t1, fn::sube, argc=0", "t2 = BIN +, t0, t1"]


def test_asignacion_en_el_operando_derecho_obliga_a_copiar():
    lines = entry_lines("let g: integer = 1; let r: integer = g + (g = 5);")
    assert lines[1:4] == ["MOV t0, g@global[0]", "MOV g@global[0], 5", "t1 = BIN +, t0, g@global[0]"]


def test_sin_riesgo_de_escritura_no_hay_copia():
    # n es local y factorial no tiene static link: no puede tocar el frame de quien la llama
    text = tac_for("function factorial(n: integer): integer { if (n <= 1) { return 1; } return n * factorial(n - 1); }")
    assert "t2 = BIN *, n@frame[0], t1" in text
    assert "MOV t" not in text


def test_anidada_con_static_link_puede_escribir_el_frame_y_obliga_a_copiar():
    text = tac_for("function f(): integer { let x: integer = 1; "
                   "function g(): integer { x = 9; return 1; } return x + g(); }")
    assert "MOV t0, x@frame[0]" in text


# ----------------------------------------------------------------------
# logica con cortocircuito y ternario
# ----------------------------------------------------------------------


def test_and_y_or_nunca_son_bin():
    program = program_for("let p: boolean = true; let q: boolean = false; let r: boolean = p && q || !p;")
    assert all(i.meta("op") not in ("&&", "||") for i in program.entry.instructions)


def test_and_salta_con_if_false_antes_de_evaluar_el_derecho():
    lines = entry_lines("let p: boolean = true; let q: boolean = false; let r: boolean = p && q;")
    assert lines[2:] == ["MOV t0, p@global[0]", "IF_FALSE t0, L_and_end_0", "MOV t0, q@global[1]",
                         "LABEL L_and_end_0", "MOV r@global[2], t0"]


def test_or_salta_con_if_true():
    lines = entry_lines("let p: boolean = true; let q: boolean = false; let r: boolean = p || q;")
    assert lines[2:] == ["MOV t0, p@global[0]", "IF_TRUE t0, L_or_end_0", "MOV t0, q@global[1]",
                         "LABEL L_or_end_0", "MOV r@global[2], t0"]


def test_cortocircuito_salta_por_encima_de_una_llamada():
    lines = entry_lines("function f(): boolean { print(1); return true; } let p: boolean = false; "
                        "let r: boolean = p && f();")
    jump = lines.index("IF_FALSE t0, L_and_end_0")
    call = next(i for i, line in enumerate(lines) if "CALL" in line)
    assert jump < call < lines.index("LABEL L_and_end_0")


def test_cortocircuito_reusa_el_temporal_de_una_comparacion():
    lines = entry_lines("let x: integer = 1; let r: boolean = x > 0 && x < 9;")
    assert lines[1:3] == ["t0 = BIN >, x@global[0], 0", "IF_FALSE t0, L_and_end_0"]


def test_ternario_un_solo_temporal_de_resultado():
    lines = entry_lines("let n: integer = 1; let s: string = n > 0 ? \"si\" : \"no\";")
    assert lines[1:] == [
        "t0 = BIN >, n@global[0], 0", "IF_FALSE t0, L_tern_else_0",
        'MOV t1, "si"', "GOTO L_tern_end_1",
        "LABEL L_tern_else_0", 'MOV t1, "no"',
        "LABEL L_tern_end_1", "MOV s@global[1], t1",
    ]


def test_valor_de_la_expresion_queda_en_un_temporal_vivo_solo_mientras_se_usa():
    program = program_for("let a: integer = 1; let b: integer = 2; print(a + b); print(a - b);")
    temps = [i.result for i in program.entry.instructions if isinstance(i.result, Temp)]
    assert [t.name for t in temps] == ["t0", "t0"]
