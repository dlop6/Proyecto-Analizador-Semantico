"""contrato del generador extendido: misma api que el core, mismo rechazo de entradas con errores."""
import inspect

import pytest

from compiler.ir.model import IRProgram
from compiler.runtime.runtime_layout import prepare
from compiler.tac.core_generator import CoreTacGenerator
from compiler.tac.extended_generator import ExtendedTacGenerator

from .conftest import program_for, semantic


def test_extiende_al_generador_core():
    assert issubclass(ExtendedTacGenerator, CoreTacGenerator)


def test_generate_tiene_la_misma_firma_que_el_core():
    signature = inspect.signature(ExtendedTacGenerator.generate)
    assert list(signature.parameters) == ["semantic_result", "runtime_layout"]
    assert isinstance(inspect.getattr_static(ExtendedTacGenerator, "generate"), classmethod)


def test_devuelve_un_irprogram():
    assert isinstance(program_for("let a: integer[] = [1];"), IRProgram)


@pytest.mark.parametrize("source", [
    "let a: integer[] = [1]; let x: integer = a[\"0\"];",   # indice no entero
    "class A {} let a: A = new A(); print(a.nada);",        # miembro inexistente
    "foreach (x in 5) { print(x); }",                        # foreach sobre no-arreglo
    "let x: integer = ;",                                    # error de sintaxis
])
def test_con_errores_no_genera_ir(source):
    result = semantic(source)
    with pytest.raises(ValueError, match="no se genera ir"):
        ExtendedTacGenerator.generate(result, None)
    with pytest.raises(ValueError, match="no se genera ir"):
        prepare(result)


def test_dos_generaciones_no_comparten_estado():
    source = "let a: integer[] = [1, 2]; foreach (x in a) { print(x); }"
    assert program_for(source) == program_for(source)
