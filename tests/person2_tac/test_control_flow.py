"""if/else, while, do-while, for, switch, break y continue (INTERMEDIATE_CODE.md §10)."""
from .conftest import entry_lines, label_at

LOOP_PREFIX = "let i: integer = 0; "


def test_if_sin_else_salta_al_final():
    assert entry_lines("let x: integer = 1; if (x > 0) { print(x); }")[1:] == [
        "t0 = BIN >, x@global[0], 0", "IF_FALSE t0, L_if_end_0", "PRINT x@global[0]", "LABEL L_if_end_0",
    ]


def test_if_con_else():
    assert entry_lines("let x: integer = 1; if (x > 0) { print(1); } else { print(2); }")[1:] == [
        "t0 = BIN >, x@global[0], 0", "IF_FALSE t0, L_if_else_0", "PRINT 1", "GOTO L_if_end_1",
        "LABEL L_if_else_0", "PRINT 2", "LABEL L_if_end_1",
    ]


def test_if_con_condicion_constante():
    assert entry_lines("if (true) { print(1); }")[0] == "IF_FALSE true, L_if_end_0"


def test_while():
    assert entry_lines(LOOP_PREFIX + "while (i < 3) { i = i + 1; }")[1:] == [
        "LABEL L_while_cond_0", "t0 = BIN <, i@global[0], 3", "IF_FALSE t0, L_while_end_1",
        "t1 = BIN +, i@global[0], 1", "MOV i@global[0], t1", "GOTO L_while_cond_0", "LABEL L_while_end_1",
    ]


def test_do_while():
    assert entry_lines(LOOP_PREFIX + "do { i = i + 1; } while (i < 3);")[1:] == [
        "LABEL L_do_body_0", "t0 = BIN +, i@global[0], 1", "MOV i@global[0], t0",
        "LABEL L_do_cond_1", "t1 = BIN <, i@global[0], 3", "IF_TRUE t1, L_do_body_0", "LABEL L_do_end_2",
    ]


def test_for():
    assert entry_lines("for (let k: integer = 0; k < 2; k = k + 1) { print(k); }") == [
        "MOV k@global[0], 0", "LABEL L_for_cond_0", "t0 = BIN <, k@global[0], 2", "IF_FALSE t0, L_for_end_2",
        "PRINT k@global[0]", "LABEL L_for_step_1", "t1 = BIN +, k@global[0], 1", "MOV k@global[0], t1",
        "GOTO L_for_cond_0", "LABEL L_for_end_2",
    ]


def test_for_sin_condicion_no_tiene_salto_condicional():
    lines = entry_lines(LOOP_PREFIX + "for (i = 0; ; i = i + 1) { break; }")
    assert not any(line.startswith("IF_") for line in lines)
    assert "GOTO L_for_end_2" in lines


def test_for_con_asignacion_como_inicializacion():
    assert entry_lines(LOOP_PREFIX + "for (i = 5; i > 0; i = i - 1) { }")[1] == "MOV i@global[0], 5"


# ----------------------------------------------------------------------
# break / continue
# ----------------------------------------------------------------------


def test_continue_de_while_va_a_la_condicion():
    lines = entry_lines(LOOP_PREFIX + "while (i < 3) { i = i + 1; continue; }")
    assert lines[-3] == "GOTO L_while_cond_0"


def test_continue_de_do_while_va_a_la_condicion_no_al_cuerpo():
    lines = entry_lines(LOOP_PREFIX + "do { continue; } while (i < 3);")
    assert lines[2] == "GOTO L_do_cond_1"


def test_continue_de_for_va_al_paso():
    lines = entry_lines("for (let k: integer = 0; k < 2; k = k + 1) { continue; }")
    assert lines[4] == "GOTO L_for_step_1"


def test_break_sale_del_bucle():
    lines = entry_lines(LOOP_PREFIX + "while (true) { break; }")
    assert "GOTO L_while_end_1" in lines


def test_break_y_continue_en_bucles_anidados_van_al_mas_interno():
    lines = entry_lines(
        LOOP_PREFIX
        + "while (i < 9) { for (let j: integer = 0; j < 9; j = j + 1) { if (j == 1) { continue; } "
          "if (j == 2) { break; } } if (i == 3) { continue; } break; }"
    )
    inner_continue = lines[lines.index("LABEL L_if_end_5") - 1]
    inner_break = lines[lines.index("LABEL L_if_end_6") - 1]
    outer_continue = lines[lines.index("LABEL L_if_end_7") - 1]
    assert inner_continue == "GOTO L_for_step_3"
    assert inner_break == "GOTO L_for_end_4"
    assert outer_continue == "GOTO L_while_cond_0"
    assert lines[lines.index("LABEL L_if_end_7") + 1] == "GOTO L_while_end_1"


def test_funcion_dentro_de_un_bucle_no_hereda_sus_destinos():
    text_lines = entry_lines(
        LOOP_PREFIX + "while (i < 1) { function f() { while (true) { break; } } f(); break; }"
    )
    assert "GOTO L_while_end_1" in text_lines


# ----------------------------------------------------------------------
# switch
# ----------------------------------------------------------------------


def test_switch_evalua_el_sujeto_una_vez_y_sin_fallthrough():
    lines = entry_lines(
        "let x: integer = 1; switch (x + 1) { case 1: print(1); case 2: print(2); default: print(0); }"
    )
    assert lines[1:] == [
        "t0 = BIN +, x@global[0], 1",
        "t1 = BIN ==, t0, 1", "IF_TRUE t1, L_switch_case_0",
        "t1 = BIN ==, t0, 2", "IF_TRUE t1, L_switch_case_1",
        "GOTO L_switch_default_2",
        "LABEL L_switch_case_0", "PRINT 1", "GOTO L_switch_end_3",
        "LABEL L_switch_case_1", "PRINT 2", "GOTO L_switch_end_3",
        "LABEL L_switch_default_2", "PRINT 0", "GOTO L_switch_end_3",
        "LABEL L_switch_end_3",
    ]
    assert lines.count("t0 = BIN +, x@global[0], 1") == 1


def test_switch_con_variable_la_copia_a_un_temporal():
    lines = entry_lines("let x: integer = 1; switch (x) { case 1: print(1); }")
    assert lines[1] == "MOV t0, x@global[0]"


def test_switch_sin_default_salta_al_final():
    lines = entry_lines("let x: integer = 1; switch (x) { case 1: print(1); }")
    assert "GOTO L_switch_end_1" in lines[:lines.index("LABEL L_switch_case_0")]


def test_break_dentro_de_switch_sale_del_switch():
    lines = entry_lines("let x: integer = 1; switch (x) { case 1: break; }")
    assert lines[lines.index("LABEL L_switch_case_0") + 1] == "GOTO L_switch_end_1"


def test_continue_dentro_de_switch_va_al_bucle_que_lo_encierra():
    lines = entry_lines(LOOP_PREFIX + "while (i < 3) { switch (i) { case 1: continue; } i = i + 1; }")
    case = label_at(lines, "switch_case")
    assert lines[lines.index(f"LABEL {case}") + 1] == "GOTO L_while_cond_0"


def test_switch_de_strings():
    lines = entry_lines('let s: string = "a"; switch (s) { case "a": print(1); }')
    assert 't1 = BIN ==, t0, "a"' in lines
