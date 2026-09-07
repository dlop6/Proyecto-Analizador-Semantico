"""
tests end-to-end de la semantica extendida sobre arreglos: literales, indices,
asignacion a un elemento, anidados -- corriendo el pipeline real (frontend -> core ->
extended), no mocks.
"""
from compiler.types import ArrayType, INTEGER

from .conftest import analyze_full, codes_of


def test_fixture_invalida_de_arreglos_acumula_todos_los_codigos(cps_fixture):
    source = cps_fixture("invalid/array_errors.cps")
    result = analyze_full(source)
    codes = codes_of(result)
    for expected in ("CPS-207", "CPS-205", "CPS-206", "CPS-204"):
        assert expected in codes, f"faltó {expected} en {codes}"


def test_literal_homogeneo_queda_tipado():
    source = "let numeros: integer[] = [1, 2, 3];"
    result = analyze_full(source)
    assert result.diagnostics == []
    var_decl = result.ast.statements[0]
    assert var_decl.initializer.inferred_type == ArrayType(INTEGER)


def test_literal_vacio_es_asignable_a_cualquier_array():
    source = "let a: integer[] = [];\nlet b: string[] = [];"
    result = analyze_full(source)
    assert result.diagnostics == []


def test_arreglo_anidado_queda_tipado():
    source = "let matriz: integer[][] = [[1, 2], [3, 4]];\nprint(matriz[0][1]);"
    result = analyze_full(source)
    assert result.diagnostics == []
    var_decl = result.ast.statements[0]
    assert var_decl.initializer.inferred_type == ArrayType(ArrayType(INTEGER))


def test_asignacion_a_elemento_con_tipo_compatible():
    source = "let numeros: integer[] = [1, 2, 3];\nnumeros[0] = 10;"
    result = analyze_full(source)
    assert result.diagnostics == []


def test_arrays_de_clases_son_invariantes():
    source = """
    class Animal {}
    class Perro : Animal {}
    let animales: Animal[] = [new Animal()];
    let perros: Perro[] = [new Perro()];
    let mal: Animal[] = perros;
    """
    result = analyze_full(source)
    assert "CPS-100" in codes_of(result)  # Array[Perro] no es asignable a Array[Animal]


def test_foreach_sobre_arreglo_tipa_la_variable_de_iteracion():
    source = "let numeros: integer[] = [1, 2, 3];\nforeach (n in numeros) { print(n); }"
    result = analyze_full(source)
    assert result.diagnostics == []
