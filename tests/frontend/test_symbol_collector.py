"""
tests de compiler/symbol_collector.py: predeclaracion, duplicados, scopes de cada
construccion (for/foreach/switch/catch), this, herencia circular y constructor.
el bloque mas grande del frontend, cubre las secciones D, E y H del plan.
"""
from antlr4 import CommonTokenStream, InputStream

from compiler.ast_builder import AstBuilder
from compiler.diagnostics import DiagnosticBag
from compiler.generated import CompiscriptLexer, CompiscriptParser
from compiler.scopes import ScopeKind
from compiler.symbol_collector import collect_symbols


def analyze(source: str):
    lexer = CompiscriptLexer(InputStream(source))
    parser = CompiscriptParser(CommonTokenStream(lexer))
    tree = parser.program()
    diag = DiagnosticBag()
    ast = AstBuilder(diag).visit(tree)
    table = collect_symbols(ast, diag)
    return table, diag


def codes_of(diag) -> list[str]:
    return [d.code for d in diag]


# ---------- predeclaracion (gate a) ----------

def test_recursion_directa_sin_diagnosticos():
    _, diag = analyze("function fact(n: integer): integer { return fact(n - 1); }")
    assert list(diag) == []


def test_recursion_mutua_sin_diagnosticos():
    _, diag = analyze(
        "function f(): integer { return g(); } "
        "function g(): integer { return f(); }"
    )
    assert list(diag) == []


def test_clase_usada_como_tipo_antes_de_declararse():
    _, diag = analyze("let x: Nodo; class Nodo { let v: integer; }")
    assert "CPS-030" not in codes_of(diag)


def test_herencia_con_forward_reference():
    _, diag = analyze("class A : B {} class B {}")
    assert "CPS-023" not in codes_of(diag)
    assert "CPS-031" not in codes_of(diag)


# ---------- duplicados (caso invalido) ----------

def test_variable_duplicada_reporta_linea_de_la_segunda():
    _, diag = analyze("let x: integer = 1;\nlet x: integer = 2;")
    dups = [d for d in diag if d.code == "CPS-020"]
    assert len(dups) == 1
    assert dups[0].line == 2


def test_let_y_const_mismo_nombre_es_duplicado():
    _, diag = analyze("let x: integer = 1;\nconst x: integer = 2;")
    assert "CPS-020" in codes_of(diag)


def test_dos_funciones_mismo_nombre():
    _, diag = analyze("function f() {} function f() {}")
    assert "CPS-020" in codes_of(diag)


def test_dos_clases_mismo_nombre():
    _, diag = analyze("class A {} class A {}")
    assert "CPS-020" in codes_of(diag)


def test_dos_atributos_mismo_nombre_en_clase():
    _, diag = analyze("class A { let x: integer; let x: integer; }")
    assert "CPS-021" in codes_of(diag)


def test_dos_constructores_en_una_clase():
    _, diag = analyze(
        "class A { function constructor() {} function constructor() {} }"
    )
    assert "CPS-021" in codes_of(diag)


def test_parametro_duplicado():
    _, diag = analyze("function f(a: integer, a: integer) {}")
    assert "CPS-022" in codes_of(diag)


# ---------- no duplicados: shadowing legal ----------

def test_shadowing_en_bloque_anidado():
    _, diag = analyze("let x: integer = 1; { let x: integer = 2; }")
    assert list(diag) == []


def test_shadowing_dentro_de_funcion():
    _, diag = analyze("let x: integer = 1; function f() { let x: integer = 2; }")
    assert list(diag) == []


def test_shadowing_en_cuerpo_del_for():
    _, diag = analyze("for (let i: integer = 0; i < 3; i = i + 1) { let i: integer = 1; }")
    assert list(diag) == []


def test_funcion_con_parametro_igual_a_nombre_es_duplicado():
    # a diferencia del bloque, el cuerpo de la funcion REUSA el scope de parametros
    _, diag = analyze("function f(x: integer) { let x: integer = 1; }")
    assert "CPS-020" in codes_of(diag)


# ---------- scopes: for / foreach / catch / switch ----------

def test_scope_del_for_variable_no_visible_fuera():
    table, diag = analyze(
        "for (let i: integer = 0; i < 3; i = i + 1) {} print(i);"
    )
    # el frontend no valida identificadores en expresiones (eso es de la semantica core),
    # pero podemos verificar la ESTRUCTURA del arbol de scopes directamente
    scope_names = [s.name for s in table.all_scopes()]
    assert "loop" in scope_names
    loop_scope = next(s for s in table.all_scopes() if s.kind == ScopeKind.LOOP)
    assert "i" in loop_scope.symbols
    assert "i" not in table.global_scope.symbols


