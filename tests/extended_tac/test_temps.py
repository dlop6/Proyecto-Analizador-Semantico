"""reciclaje de temporales en los constructos extendidos."""
from compiler.ir.model import Temp

from .conftest import FIXTURES, entry_lines, program_for


def test_ninguna_unidad_termina_con_temporales_vivos_en_las_fixtures():
    # el builder rechaza cerrar una unidad con temporales vivos: si genera, se cumplio
    for path in sorted((FIXTURES / "valid").glob("*.cps")):
        program_for(path.read_text(encoding="utf-8"))


def test_los_temporales_del_foreach_siguen_vivos_durante_el_cuerpo():
    # el cuerpo pide temporales nuevos sin pisar arreglo (t0), indice (t1) ni longitud (t2)
    lines = entry_lines("let a: integer[] = [1]; foreach (x in a) { let y: integer = x + x * 2; }")
    body = lines[lines.index("MOV x@global[1], t4") + 1:lines.index("LABEL L_foreach_step_1")]
    used = {token.rstrip(",") for line in body for token in line.split() if token.startswith("t")}
    assert used
    assert not used & {"t0", "t1", "t2"}


def test_arreglos_y_objetos_reciclan_temporales():
    lines = entry_lines("""
    class P { let v: integer = 0; }
    let a: P = new P();
    let b: P = new P();
    let c: integer[] = [1];
    let d: integer[] = [2];
    """)
    created = [line.split()[0] for line in lines if " = NEW_" in line]
    assert created == ["t0", "t0", "t0", "t0"]


def test_pico_de_temporales_acotado_en_una_cadena_de_accesos():
    program = program_for("""
    class N { let v: integer = 1; }
    let n: N = new N();
    let s: integer = n.v + n.v + n.v + n.v + n.v;
    """)
    names = {
        op.index for i in program.entry.instructions for op in (i.result, i.arg1, i.arg2) if isinstance(op, Temp)
    }
    assert len(names) <= 4
