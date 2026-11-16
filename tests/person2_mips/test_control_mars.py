"""LABEL, GOTO, IF_TRUE e IF_FALSE ejecutados en mars, con todas las construcciones de control del lenguaje."""
from .support import assemble, output


def test_if_else_encadenado():
    # la gramatica exige llaves: el "else if" es un if dentro del bloque else
    assert output("""
    function clasificar(n: integer): string {
        if (n < 0) { return "negativo"; }
        else { if (n == 0) { return "cero"; } else { if (n > 100) { return "grande"; } } }
        return "positivo";
    }
    print(clasificar(-3)); print(clasificar(0)); print(clasificar(7)); print(clasificar(500));
    """) == ["negativo", "cero", "positivo", "grande"]


def test_while_suma():
    assert output("""
    let i: integer = 1;
    let suma: integer = 0;
    while (i <= 100) { suma = suma + i; i = i + 1; }
    print(suma);
    """) == ["5050"]


def test_while_que_no_entra():
    assert output("let i: integer = 10; while (i < 3) { print(i); } print(\"fin\");") == ["fin"]


def test_do_while_corre_al_menos_una_vez():
    assert output("""
    let i: integer = 10;
    do { print(i); i = i + 1; } while (i < 3);
    let j: integer = 0;
    do { j = j + 2; } while (j < 7);
    print(j);
    """) == ["10", "8"]


def test_for_con_y_sin_condicion():
    assert output("""
    for (let k: integer = 0; k < 3; k = k + 1) { print(k); }
    let i: integer = 0;
    for (i = 10; ; i = i - 1) { if (i < 8) { break; } }
    print(i);
    """) == ["0", "1", "2", "7"]


def test_bucles_anidados_con_break_y_continue_al_mas_interno():
    assert output("""
    let i: integer = 0;
    while (i < 10) {
        i = i + 1;
        if (i % 2 == 0) { continue; }
        for (let j: integer = 0; j < i; j = j + 1) {
            if (j == 3) { break; }
            if (j == 1) { continue; }
            print(j);
        }
        do {
            if (i > 7) { break; }
            continue;
        } while (false);
        if (i > 8) { break; }
    }
    print(i);
    """) == ["0", "0", "2", "0", "2", "0", "2", "0", "2", "9"]


def test_tablas_de_multiplicar_anidadas():
    assert output("""
    for (let a: integer = 1; a <= 3; a = a + 1) {
        let linea: string = "";
        for (let b: integer = 1; b <= 3; b = b + 1) { linea = linea + (a * b) + " "; }
        print(linea);
    }
    """) == ["1 2 3 ", "2 4 6 ", "3 6 9 "]


def test_switch_sin_fallthrough_con_default():
    assert output("""
    function nombre(n: integer): string {
        let r: string = "?";
        switch (n) {
            case 1: r = "uno";
            case 2: r = "dos"; break;
            default: r = "otro";
        }
        return r;
    }
    print(nombre(1)); print(nombre(2)); print(nombre(9));
    """) == ["uno", "dos", "otro"]


def test_switch_sin_default_y_con_continue_dentro_de_un_bucle():
    assert output("""
    switch (3) { case 4: print("cuatro"); }
    let i: integer = 0;
    while (i < 4) {
        i = i + 1;
        switch (i) {
            case 2: continue;
            default: print(i);
        }
    }
    """) == ["1", "3", "4"]


def test_while_true_con_break():
    assert output("""
    let n: integer = 0;
    while (true) { n = n + 1; if (n == 5) { break; } }
    print(n);
    """) == ["5"]


def test_condicion_constante_se_resuelve_al_compilar():
    asm = assemble("while (true) { print(1); break; } if (false) { print(2); }")
    assert "beqz" not in asm and "bnez" not in asm


def test_condicion_que_muere_en_el_salto_no_se_guarda_en_su_home():
    # el temporal de `i < 3` solo lo lee el IF_FALSE: no tiene que volcarse a memoria antes de saltar
    asm = assemble("let i: integer = 0; while (i < 3) { i = i + 1; }")
    assert "guarda t" not in asm
