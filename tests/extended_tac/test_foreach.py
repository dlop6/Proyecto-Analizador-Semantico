"""foreach: indice + LEN + ARR_GET, con break/continue reutilizando las pilas del core."""
from compiler.ir.opcodes import Opcode

from .conftest import entry_lines, function_named, opcodes, program_for, tac_for

SOURCE = "let a: integer[] = [1, 2]; foreach (x in a) { print(x); }"


def test_forma_completa_del_foreach():
    assert entry_lines(SOURCE)[4:] == [
        "MOV t0, a@global[0]",
        "MOV t1, 0",
        "t2 = LEN t0",
        "LABEL L_foreach_cond_0",
        "t3 = BIN <, t1, t2",
        "IF_FALSE t3, L_foreach_end_2",
        "t4 = ARR_GET t0, t1",
        "MOV x@global[1], t4",
        "PRINT x@global[1]",
        "LABEL L_foreach_step_1",
        "t1 = BIN +, t1, 1",
        "GOTO L_foreach_cond_0",
        "LABEL L_foreach_end_2",
    ]


def test_el_iterable_se_evalua_una_sola_vez_antes_del_bucle():
    source = """
    function datos(): integer[] { return [1, 2]; }
    foreach (x in datos()) { print(x); }
    """
    lines = entry_lines(source)
    calls = [line for line in lines if "CALL" in line and "fn::datos" in line]
    assert len(calls) == 1
    assert lines.index(calls[0]) < next(i for i, line in enumerate(lines) if line.startswith("LABEL L_foreach_cond"))


def test_continue_salta_al_incremento_y_break_a_la_salida():
    source = """
    let a: integer[] = [1, 2, 3];
    foreach (x in a) {
      if (x == 1) { continue; }
      if (x == 3) { break; }
      print(x);
    }
    """
    gotos = [line for line in entry_lines(source) if line.startswith("GOTO")]
    assert "GOTO L_foreach_step_1" in gotos
    assert "GOTO L_foreach_end_2" in gotos


def test_foreach_anidado_usa_las_etiquetas_del_bucle_mas_interno():
    source = """
    let m: integer[][] = [[1], [2]];
    foreach (fila in m) { foreach (x in fila) { break; } continue; }
    """
    lines = entry_lines(source)
    assert "GOTO L_foreach_end_5" in lines      # break del foreach interno
    assert "GOTO L_foreach_step_1" in lines     # continue del foreach externo
    assert lines.index("GOTO L_foreach_end_5") < lines.index("GOTO L_foreach_step_1")


def test_foreach_dentro_de_una_funcion_usa_slots_del_frame():
    source = "function f(a: integer[]) { foreach (x in a) { print(x); } }"
    body = function_named(program_for(source), "fn::f").instructions
    assert Opcode.LEN in opcodes(body)
    text = tac_for(source)
    assert "MOV t0, a@frame[0]" in text
    assert "MOV x@frame[1], t4" in text


def test_foreach_sobre_matriz_entrega_cada_fila_como_arreglo():
    lines = entry_lines("let m: integer[][] = [[1]]; foreach (fila in m) { print(fila[0]); }")
    assert any(line.startswith("MOV fila@global[1], t") for line in lines)
