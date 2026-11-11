"""
RegisterAllocator: reparte $t0-$t7 entre los temporales del ir y se encarga de que ningun
valor se pierda. solo conoce registros y homes de temporales; no sabe de opcodes ni de
variables (esas se cargan a $t8/$t9 por instruccion, fuera de aca).

mapeo con las operaciones del pdf (getReg, markDirty, release, flushLive,
invalidateCallerSaved, reset):

  get_reg(temp, load)        getReg: registro para el temporal; si no hay libres, spill LRU
  mark_dirty(temp)           markDirty: el registro tiene un valor mas nuevo que su home
  release(temp)              release: el temporal murio, se libera sin guardar
  flush_live()               flushLive: guarda los sucios en su home (los deja cacheados, limpios)
  invalidate_caller_saved()  invalidateCallerSaved: despues de una llamada o de una etiqueta
  reset(plan)                reset: funcion nueva, estado limpio

regla de bloques (la aplica el emisor, ver abi.py): antes de saltos, llamadas y etiquetas
se hace flush_live; despues de una llamada o de marcar una etiqueta se invalida todo, porque
ahi no se sabe que registros siguen valiendo. el home siempre queda como fuente de verdad.

adicion al contrato del pdf: instruction() fija los registros que una instruccion ya esta
usando, para que pedir el segundo operando no expulse al primero.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from compiler.backend.mips.builder import MipsBuilder
from compiler.backend.mips.frame_planner import FramePlan
from compiler.backend.mips.operands import FP, POOL, Mem, Reg
from compiler.ir.model import Temp

_Key = tuple[int, int]  # (unidad, indice): el t0 de una funcion no es el t0 de otra


def _key(temp: Temp) -> _Key:
    return (temp.unit, temp.index)


class RegisterAllocator:
    def __init__(self, builder: MipsBuilder, plan: FramePlan) -> None:
        self._builder = builder
        self.spills = 0    # cuantos temporales sucios se volcaron a su home por falta de registros
        self.reloads = 0   # cuantos se volvieron a cargar desde su home
        self.reset(plan)

    # ---------- estado de la funcion actual ----------

    def reset(self, plan: FramePlan) -> None:
        self._plan = plan
        self._unit: int | None = None
        self._in_reg: dict[_Key, Reg] = {}
        self._holder: dict[Reg, _Key] = {}
        self._dirty: set[Reg] = set()
        self._home_valid: set[_Key] = set()   # el home tiene el valor vigente
        self._live: set[_Key] = set()
        self._last_use: dict[Reg, int] = {}
        self._tick = 0
        self._pinned: set[Reg] | None = None  # None = fuera de instruction()

    # ---------- consultas (solo lectura) ----------

    def holding(self, temp: Temp) -> Reg | None:
        return self._in_reg.get(_key(temp))

    def is_dirty(self, temp: Temp) -> bool:
        reg = self.holding(temp)
        return reg is not None and reg in self._dirty

    @property
    def free_registers(self) -> tuple[Reg, ...]:
        return tuple(r for r in POOL if r not in self._holder)

    # ---------- operaciones del pdf ----------

    @contextmanager
    def instruction(self) -> Iterator[None]:
        """dentro del bloque, los registros que ya se entregaron no se pueden expulsar."""
        if self._pinned is not None:
            raise RuntimeError("instruction() no se puede anidar")
        self._pinned = set()
        try:
            yield
        finally:
            self._pinned = None

    def get_reg(self, temp: Temp, load: bool = True) -> Reg:
        """
        registro del temporal. load=True: se va a leer (si no esta en registro se carga de su
        home; si nunca tuvo valor es un error del lowerer). load=False: se va a escribir
        (es una definicion nueva y no se carga nada; el que llama marca mark_dirty despues).
        """
        key = self._check(temp)
        reg = self._in_reg.get(key)
        if reg is None:
            if load and key not in self._home_valid:
                raise ValueError(f"se lee t{temp.index} pero no tiene valor (nunca se definio o falto mark_dirty)")
            reg = self._take_register()
            self._in_reg[key], self._holder[reg] = reg, key
            if load:
                self._builder.emit("lw", reg, self._home(temp), comment=f"recarga t{temp.index}")
                self.reloads += 1
            else:
                # definicion nueva: lo que hubiera en el home ya no vale
                self._home_valid.discard(key)
        elif not load:
            self._home_valid.discard(key)
        self._live.add(key)
        self._touch(reg)
        return reg

    def mark_dirty(self, temp: Temp) -> None:
        key = self._check(temp)
        reg = self._in_reg.get(key)
        if reg is None:
            raise ValueError(f"t{temp.index} no esta en ningun registro, no se puede marcar sucio")
        self._dirty.add(reg)
        self._home_valid.discard(key)

    def release(self, temp: Temp) -> None:
        key = self._check(temp)
        if key not in self._live:
            raise ValueError(f"t{temp.index} no esta vivo (liberacion doble o nunca definido)")
        self._live.discard(key)
        self._home_valid.discard(key)
        reg = self._in_reg.pop(key, None)
        if reg is not None:
            self._drop(reg)

    def flush_live(self) -> None:
        """guarda en su home todo lo sucio. los registros quedan limpios pero siguen cacheados."""
        for reg in POOL:
            if reg in self._dirty:
                self._store(reg)

    def invalidate_caller_saved(self) -> None:
        """despues de una llamada o de una etiqueta ningun registro vale. exige haber hecho flush antes."""
        if self._dirty:
            raise ValueError("hay temporales sucios sin guardar: falta flush_live() antes de invalidar")
        for reg in tuple(self._holder):
            del self._in_reg[self._holder[reg]]
            self._drop(reg)

    # ---------- internos ----------

    def _check(self, temp: Temp) -> _Key:
        if not isinstance(temp, Temp):
            raise TypeError(f"el allocator solo maneja temporales, no {temp!r}")
        if self._unit is None:
            self._unit = temp.unit
        elif temp.unit != self._unit:
            raise ValueError(f"t{temp.index} es de la unidad {temp.unit} y se esta compilando la {self._unit}")
        self._home(temp)  # valida que el frame tenga lugar para este temporal
        return _key(temp)

    def _home(self, temp: Temp) -> Mem:
        return Mem(self._plan.temp_offset(temp.index), FP)

    def _take_register(self) -> Reg:
        free = self.free_registers
        if free:
            reg = free[0]
        else:
            candidates = [r for r in POOL if self._pinned is None or r not in self._pinned]
            if not candidates:
                raise RuntimeError("todos los registros estan fijados por la instruccion en curso")
            # lru; los ticks son unicos, el indice del registro solo desempata por claridad
            reg = min(candidates, key=lambda r: (self._last_use.get(r, 0), POOL.index(r)))
            if reg in self._dirty:
                self._store(reg)
                self.spills += 1
            del self._in_reg[self._holder[reg]]
            self._drop(reg)
        return reg

    def _store(self, reg: Reg) -> None:
        key = self._holder[reg]
        self._builder.emit("sw", reg, Mem(self._plan.temp_offset(key[1]), FP), comment=f"guarda t{key[1]}")
        self._dirty.discard(reg)
        self._home_valid.add(key)

    def _drop(self, reg: Reg) -> None:
        self._holder.pop(reg, None)
        self._dirty.discard(reg)
        self._last_use.pop(reg, None)

    def _touch(self, reg: Reg) -> None:
        self._tick += 1
        self._last_use[reg] = self._tick
        if self._pinned is not None:
            self._pinned.add(reg)
