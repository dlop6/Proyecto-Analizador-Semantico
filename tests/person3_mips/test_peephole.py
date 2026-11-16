"""
optimizacion por mirilla: cada regla R1-R6 en un fragmento aislado (el algoritmo), los
casos en que NO debe aplicar (seguridad) y la equivalencia en mars antes/despues sobre
todos los programas de la suite (que optimiza el ensamblador real sin cambiar su salida).
"""
from pathlib import Path

import pytest

from compiler.backend.mips.builder import MipsBuilder
from compiler.backend.mips.extended_backend import ExtendedMipsBackend
from compiler.backend.mips.model import AssemblyInstruction, LabelDef
from compiler.backend.mips.operands import A0, T, V0, Imm, LabelRef
from compiler.backend.mips.peephole import RULES, PeepholeOptimizer
from compiler.compiler_service import compile_source

from tests.mips_base.mars_runner import run_mars
from tests.mips_base.pipeline import ir_for

T0, T1, T2 = T[0], T[1], T[2]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _program(*items):
    """main: <items> ; imprime $t0 ; termina. items son (opcode, operandos...) o un str (etiqueta)."""
    b = MipsBuilder()
    b.mark("main")
    for item in items:
        if isinstance(item, str):
            b.mark(item)
        else:
            b.emit(item[0], *item[1:])
    b.emit("move", A0, T0)
    b.emit("li", V0, Imm(1))
    b.emit("syscall")
    b.emit("li", V0, Imm(10))
    b.emit("syscall")
    return b.build()


def _ops(program):
    return [item.opcode if isinstance(item, AssemblyInstruction) else f"{item.name}:" for item in program.text]


def _run(program) -> str:
    result = run_mars(program.render())
    assert result.ok, result.raw
    return result.stdout


def _check(rule, items, expected_ops):
    """aplica la mirilla al fragmento: dispara `rule`, deja expected_ops y no cambia la salida en mars."""
    program = _program(*items)
    optimized, report = PeepholeOptimizer.optimize(program)
    assert report.applied[rule] >= 1, report.applied
    assert _ops(optimized) == expected_ops
    assert _run(optimized) == _run(program)
    return report


TAIL = ["move", "li", "syscall", "li", "syscall"]


def test_son_exactamente_seis_reglas_distintas():
    assert list(RULES) == ["R1", "R2", "R3", "R4", "R5", "R6"]


def test_r1_move_al_mismo_registro_se_elimina():
    _check("R1", [("li", T0, Imm(7)), ("move", T0, T0)], ["main:", "li", *TAIL])


def test_r2_move_repetido_adyacente_se_elimina():
    _check("R2", [("li", T1, Imm(5)), ("move", T0, T1), ("move", T0, T1)], ["main:", "li", "move", *TAIL])


def test_r2_no_aplica_si_hay_una_etiqueta_en_medio():
    program = _program(("li", T1, Imm(5)), ("move", T0, T1), "otra", ("move", T0, T1))
    optimized, report = PeepholeOptimizer.optimize(program)
    assert report.applied["R2"] == 0
    assert _ops(optimized) == _ops(program)


def test_r3_addiu_con_cero_es_un_move():
    _check("R3", [("li", T1, Imm(9)), ("addiu", T0, T1, Imm(0))], ["main:", "li", "move", *TAIL])


def test_r3_con_el_mismo_registro_queda_en_nada_por_r1():
    report = _check("R3", [("li", T0, Imm(9)), ("addiu", T0, T0, Imm(0))], ["main:", "li", *TAIL])
    assert report.applied["R1"] == 1   # una regla habilita la otra: se repite hasta el punto fijo


def test_r3_no_toca_un_addiu_distinto_de_cero():
    program = _program(("li", T1, Imm(9)), ("addiu", T0, T1, Imm(1)))
    assert PeepholeOptimizer.optimize(program)[1].total == 0


def test_r4_beq_con_el_mismo_registro_es_un_salto_incondicional():
    # el li 1 queda saltado: la salida es 2
    report = _check(
        "R4",
        [("li", T0, Imm(2)), ("beq", T1, T1, LabelRef("fin")), ("li", T0, Imm(1)), "fin"],
        ["main:", "li", "j", "li", "fin:", *TAIL],
    )
    assert report.applied["R6"] == 0


def test_r5_bne_con_el_mismo_registro_nunca_salta():
    _check(
        "R5",
        [("li", T0, Imm(3)), ("bne", T2, T2, LabelRef("lejos")), ("li", T0, Imm(4)), "lejos"],
        ["main:", "li", "li", "lejos:", *TAIL],
    )


def test_r6_salto_a_la_etiqueta_siguiente_se_elimina():
    _check("R6", [("li", T0, Imm(6)), ("j", LabelRef("sig")), "sig"], ["main:", "li", "sig:", *TAIL])


def test_r6_con_varias_etiquetas_seguidas():
    _check("R6", [("li", T0, Imm(6)), ("j", LabelRef("b")), "a", "b"], ["main:", "li", "a:", "b:", *TAIL])


def test_r6_no_aplica_si_hay_codigo_antes_de_la_etiqueta():
    program = _program(("j", LabelRef("fin")), ("li", T0, Imm(1)), "fin")
    optimized, report = PeepholeOptimizer.optimize(program)
    assert report.applied["R6"] == 0 and _ops(optimized) == _ops(program)


def test_las_etiquetas_y_la_seccion_de_datos_no_se_tocan():
    program = _program(("li", T0, Imm(1)), ("move", T0, T0), ("j", LabelRef("x")), "x")
    optimized, _ = PeepholeOptimizer.optimize(program)
    assert optimized.data == program.data
    assert [i for i in optimized.text if isinstance(i, LabelDef)] == [i for i in program.text if isinstance(i, LabelDef)]


def test_el_informe_cuenta_instrucciones_antes_y_despues():
    program = _program(("li", T0, Imm(1)), ("move", T0, T0), ("move", T1, T0), ("move", T1, T0))
    _, report = PeepholeOptimizer.optimize(program)
    assert (report.before, report.after, report.total) == (9, 7, 2)
    assert "R1x1" in report.summary() and "R2x1" in report.summary()


# ---------- sobre ensamblador real ----------

PROGRAMS = (
    sorted((FIXTURES / "mips_core").glob("*.cps"))
    + sorted((FIXTURES / "mips_extended").glob("*.cps"))
    + sorted((FIXTURES / "extended_tac" / "valid").glob("*.cps"))
)


@pytest.mark.parametrize("case", PROGRAMS, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_misma_salida_en_mars_antes_y_despues_de_la_mirilla(case):
    program, layout = ir_for(case.read_text(encoding="utf-8"))
    before = ExtendedMipsBackend.generate(program, layout)
    after, report = PeepholeOptimizer.optimize(before)
    assert report.after <= report.before
    a, b = run_mars(before.render(), max_steps=3_000_000), run_mars(after.render(), max_steps=3_000_000)
    assert a.ok and b.ok, (a.raw, b.raw)
    assert a.stdout == b.stdout


def test_la_mirilla_optimiza_el_ensamblador_generado_de_un_programa_real():
    result = compile_source((FIXTURES / "mips_extended" / "mirilla.cps").read_text(encoding="utf-8"))
    assert result.peephole.applied["R3"] >= 1     # x + 0
    assert result.peephole.applied["R6"] >= 1     # salto a la etiqueta siguiente
    assert result.peephole.after < result.peephole.before
    assert result.asm_text != result.asm_unoptimized
