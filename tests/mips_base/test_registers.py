"""register allocator: reglas (unitarias) y comportamiento real (ejecutado en mars)."""
import pytest

from compiler.backend.mips.builder import MipsBuilder
from compiler.backend.mips.frame_planner import FramePlanner
from compiler.backend.mips.operands import A0, FP, POOL, RA, SP, T, V0, Imm, LabelRef
from compiler.backend.mips.register_allocator import RegisterAllocator
from compiler.ir.model import IRFragment, Temp
from compiler.types import BOOLEAN, INTEGER

from .mars_runner import run_mars


def temp(index, unit=0, type_=INTEGER):
    return Temp(index, type_, unit)


def make(created=12):
    builder = MipsBuilder()
    plan = FramePlanner.plan_entry(IRFragment((), peak_temps=created, created_temps=created))
    builder.mark("main")
    builder.emit("move", FP, SP)
    builder.emit("addi", SP, SP, Imm(-plan.size))
    return builder, RegisterAllocator(builder, plan), plan


def finish(builder):
    builder.emit("li", V0, Imm(10))
    builder.emit("syscall")
    return builder.render()


def define(alloc, t, value, builder):
    reg = alloc.get_reg(t, load=False)
    builder.emit("li", reg, Imm(value))
    alloc.mark_dirty(t)
    return reg


def print_a0(builder):
    builder.emit("li", V0, Imm(1))
    builder.emit("syscall")


# ---------- reglas ----------

def test_los_registros_entregados_son_solo_del_pool():
    builder, alloc, _ = make(12)
    seen = set()
    for i in range(12):
        seen.add(define(alloc, temp(i), i, builder))
    assert seen <= set(POOL) and len(seen) == 8


def test_sin_aliasing_cada_registro_tiene_un_solo_dueño():
    builder, alloc, _ = make(12)
    for i in range(12):
        define(alloc, temp(i), i, builder)
        held = [alloc.holding(temp(j)) for j in range(i + 1)]
        regs = [r for r in held if r is not None]
        assert len(regs) == len(set(regs))


def test_spill_lru_expulsa_al_menos_usado_y_vuelca_si_esta_sucio():
    builder, alloc, _ = make(10)
    for i in range(8):
        define(alloc, temp(i), i, builder)
    alloc.get_reg(temp(0))                         # t0 queda como el mas reciente
    define(alloc, temp(8), 8, builder)             # t1 era el menos usado
    assert alloc.holding(temp(1)) is None and alloc.holding(temp(0)) is not None
    assert alloc.spills == 1


def test_expulsar_un_limpio_no_genera_store():
    builder, alloc, _ = make(10)
    for i in range(8):
        define(alloc, temp(i), i, builder)
    alloc.flush_live()
    before = builder.render().count("sw ")
    define(alloc, temp(8), 8, builder)
    assert builder.render().count("sw ") == before and alloc.spills == 0


def test_instruction_fija_los_registros_en_uso():
    builder, alloc, _ = make(10)
    for i in range(8):
        define(alloc, temp(i), i, builder)
    with alloc.instruction():
        first = alloc.get_reg(temp(7))             # el mas reciente: lru lo salvaria igual
        second = alloc.get_reg(temp(0))            # el mas viejo
        third = alloc.get_reg(temp(8), load=False) # fuerza una expulsion
    assert len({first, second, third}) == 3
    assert alloc.holding(temp(7)) == first and alloc.holding(temp(0)) == second


def test_instruction_no_se_anida():
    _, alloc, _ = make()
    with alloc.instruction():
        with pytest.raises(RuntimeError):
            with alloc.instruction():
                pass


def test_leer_un_temporal_sin_valor_falla():
    _, alloc, _ = make()
    with pytest.raises(ValueError, match="no tiene valor"):
        alloc.get_reg(temp(0))


def test_olvidar_mark_dirty_se_detecta_al_releer_tras_expulsion():
    builder, alloc, _ = make(10)
    alloc.get_reg(temp(0), load=False)             # se escribio pero nunca se marco sucio
    for i in range(1, 9):
        define(alloc, temp(i), i, builder)         # fuerza a expulsar t0
    with pytest.raises(ValueError, match="no tiene valor"):
        alloc.get_reg(temp(0))


def test_release_doble_o_de_un_temporal_desconocido_falla():
    builder, alloc, _ = make()
    define(alloc, temp(0), 1, builder)
    alloc.release(temp(0))
    with pytest.raises(ValueError):
        alloc.release(temp(0))
    with pytest.raises(ValueError):
        alloc.release(temp(5))


