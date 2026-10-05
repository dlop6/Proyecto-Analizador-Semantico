"""helpers compartidos de los tests del ir: semantica real, nada mockeado."""
from compiler.core_semantics import analyze as analyze_core
from compiler.extended_semantics import analyze as analyze_extended
from compiler.frontend import analyze_source
from compiler.runtime.runtime_layout import prepare


def semantic(source: str):
    return analyze_extended(analyze_core(analyze_source(source)))


def layout_for(source: str):
    result = semantic(source)
    assert not result.has_errors, [(d.code, d.line, d.column) for d in result.diagnostics]
    return result, prepare(result)


def function_named(layout, label: str):
    return next(fn for fn in layout.functions if fn.label == label)


def variable(result, scope_name: str, name: str):
    scope = next(s for s in result.symbols.all_scopes() if s.name == scope_name)
    return scope.symbols[name]
