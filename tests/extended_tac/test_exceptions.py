"""try/catch: TRY_BEGIN, TRY_END, GOTO, handler con CATCH y etiqueta de salida."""
from .conftest import entry_lines, tac_for

SOURCE = """
let a: integer[] = [1];
try { print(a[3]); } catch (err) { print(err); }
print("fin");
"""


def test_forma_completa_del_try_catch():
    assert entry_lines(SOURCE)[3:] == [
        "TRY_BEGIN L_try_handler_0",
        "t1 = ARR_GET a@global[0], 3",
        "PRINT t1",
        "TRY_END",
        "GOTO L_try_end_1",
        "LABEL L_try_handler_0",
        "CATCH err@global[1]",
        "PRINT err@global[1]",
        "LABEL L_try_end_1",
        'PRINT "fin"',
    ]


def test_la_variable_del_catch_dentro_de_una_funcion_vive_en_el_frame():
    assert "CATCH e@frame[0]" in tac_for("function f() { try { print(1); } catch (e) { print(e); } }")


def test_try_anidado_usa_etiquetas_distintas():
    lines = entry_lines("try { try { print(1); } catch (a) { print(a); } } catch (b) { print(b); }")
    assert lines.count("TRY_END") == 2
    handlers = [line for line in lines if line.startswith("LABEL L_try_handler")]
    assert len(set(handlers)) == 2


def test_try_dentro_de_un_bucle_respeta_break():
    lines = entry_lines("while (true) { try { break; } catch (e) { print(e); } }")
    assert "GOTO L_while_end_1" in lines
