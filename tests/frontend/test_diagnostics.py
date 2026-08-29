"""tests de compiler/diagnostics.py: contrato posicional, bolsa de diagnosticos, catalogo."""
import re

from compiler.diagnostics import Diagnostic, DiagnosticBag, Severity, _MESSAGES


def test_diagnostic_es_posicional_como_exige_el_pdf():
    d = Diagnostic("CPS-020", "mensaje de prueba", 3, 7)
    assert d.code == "CPS-020"
    assert d.message == "mensaje de prueba"
    assert d.line == 3
    assert d.column == 7
    assert d.severity == Severity.ERROR  # default
    assert d.length == 1  # default


def test_has_errors_ignora_warnings():
    bag = DiagnosticBag()
    bag.warning("CPS-002", 1, 1, detail="99999999999999999999999")
    assert not bag.has_errors
    bag.error("CPS-020", 2, 2, detail="x")
    assert bag.has_errors


def test_dedupe_por_code_line_column():
    bag = DiagnosticBag()
    bag.error("CPS-020", 5, 3, detail="x")
    bag.error("CPS-020", 5, 3, detail="x")
    bag.error("CPS-020", 5, 3, detail="otro detalle distinto")  # misma posicion, sigue siendo dup
    assert len(bag) == 1


def test_orden_determinista_linea_columna_codigo():
    bag = DiagnosticBag()
    bag.error("CPS-021", 2, 1, detail="a")
    bag.error("CPS-020", 1, 5, detail="b")
    bag.error("CPS-020", 1, 1, detail="c")
    ordenados = bag.sorted()
    posiciones = [(d.line, d.column) for d in ordenados]
    assert posiciones == sorted(posiciones)


def test_severidad_por_defecto_segun_catalogo():
    bag = DiagnosticBag()
    d = bag.report("CPS-002", 1, 1, detail="123")  # CPS-002 es warning por diseño
    assert d.severity == Severity.WARNING


def test_ningun_codigo_huerfano_en_el_catalogo():
    # todo codigo usado en el proyecto debe tener mensaje. si alguien agrega un codigo
    # y se olvida del mensaje, este test truena.
    patron = re.compile(r"^CPS-\d{3}$")
    for code in _MESSAGES:
        assert patron.match(code), f"codigo con formato invalido: {code}"


def test_codigos_de_persona1_no_invaden_el_rango_de_otros():
    # persona 1 es dueño exclusivo de CPS-0xx. CPS-1xx es de persona 2, CPS-2xx de persona 3.
    for code in _MESSAGES:
        numero = int(code.split("-")[1])
        assert numero < 100, f"{code} se sale del rango CPS-0xx reservado para persona 1"
