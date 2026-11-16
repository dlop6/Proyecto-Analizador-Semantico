"""arreglos en mars: 0/1/n elementos, matrices, foreach, escritura indexada y chequeo de limites."""
import pytest

from .support import assemble, output


def test_literal_lectura_y_escritura_indexada():
    assert output("""
    let v: integer[] = [3, 1, 4, 1, 5];
    v[4] = v[0] + v[2];
    let i: integer = 1;
    v[i] = 9;
    print(v[4]);
    print(v[1]);
    """) == ["7", "9"]


@pytest.mark.parametrize("literal, expected", [("[]", "0"), ("[42]", "1"), ("[1, 2, 3, 4, 5, 6, 7]", "7")])
def test_longitud_de_arreglos_de_0_1_y_n_elementos(literal, expected):
    # la longitud solo se observa con foreach (LEN), que es el unico que la usa
    assert output(f"""
    let v: integer[] = {literal};
    let n: integer = 0;
    foreach (x in v) {{ n = n + 1; }}
    print(n);
    """) == [expected]


def test_la_longitud_va_en_la_palabra_0_y_los_elementos_desde_el_offset_4():
    asm = assemble("let v: integer[] = [7, 8]; print(v[1]);")
    assert "    li $t8, 12\n" in asm                      # rt_alloc(4 + 4*2)
    assert "    sw $t8, 0($t0)    # longitud" in asm
    assert "    sw $t8, 4($t0)\n" in asm and "    sw $t8, 8($t0)\n" in asm
    assert "    lw $t0, 8($t8)\n" in asm                  # v[1] = 4 + 4*1


def test_inicializar_un_literal_no_chequea_limites_pero_indexar_si():
    asm = assemble("let v: integer[] = [7, 8, 9]; print(v[1]);")
    assert asm.count("jal rt_check_bounds") == 1     # solo la lectura v[1]
    # un ARR_SET sobre un arreglo que no se acaba de crear si se chequea
    asm = assemble("let v: integer[] = [7, 8, 9]; v[0] = 1;")
    assert asm.count("jal rt_check_bounds") == 1


def test_matriz_como_arreglo_de_arreglos():
    assert output("""
    let m: integer[][] = [[1, 2], [3, 4], [5, 6]];
    m[2][1] = m[0][0] + m[1][1];
    print(m[2][1]);
    let suma: integer = 0;
    foreach (fila in m) { foreach (x in fila) { suma = suma + x; } }
    print(suma);
    """) == ["5", "20"]


def test_foreach_sobre_strings_con_break_y_continue():
    assert output("""
    let palabras: string[] = ["a", "saltar", "b", "fin", "c"];
    foreach (p in palabras) {
        if (p == "saltar") { continue; }
        if (p == "fin") { break; }
        print(p);
    }
    """) == ["a", "b"]


def test_arreglo_de_objetos_y_arreglo_dentro_de_un_objeto():
    assert output("""
    class Caja { let items: integer[] = [1, 2, 3]; }
    let cajas: Caja[] = [new Caja(), new Caja()];
    cajas[1].items[0] = 50;
    print(cajas[0].items[0]);
    print(cajas[1].items[0]);
    """) == ["1", "50"]


@pytest.mark.parametrize("index", ["3", "-1", "100"])
def test_indice_fuera_de_rango_sin_try_termina_controladamente(index):
    assert output(f"""
    let v: integer[] = [1, 2, 3];
    print("antes");
    print(v[{index}]);
    print("no llega");
    """) == ["antes", "Error no capturado: indice fuera de rango"]


def test_asignacion_fuera_de_rango_tampoco_escribe():
    assert output("""
    let v: integer[] = [1, 2];
    try { v[2] = 5; } catch (e) { print(e); }
    print(v[0] + v[1]);
    """) == ["indice fuera de rango", "3"]


def test_arreglo_null_se_detecta_al_indexar_y_al_recorrer():
    assert output("""
    let v: integer[] = null;
    try { print(v[0]); } catch (e) { print(e); }
    try { foreach (x in v) { print(x); } } catch (e) { print("foreach: " + e); }
    """) == ["acceso a null", "foreach: acceso a null"]


def test_indice_calculado_en_un_lazo():
    assert output("""
    let v: integer[] = [0, 0, 0, 0];
    for (let i: integer = 0; i < 4; i = i + 1) { v[i] = i * i; }
    print(v[3] + v[2]);
    """) == ["13"]
