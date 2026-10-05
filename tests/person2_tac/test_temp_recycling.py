"""
reciclaje de temporales observable (gate B): los nombres liberados se reutilizan, nunca
hay dos valores vivos en el mismo temporal y el pico queda registrado por funcion.
"""
from .conftest import FIXTURES, entry_lines, program_for


def test_una_secuencia_de_expresiones_reusa_los_nombres_liberados():
    lines = entry_lines("let a: integer = 1; let b: integer = 2; "
                        "let x: integer = a * b + a; let y: integer = b - a; let z: integer = a % b;")
    written = [line.split(" = ")[0] for line in lines if " = BIN" in line]
    assert written == ["t0", "t1", "t0", "t0"]


def test_expresion_grande_con_pocos_temporales():
    program = program_for("let a: integer = 1; let r: integer = a * a + a * a + a * a + a * a + a * a;")
    assert program.entry.peak_temps <= 3
    assert program.entry.created_temps <= 3


def test_pico_por_funcion_coincide_con_func_end():
    program = program_for("function f(a: integer): integer { return (a + 1) * (a + 2) * (a + 3); }")
    fn = program.functions[0]
    assert fn.peak_temps == fn.instructions[-1].meta("temps") == 3


def test_dos_funciones_compiladas_seguidas_no_comparten_temporales():
    program = program_for("function f(): integer { return 1 + 2; } function g(): integer { return 3 + 4; }")
    first_results = [fn.instructions[1].result for fn in program.functions]
    assert [t.name for t in first_results] == ["t0", "t0"]
    assert first_results[0].unit != first_results[1].unit


def test_categorias_distintas_no_se_mezclan_en_el_pool():
    lines = entry_lines('let a: integer = 1; let s: string = "x" + "y"; let n: integer = a + a;')
    assert lines[1] == 't0 = BIN +, "x", "y"'
    assert lines[3] == "t1 = BIN +, a@global[0], a@global[0]"


def test_todos_los_fixtures_respetan_las_reglas_del_temp_manager():
    """
    el IRBuilder de persona 1 explota si se lee un temporal ya liberado, si se libera dos
    veces o si una unidad cierra con temporales vivos. que todos los fixtures generen sin
    IRError demuestra que el generador libera cada temporal exactamente una vez y despues
    de su ultimo uso; el pico chico demuestra que de verdad se recicla.
    """
    for path in sorted((FIXTURES / "valid").glob("*.cps")):
        program = program_for(path.read_text(encoding="utf-8"))
        for unit in [program.entry] + list(program.functions):
            assert unit.peak_temps <= 5, (path.name, unit)
            assert unit.peak_temps <= unit.created_temps


def test_un_temporal_liberado_se_reusa_y_uno_vivo_no():
    # (a + b) sigue vivo mientras se calcula (a - b): no pueden compartir nombre
    lines = entry_lines("let a: integer = 1; let b: integer = 2; let r: integer = (a + b) * (a - b);")
    assert lines[2:5] == ["t0 = BIN +, a@global[0], b@global[1]", "t1 = BIN -, a@global[0], b@global[1]",
                          "t2 = BIN *, t0, t1"]
