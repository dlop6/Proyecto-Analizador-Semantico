"""helpers de los tests del tac core: pipeline real de punta a punta, nada mockeado."""
from pathlib import Path

from compiler.core_semantics import analyze as analyze_core
from compiler.extended_semantics import analyze as analyze_extended
from compiler.frontend import analyze_source
from compiler.ir.opcodes import Opcode
from compiler.ir.serializer import serialize
from compiler.runtime.runtime_layout import prepare
from compiler.tac.core_generator import CoreTacGenerator

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "core_tac"


def semantic(source: str):
    return analyze_extended(analyze_core(analyze_source(source)))


def program_for(source: str):
    result = semantic(source)
    assert not result.has_errors, [(d.code, d.line, d.column, d.message) for d in result.diagnostics]
    return CoreTacGenerator.generate(result, prepare(result))


def tac_for(source: str) -> str:
    return serialize(program_for(source))


def entry_lines(source: str) -> list[str]:
    """texto del codigo global, linea por linea y sin la sangria."""
    return [line.strip() for line in tac_for(source).split("\n\n")[0].splitlines()]


def function_named(program, label: str):
    return next(fn for fn in program.functions if fn.label == label)


def opcodes(instructions) -> list[Opcode]:
    return [i.opcode for i in instructions]


def label_at(lines: list[str], prefix: str) -> str:
    """nombre de la primera etiqueta marcada que empieza con `L_<prefix>_`."""
    return next(line.split()[1] for line in lines if line.startswith(f"LABEL L_{prefix}_"))