def test_release_libera_el_registro_sin_guardar():
    builder, alloc, _ = make()
    reg = define(alloc, temp(0), 1, builder)
    alloc.release(temp(0))
    assert reg in alloc.free_registers and "sw " not in builder.render()
    with pytest.raises(ValueError):
        alloc.get_reg(temp(0))                     # ya no tiene valor


def test_invalidar_con_sucios_pendientes_falla():
    builder, alloc, _ = make()
    define(alloc, temp(0), 1, builder)
    with pytest.raises(ValueError, match="flush_live"):
        alloc.invalidate_caller_saved()
    alloc.flush_live()
    alloc.invalidate_caller_saved()
    assert alloc.holding(temp(0)) is None and len(alloc.free_registers) == 8


def test_mark_dirty_de_un_temporal_fuera_de_registro_falla():
    _, alloc, _ = make()
    with pytest.raises(ValueError):
        alloc.mark_dirty(temp(0))


def test_temporal_de_otra_unidad_o_sin_home_falla():
    builder, alloc, _ = make(4)
    define(alloc, temp(0, unit=0), 1, builder)
    with pytest.raises(ValueError, match="unidad"):
        alloc.get_reg(temp(1, unit=3), load=False)
    with pytest.raises(ValueError):
        alloc.get_reg(temp(9), load=False)          # el frame solo reservo 4 homes
    with pytest.raises(TypeError):
        alloc.get_reg("t0")


def test_el_tipo_del_temporal_no_cambia_su_identidad():
    builder, alloc, _ = make()
    reg = define(alloc, temp(0, type_=BOOLEAN), 1, builder)
    assert alloc.get_reg(temp(0, type_=INTEGER)) == reg


def test_reset_deja_el_estado_limpio_entre_funciones():
    builder, alloc, plan = make()
    define(alloc, temp(0), 1, builder)
    alloc.reset(plan)
    assert alloc.holding(temp(0)) is None and len(alloc.free_registers) == 8
    alloc.get_reg(temp(0, unit=7), load=False)      # otra unidad ya es valida tras el reset


def test_es_determinista():
    def run():
        builder, alloc, _ = make(12)
        for i in range(12):
            define(alloc, temp(i), i, builder)
        for i in range(12):
            with alloc.instruction():
                alloc.get_reg(temp(i))
        return finish(builder)

    assert run() == run()


# ---------- ejecutado en mars ----------

def test_mas_de_ocho_temporales_vivos_no_pierden_datos_en_mars():
    builder, alloc, _ = make(12)
    for i in range(12):
        define(alloc, temp(i), 10 * i + 1, builder)
    builder.emit("li", A0, Imm(0))
    for i in range(12):
        with alloc.instruction():
            reg = alloc.get_reg(temp(i))
            builder.emit("add", A0, A0, reg)
    print_a0(builder)
    result = run_mars(finish(builder))
    assert result.ok and result.stdout == str(sum(10 * i + 1 for i in range(12)))
    assert alloc.spills > 0 and alloc.reloads > 0


def test_los_valores_sobreviven_a_una_llamada_que_pisa_todos_los_t_en_mars():
    builder, alloc, _ = make(10)
    for i in range(10):
        define(alloc, temp(i), 100 + i, builder)
    alloc.flush_live()
    builder.emit("jal", LabelRef("clobber"))
    alloc.invalidate_caller_saved()
    builder.emit("li", A0, Imm(0))
    for i in range(10):
        with alloc.instruction():
            builder.emit("add", A0, A0, alloc.get_reg(temp(i)))
    print_a0(builder)
    builder.emit("li", V0, Imm(10))
    builder.emit("syscall")
    builder.mark("clobber")
    for reg in T:
        builder.emit("li", reg, Imm(-1))
    builder.emit("jr", RA)
    result = run_mars(builder.render())
    assert result.ok and result.stdout == str(sum(100 + i for i in range(10)))


def test_redefinir_un_temporal_descarta_el_valor_viejo_en_mars():
    builder, alloc, _ = make()
    define(alloc, temp(0), 5, builder)
    define(alloc, temp(0), 9, builder)              # t0 se reusa para otro valor
    alloc.flush_live()
    alloc.invalidate_caller_saved()
    builder.emit("move", A0, alloc.get_reg(temp(0)))
    print_a0(builder)
    assert run_mars(finish(builder)).stdout == "9"
