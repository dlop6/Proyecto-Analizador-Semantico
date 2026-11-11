"""helper de los tests del backend: fuente -> (IRProgram, RuntimeLayout) con el pipeline real."""
from compiler.core_semantics import analyze as analyze_core
from compiler.extended_semantics import analyze as analyze_extended
from compiler.frontend import analyze_source
from compiler.runtime.runtime_layout import prepare
from compiler.tac.extended_generator import ExtendedTacGenerator


def ir_for(source: str):
    result = analyze_extended(analyze_core(analyze_source(source)))
    assert not result.has_errors, [(d.code, d.line, d.column, d.message) for d in result.diagnostics]
    layout = prepare(result)
    return ExtendedTacGenerator.generate(result, layout), layout


def function_named(program, label: str):
    return next(fn for fn in program.functions if fn.label == label)
