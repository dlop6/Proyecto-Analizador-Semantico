"""arreglos: literales, indexacion, asignacion indexada y multidimensionales."""
from compiler.ir.opcodes import Opcode

from .conftest import entry_lines, opcodes, program_for


def test_literal_crea_el_arreglo_y_asigna_cada_elemento_en_orden():
    lines = entry_lines("let a: integer[] = [7, 8, 9];")
    assert lines == [
        "t0 = NEW_ARR 3",
        "ARR_SET t0, 0, 7",
        "ARR_SET t0, 1, 8",
        "ARR_SET t0, 2, 9",
        "MOV a@global[0], t0",
    ]


def test_literal_vacio_con_contexto_crea_un_arreglo_de_cero_elementos():
    assert entry_lines("let a: integer[] = [];") == ["t0 = NEW_ARR 0", "MOV a@global[0], t0"]


def test_lectura_por_indice_usa_arr_get():
    lines = entry_lines("let a: integer[] = [1, 2]; let x: integer = a[1];")
    assert "t1 = ARR_GET a@global[0], 1" in lines
    assert lines[-1] == "MOV x@global[1], t1"


def test_asignacion_indexada_usa_arr_set_sobre_el_arreglo():
    lines = entry_lines("let a: integer[] = [1, 2]; let i: integer = 0; a[i] = 5;")
    assert lines[-1] == "ARR_SET a@global[0], i@global[1], 5"


def test_asignacion_indexada_evalua_el_valor_despues_del_indice():
    lines = entry_lines("let a: integer[] = [1, 2]; a[0] = a[1] + 1;")
    get, add, set_ = lines[-3:]
    assert get == "t1 = ARR_GET a@global[0], 1"
    assert add == "t2 = BIN +, t1, 1"
    assert set_ == "ARR_SET a@global[0], 0, t2"


def test_asignacion_indexada_usada_como_valor_devuelve_el_valor_asignado():
    lines = entry_lines("let a: integer[] = [1]; let x: integer = 0; x = a[0] = 3;")
    assert lines[-2:] == ["ARR_SET a@global[0], 0, 3", "MOV x@global[1], 3"]


def test_matriz_es_un_arreglo_de_arreglos():
    lines = entry_lines("let m: integer[][] = [[1], [2]];")
    assert lines == [
        "t0 = NEW_ARR 2",
        "t1 = NEW_ARR 1",
        "ARR_SET t1, 0, 1",
        "ARR_SET t0, 0, t1",
        "t1 = NEW_ARR 1",
        "ARR_SET t1, 0, 2",
        "ARR_SET t0, 1, t1",
        "MOV m@global[0], t0",
    ]


def test_indexacion_multidimensional_encadena_arr_get():
    lines = entry_lines("let m: integer[][] = [[1, 2]]; let x: integer = m[0][1];")
    # t0 se recicla (ya se libero tras el MOV); el elemento es int y sale de otro pool
    assert lines[-3:] == ["t0 = ARR_GET m@global[0], 0", "t2 = ARR_GET t0, 1", "MOV x@global[1], t2"]


def test_asignacion_en_matriz_lee_la_fila_y_escribe_el_elemento():
    lines = entry_lines("let m: integer[][] = [[1, 2]]; m[0][1] = 9;")
    assert lines[-2:] == ["t0 = ARR_GET m@global[0], 0", "ARR_SET t0, 1, 9"]


def test_el_indice_que_reescribe_la_variable_obliga_a_copiar_el_arreglo_antes():
    # izquierda -> derecha: el arreglo se lee ANTES de que la llamada pueda reasignarlo
    source = """
    let a: integer[] = [1, 2];
    function cambiar(): integer { a = [5, 6]; return 0; }
    let x: integer = a[cambiar()];
    """
    lines = entry_lines(source)
    assert lines[-4:] == [
        "MOV t0, a@global[0]",
        "CALL t1, fn::cambiar, argc=0",
        "t2 = ARR_GET t0, t1",
        "MOV x@global[1], t2",
    ]


def test_no_hay_chequeo_estatico_de_limites():
    program = program_for("let a: integer[] = [1]; print(a[99]);")
    assert Opcode.ARR_GET in opcodes(program.entry.instructions)
