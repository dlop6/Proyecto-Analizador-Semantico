"""
el backend core usa el RegisterAllocator real: con mas de 8 temporales vivos hace spill y
reload sin perder valores, y el analisis de vida evita guardar temporales que ya murieron.
"""
from compiler.backend.mips.liveness import dead_temps
from compiler.ir.model import Const, Label, TACInstruction, Temp
from compiler.ir.opcodes import Opcode
from compiler.runtime.storage import StorageKind, StorageRef
from compiler.types import BOOLEAN, INTEGER

from .support import assemble, backend_for, output


def _nested(depth: int) -> str:
    """(a*1) + ((a*2) + ((a*3) + ...)): cada producto queda vivo mientras se calcula el resto."""
    expr = f"(a * {depth})"
    for k in reversed(range(1, depth)):
        expr = f"(a * {k}) + ({expr})"
    return expr


def test_mas_de_ocho_temporales_vivos_hacen_spill_y_el_resultado_es_correcto():
    depth = 14
    source = f"let a: integer = 3; print({_nested(depth)});"
    backend = backend_for(source)
    asm = backend.build().render()
    assert backend.allocator.spills > 0 and backend.allocator.reloads > 0
    assert "recarga t" in asm
    assert output(source) == [str(3 * sum(range(1, depth + 1)))]


def test_presion_de_registros_dentro_de_una_funcion_recursiva():
    source = f"""
    function f(a: integer): integer {{
        if (a == 0) {{ return 0; }}
        return {_nested(10)} + f(a - 1);
    }}
    print(f(4));
    """
    backend = backend_for(source)
    backend.build()
    assert backend.allocator.spills > 0
    assert output(source) == [str(sum(range(1, 11)) * (4 + 3 + 2 + 1))]


def test_dos_funciones_no_comparten_estado_del_allocator():
    # el t0 de cada funcion vive en su propio frame; si se mezclaran, los resultados se cruzarian
    assert output("""
    function uno(x: integer): integer { return (x + 1) * (x + 2); }
    function dos(y: integer): integer { return uno(y) - uno(y - 1); }
    print(dos(5)); print(uno(5) + dos(1));
    """) == ["12", "46"]   # 42 - 30 ; 42 + (6 - 2)


def test_temporales_muertos_no_se_guardan_en_su_home():
    # x + 1 se usa una sola vez: no hay motivo para volcarlo a memoria en la etiqueta del bucle
    asm = assemble("let x: integer = 0; while (x < 10) { x = x + 1; } print(x);")
    assert "guarda t" not in asm


def test_temporal_vivo_a_traves_de_una_llamada_si_se_guarda():
    asm = assemble("""
    function id(v: integer): integer { return v; }
    let a: integer = 2;
    print(a * 3 + id(4));
    """)
    assert "guarda t" in asm   # a*3 sigue vivo mientras corre id(4)


# ----------------------------------------------------------------------
# analisis de vida (unidad)
# ----------------------------------------------------------------------

def _t(i, kind=INTEGER):
    return Temp(i, kind)


def _bin(result, a, b, op="+"):
    return TACInstruction(Opcode.BIN, result, a, b, (("op", op),))


X = StorageRef(StorageKind.GLOBAL, 0, name="x")


def test_un_temporal_muere_en_su_ultimo_uso():
    code = (_bin(_t(0), Const(1, INTEGER), Const(2, INTEGER)), TACInstruction(Opcode.MOV, X, _t(0)))
    assert dead_temps(code) == [(), (_t(0),)]


def test_definicion_que_nadie_lee_muere_ahi_mismo():
    code = (_bin(_t(0), Const(1, INTEGER), Const(2, INTEGER)),)
    assert dead_temps(code) == [(_t(0),)]


def test_un_temporal_usado_en_la_condicion_de_un_bucle_no_muere_dentro_del_bucle():
    loop, end = Label("L_while_cond_0"), Label("L_while_end_1")
    code = (
        TACInstruction(Opcode.MOV, _t(0), Const(5, INTEGER)),             # 0: t0 vive en todo el bucle
        TACInstruction(Opcode.LABEL, arg1=loop),                          # 1
        _bin(_t(1, BOOLEAN), X, _t(0), "<"),                              # 2
        TACInstruction(Opcode.IF_FALSE, arg1=_t(1, BOOLEAN), arg2=end),   # 3: t1 muere aca
        _bin(_t(2), X, Const(1, INTEGER)),                                # 4
        TACInstruction(Opcode.MOV, X, _t(2)),                             # 5: t2 muere aca
        TACInstruction(Opcode.GOTO, arg1=loop),                           # 6
        TACInstruction(Opcode.LABEL, arg1=end),                           # 7
    )
    dead = dead_temps(code)
    assert all(_t(0) not in d for d in dead)
    assert dead[3] == (_t(1, BOOLEAN),) and dead[5] == (_t(2),)


def test_valor_que_llega_por_las_dos_ramas_de_un_cortocircuito():
    end = Label("L_and_end_0")
    p = _t(0, BOOLEAN)
    code = (
        TACInstruction(Opcode.MOV, p, X),
        TACInstruction(Opcode.IF_FALSE, arg1=p, arg2=end),
        TACInstruction(Opcode.MOV, p, Const(True, BOOLEAN)),
        TACInstruction(Opcode.LABEL, arg1=end),
        TACInstruction(Opcode.MOV, X, p),
    )
    dead = dead_temps(code)
    assert dead[1] == () and dead[2] == () and dead[4] == (p,)


def test_lo_que_lee_un_catch_no_muere_en_ninguna_parte_de_la_unidad():
    handler, after = Label("L_try_handler_0"), Label("L_try_end_1")
    code = (
        TACInstruction(Opcode.MOV, _t(0), Const(1, INTEGER)),
        TACInstruction(Opcode.TRY_BEGIN, arg1=handler),
        TACInstruction(Opcode.PRINT, arg1=_t(0)),
        TACInstruction(Opcode.TRY_END),
        TACInstruction(Opcode.GOTO, arg1=after),
        TACInstruction(Opcode.LABEL, arg1=handler),
        TACInstruction(Opcode.PRINT, arg1=_t(0)),
        TACInstruction(Opcode.LABEL, arg1=after),
    )
    assert all(_t(0) not in d for d in dead_temps(code))


def test_en_arr_set_el_arreglo_del_resultado_se_lee():
    arr = _t(0)
    code = (
        TACInstruction(Opcode.ARR_SET, arr, Const(0, INTEGER), Const(9, INTEGER)),
        TACInstruction(Opcode.MOV, X, arr),
    )
    # si ARR_SET contara como escritura, arr estaria muerto antes y se perderia el valor
    assert dead_temps(code) == [(), (arr,)]
