"""
reparte y recicla temporales (t0, t1, ...) de UNA unidad de codigo: una funcion o el
codigo global. el builder crea uno nuevo por unidad, asi dos funciones nunca comparten
estado de temporales y cada una arranca de t0.

reciclaje: al liberar un temporal su numero vuelve a un pool de su categoria y el
proximo acquire de esa categoria reusa el numero libre mas bajo. un temporal nunca se
entrega dos veces mientras sigue vivo.

categorias (decision de diseño): el pdf pide pool "por tipo". con un pool por tipo
exacto casi no habria reciclaje (cada clase o arreglo distinto tendria el suyo), asi
que el pool es por categoria de valor: int, bool, string y ref (objetos, arreglos y null).
"""
from __future__ import annotations

from compiler.ir.model import Temp
from compiler.types import BOOLEAN, INTEGER, STRING, ArrayType, ClassType, EmptyArrayType, NullType, Type


class TempError(Exception):
    """uso invalido de temporales: doble liberacion, temporal ajeno o tipo sin categoria."""


def temp_category(type_: Type) -> str:
    if type_ == INTEGER:
        return "int"
    if type_ == BOOLEAN:
        return "bool"
    if type_ == STRING:
        return "string"
    if isinstance(type_, (ClassType, ArrayType, EmptyArrayType, NullType)):
        return "ref"
    raise TempError(f"no hay temporales de tipo {type_}")


class TempManager:
    def __init__(self, unit: int = 0) -> None:
        self._unit = unit
        self._next = 0
        self._free: dict[str, list[int]] = {}
        self._live: dict[int, Temp] = {}
        self._peak = 0

    def acquire(self, type_: Type) -> Temp:
        pool = self._free.setdefault(temp_category(type_), [])
        if pool:
            index = min(pool)
            pool.remove(index)
        else:
            index = self._next
            self._next += 1
        temp = Temp(index, type_, self._unit)
        self._live[index] = temp
        self._peak = max(self._peak, len(self._live))
        return temp

    def release(self, temp: Temp) -> None:
        if self._live.get(temp.index) != temp:
            raise TempError(f"{temp.name} no esta vivo: doble liberacion o temporal de otra unidad")
        del self._live[temp.index]
        self._free.setdefault(temp_category(temp.type), []).append(temp.index)

    def is_live(self, temp: Temp) -> bool:
        return self._live.get(temp.index) == temp

    @property
    def live_count(self) -> int:
        return len(self._live)

    @property
    def peak(self) -> int:
        return self._peak

    @property
    def created(self) -> int:
        return self._next