def test_for_produce_exactamente_loop_y_block():
    table, _ = analyze("for (let i: integer = 0;;) { let j: integer = 1; }")
    kinds = [s.kind for s in table.all_scopes() if s.kind in (ScopeKind.LOOP, ScopeKind.BLOCK)]
    assert kinds == [ScopeKind.LOOP, ScopeKind.BLOCK]


def test_foreach_variable_en_loop_scope_tipo_diferido():
    table, diag = analyze("let a: integer[] = []; foreach (x in a) { print(x); }")
    assert list(diag) == []
    loop_scope = next(s for s in table.all_scopes() if s.kind == ScopeKind.LOOP)
    assert "x" in loop_scope.symbols
    assert loop_scope.symbols["x"].type is None  # contrato: la semantica core lo completa
    assert loop_scope.symbols["x"].is_iteration_var is True


def test_catch_variable_visible_dentro_no_fuera():
    _, diag = analyze("try {} catch (e) { print(e); }")
    assert list(diag) == []


def test_catch_redeclarar_parametro_en_cuerpo_es_duplicado():
    _, diag = analyze("try {} catch (e) { let e: integer = 1; }")
    assert "CPS-020" in codes_of(diag)


def test_switch_comparte_scope_entre_cases_duplicado():
    _, diag = analyze(
        "switch (1) { case 1: let x: integer = 1; case 2: let x: integer = 2; }"
    )
    assert "CPS-020" in codes_of(diag)


def test_switch_variable_visible_en_otro_case():
    _, diag = analyze(
        "switch (1) { case 1: let x: integer = 1; case 2: x = 2; }"
    )
    assert "CPS-020" not in codes_of(diag)


# ---------- this ----------

def test_this_dentro_de_metodo_resuelve_bien():
    table, diag = analyze("class A { function m() { print(this); } }")
    assert list(diag) == []


def test_this_en_funcion_libre_es_error():
    _, diag = analyze("function f() { print(this); }")
    assert "CPS-040" in codes_of(diag)


def test_this_en_top_level_es_error():
    _, diag = analyze("print(this);")
    assert "CPS-040" in codes_of(diag)


# ---------- herencia circular ----------

def test_herencia_circular_detectada_sin_colgarse():
    _, diag = analyze("class A : B {} class B : A {}")
    assert "CPS-031" in codes_of(diag)


def test_herencia_circular_de_tres_clases():
    _, diag = analyze("class A : B {} class B : C {} class C : A {}")
    assert "CPS-031" in codes_of(diag)


# ---------- constructor ----------

def test_constructor_con_tipo_de_retorno_es_error():
    _, diag = analyze("class A { function constructor(): integer {} }")
    assert "CPS-032" in codes_of(diag)


def test_constructor_sin_tipo_de_retorno_no_reporta():
    _, diag = analyze("class A { function constructor() {} }")
    assert "CPS-032" not in codes_of(diag)


# ---------- break / continue / return fuera de contexto ----------

def test_break_fuera_de_bucle():
    _, diag = analyze("break;")
    assert "CPS-012" in codes_of(diag)


def test_break_dentro_de_bucle_no_reporta():
    _, diag = analyze("while (true) { break; }")
    assert "CPS-012" not in codes_of(diag)


def test_continue_fuera_de_bucle():
    _, diag = analyze("function f() { continue; }")
    assert "CPS-013" in codes_of(diag)


def test_return_fuera_de_funcion():
    _, diag = analyze("return 1;")
    assert "CPS-014" in codes_of(diag)


def test_return_dentro_de_funcion_no_reporta():
    _, diag = analyze("function f(): integer { return 1; }")
    assert "CPS-014" not in codes_of(diag)


def test_const_sin_inicializador_es_inalcanzable_por_gramatica():
    """
    documenta que CPS-011 no se puede disparar con esta gramatica: 'const x: integer;'
    es rechazado por antlr antes de llegar al symbol_collector porque constantDeclaration
    exige '=' expression obligatorio.
    """
    lexer = CompiscriptLexer(InputStream("const x: integer;"))
    parser = CompiscriptParser(CommonTokenStream(lexer))
    from antlr4.error.ErrorListener import ErrorListener

    class Collector(ErrorListener):
        def __init__(self):
            self.errors = []

        def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
            self.errors.append(msg)

    parser.removeErrorListeners()
    listener = Collector()
    parser.addErrorListener(listener)
    parser.program()
    assert len(listener.errors) >= 1


# ---------- parametros con is_param ----------

def test_parametros_quedan_marcados_is_param():
    table, _ = analyze("function f(a: integer, b: string) { print(a); }")
    fn_scope = next(s for s in table.all_scopes() if s.kind == ScopeKind.FUNCTION)
    assert fn_scope.symbols["a"].is_param is True
    assert fn_scope.symbols["b"].is_param is True
