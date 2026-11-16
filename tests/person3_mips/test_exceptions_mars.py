"""try/catch en mars: captura local, anidada, propagada por llamadas y error no capturado."""
from .support import assemble, output


def test_codigo_normal_no_ejecuta_el_catch():
    assert output("""
    try { print("try"); } catch (e) { print("catch"); }
    print("despues");
    """) == ["try", "despues"]


def test_error_corta_el_resto_del_try_y_entra_al_catch_con_el_mensaje():
    assert output("""
    let v: integer[] = [1];
    try { print("uno"); print(v[1]); print("no llega"); } catch (e) { print("catch: " + e); }
    print("sigue");
    """) == ["uno", "catch: indice fuera de rango", "sigue"]


def test_division_entre_cero_capturada():
    assert output("""
    let cero: integer = 0;
    try { print(10 / cero); } catch (e) { print(e); }
    try { print(10 % cero); } catch (e) { print(e); }
    """) == ["division entre cero", "division entre cero"]


def test_try_anidados_usan_el_manejador_mas_interno():
    assert output("""
    let v: integer[] = [1];
    try {
        try { print(v[5]); } catch (a) { print("interno: " + a); }
        print(v[6]);
    } catch (b) { print("externo: " + b); }
    """) == ["interno: indice fuera de rango", "externo: indice fuera de rango"]


def test_error_dentro_del_catch_va_al_try_que_lo_encierra():
    assert output("""
    let v: integer[] = [1];
    try {
        try { print(v[5]); } catch (a) { print(v[7]); }
    } catch (b) { print("afuera: " + b); }
    """) == ["afuera: indice fuera de rango"]


def test_error_se_propaga_por_dos_funciones_hasta_el_catch():
    assert output("""
    let v: integer[] = [1, 2];
    function profunda(i: integer): integer { return v[i]; }
    function media(i: integer): integer { let r: integer = profunda(i); print("media ok"); return r; }
    try {
        print(media(0));
        print(media(9));
        print("no llega");
    } catch (e) { print("arriba: " + e); }
    """) == ["media ok", "1", "arriba: indice fuera de rango"]


def test_catch_dentro_de_una_funcion_y_return_dentro_del_try():
    assert output("""
    let v: integer[] = [5];
    function seguro(i: integer): integer {
        try { return v[i]; } catch (e) { print("seguro: " + e); }
        return -1;
    }
    print(seguro(0));
    print(seguro(3));
    """) == ["5", "seguro: indice fuera de rango", "-1"]


def test_break_y_continue_dentro_de_un_try_en_un_lazo():
    assert output("""
    let v: integer[] = [1, 2, 3, 4];
    let i: integer = 0;
    while (i < 10) {
        i = i + 1;
        try {
            if (i == 2) { continue; }
            if (i == 4) { break; }
            print(v[i]);
        } catch (e) { print(e); }
    }
    print(i);
    """) == ["2", "4", "4"]


def test_error_no_capturado_en_una_funcion_termina_controladamente():
    assert output("""
    function f(): integer { let v: integer[] = []; return v[0]; }
    print("antes");
    print(f());
    print("no llega");
    """) == ["antes", "Error no capturado: indice fuera de rango"]


def test_el_try_no_emite_codigo_en_tiempo_de_ejecucion():
    # los manejadores son lexicos: el try solo cambia a donde salta cada chequeo de $v1
    asm = assemble("let v: integer[] = [1]; try { print(v[0]); } catch (e) { print(e); }")
    assert "bne $v1, $zero, L_try_handler_0" in asm
