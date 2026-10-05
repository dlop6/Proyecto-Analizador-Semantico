"""funciones, parametros, return, llamadas, recursion y funciones anidadas con static link."""
from compiler.ir.model import Label
from compiler.ir.opcodes import Opcode
from compiler.runtime.storage import StorageKind

from .conftest import entry_lines, function_named, opcodes, program_for, tac_for


def test_funcion_abre_y_cierra_con_su_etiqueta_y_frame():
    program = program_for("function f(a: integer, b: integer): integer { let c: integer = a; return c; }")
    fn = function_named(program, "fn::f")
    assert fn.instructions[0].opcode is Opcode.FUNC_BEGIN and fn.instructions[0].meta("frame") == 3
    assert fn.instructions[-1].opcode is Opcode.FUNC_END


def test_parametros_no_se_redeclaran():
    fn = function_named(program_for("function f(a: integer): integer { return a; }"), "fn::f")
    assert opcodes(fn.instructions) == [Opcode.FUNC_BEGIN, Opcode.RETURN, Opcode.FUNC_END]


def test_funcion_sin_return_final_recibe_return_vacio():
    fn = function_named(program_for("function f() { print(1); }"), "fn::f")
    assert opcodes(fn.instructions)[-2:] == [Opcode.RETURN, Opcode.FUNC_END]
    assert fn.instructions[-2].arg1 is None


def test_funcion_con_return_final_no_duplica_el_return():
    fn = function_named(program_for("function f(): integer { return 1; }"), "fn::f")
    assert opcodes(fn.instructions).count(Opcode.RETURN) == 1


def test_return_vacio():
    assert "  RETURN\n" in tac_for("function f() { return; }")


def test_funciones_no_interrumpen_el_codigo_global():
    lines = entry_lines("print(1); function f() { print(2); } print(3);")
    assert lines == ["PRINT 1", "PRINT 3"]


def test_cada_funcion_arranca_sus_temporales_en_t0():
    program = program_for("function f(a: integer): integer { return a + 1; } "
                          "function g(a: integer): integer { return a * 2; } print(f(1) + g(2));")
    for label in ("fn::f", "fn::g"):
        fn = function_named(program, label)
        assert fn.instructions[1].result.name == "t0"
        assert fn.peak_temps == fn.instructions[-1].meta("temps") == 1


# ----------------------------------------------------------------------
# llamadas
# ----------------------------------------------------------------------


def test_llamada_como_sentencia_no_pide_temporal():
    program = program_for("function f(): integer { return 1; } f();")
    call = next(i for i in program.entry.instructions if i.opcode is Opcode.CALL)
    assert call.result is None and program.entry.created_temps == 0


def test_llamada_como_valor_usa_temporal():
    assert entry_lines("function f(): integer { return 1; } let x: integer = f();") == [
        "CALL t0, fn::f, argc=0", "MOV x@global[0], t0",
    ]


def test_argumentos_izquierda_a_derecha():
    lines = entry_lines("function f(a: integer, b: integer, c: integer) { } "
                        "let x: integer = 1; f(x, x + 1, 3);")
    assert lines[1:] == ["ARG x@global[0]", "t0 = BIN +, x@global[0], 1", "ARG t0", "ARG 3",
                         "CALL fn::f, argc=3"]


def test_llamada_anidada_como_argumento():
    lines = entry_lines("function f(a: integer, b: integer): integer { return a; } "
                        "let r: integer = f(1, f(2, 3));")
    assert lines == ["ARG 1", "ARG 2", "ARG 3", "CALL t0, fn::f, argc=2", "ARG t0",
                     "CALL t0, fn::f, argc=2", "MOV r@global[0], t0"]


def test_funcion_void_usada_como_valor_da_null():
    lines = entry_lines("function f() { } let y = f(); print(f());")
    assert lines == ["CALL fn::f, argc=0", "MOV y@global[0], null", "CALL fn::f, argc=0", "PRINT null"]


def test_llamada_a_funcion_declarada_despues():
    program = program_for("print(f()); function f(): integer { return 1; }")
    call = next(i for i in program.entry.instructions if i.opcode is Opcode.CALL)
    assert call.arg1 == Label("fn::f")


# ----------------------------------------------------------------------
# recursion
# ----------------------------------------------------------------------


def test_recursion_es_un_call_a_la_misma_etiqueta():
    fn = function_named(program_for(
        "function factorial(n: integer): integer { if (n <= 1) { return 1; } return n * factorial(n - 1); }"
    ), "fn::factorial")
    calls = [i for i in fn.instructions if i.opcode is Opcode.CALL]
    assert [c.arg1.name for c in calls] == ["fn::factorial"]
    assert calls[0].meta("link") is None


def test_recursion_doble():
    fn = function_named(program_for(
        "function fib(n: integer): integer { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); }"
    ), "fn::fib")
    assert [i.arg1.name for i in fn.instructions if i.opcode is Opcode.CALL] == ["fn::fib", "fn::fib"]


def test_recursion_mutua():
    program = program_for(
        "function par(n: integer): boolean { if (n == 0) { return true; } return impar(n - 1); }"
        "function impar(n: integer): boolean { if (n == 0) { return false; } return par(n - 1); }"
    )
    assert any(i.opcode is Opcode.CALL and i.arg1.name == "fn::impar" for i in function_named(program, "fn::par").instructions)
    assert any(i.opcode is Opcode.CALL and i.arg1.name == "fn::par" for i in function_named(program, "fn::impar").instructions)


def test_recursion_en_funcion_anidada():
    text = tac_for("function f(): integer { function g(n: integer): integer { if (n == 0) { return 0; } "
                   "return g(n - 1); } return g(3); }")
    assert "CALL t0, fn::f.g, argc=1" in text


# ----------------------------------------------------------------------
# funciones anidadas
# ----------------------------------------------------------------------


def test_anidada_se_emite_antes_que_la_que_la_contiene():
    program = program_for("function f(): integer { function g(): integer { return 1; } return g(); }")
    assert [fn.label for fn in program.functions] == ["fn::f.g", "fn::f"]


def test_anidada_sin_captura_no_usa_static_link():
    program = program_for("function f(): integer { function g(): integer { return 1; } return g(); }")
    call = next(i for i in function_named(program, "fn::f").instructions if i.opcode is Opcode.CALL)
    assert call.meta("link") is None


def test_anidada_con_captura_lee_nonlocal_y_recibe_link():
    program = program_for("function f(): integer { let x: integer = 1; "
                          "function g(): integer { return x; } return g(); }")
    ret = next(i for i in function_named(program, "fn::f.g").instructions if i.opcode is Opcode.RETURN)
    assert ret.arg1.kind is StorageKind.NONLOCAL and ret.arg1.lexical_depth == 1
    call = next(i for i in function_named(program, "fn::f").instructions if i.opcode is Opcode.CALL)
    assert call.meta("link") == 0


def test_anidada_escribe_variable_del_frame_externo():
    text = tac_for("function f(): integer { let x: integer = 1; "
                   "function g() { x = x + 1; } g(); return x; }")
    assert "MOV x@frame^1[0], t0" in text


def test_dos_niveles_de_anidamiento():
    text = tac_for("function a(): integer { let x: integer = 1; function b(): integer { "
                   "function c(): integer { return x; } return c(); } return b(); }")
    assert "RETURN x@frame^2[0]" in text
    assert "CALL t0, fn::a.b.c, argc=0, link=0" in text
    assert "CALL t0, fn::a.b, argc=0, link=0" in text


def test_llamada_entre_hermanas_anidadas_pasa_el_frame_del_padre():
    text = tac_for("function f(): integer { let x: integer = 1; "
                   "function g(): integer { return x; } "
                   "function h(): integer { return g(); } return h(); }")
    # h llama a g (que necesita el frame de f): sube un salto desde su frame
    assert "CALL t0, fn::f.g, argc=0, link=1" in text
