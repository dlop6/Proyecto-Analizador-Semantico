"""
FramePlanner: decide donde vive cada cosa de un frame, en bytes. solo calcula offsets; no
emite nada ni toca registros.

region por debajo de $fp (cada casilla es una palabra, ver abi.local_area_offset):
    [locales][home de temporales][argumentos pendientes]

- locales: una casilla por slot LOCAL, en orden de slot.
- home de temporales: una por nombre creado (t0..tN-1). es donde el allocator vuelca un
  temporal cuando se queda sin registros o antes de una llamada.
- argumentos pendientes: el IR emite los ARG sueltos y los consume un CALL mas adelante,
  incluso con llamadas anidadas (f(1, g(2))) y con temporales que se reusan entre el ARG y
  el CALL. por eso cada ARG se guarda apenas se ejecuta y el CALL los copia a la pila.
  el tamaño es la profundidad maxima de ARG pendientes de la funcion.

los argumentos entrantes (static link, this, params) los puso el que llama, por encima de
$fp, a partir de 8($fp).
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping

from compiler.backend.mips.abi import WORD, incoming_arg_offset, local_area_offset
from compiler.ir.model import IRFragment, IRFunction, IRProgram, TACInstruction
from compiler.ir.opcodes import Opcode
from compiler.runtime.storage import StorageKind

if TYPE_CHECKING:
    from compiler.runtime.runtime_layout import RuntimeLayout


@dataclass(frozen=True, slots=True)
class FramePlan:
    label: str
    size: int                              # bytes que el prologo reserva bajo $fp
    static_link: int | None                # offset del static link entrante, si lo hay
    receiver: int | None                   # offset de this entrante, si es metodo
    param_offsets: Mapping[int, int]       # slot del ActivationRecord -> offset (params)
    local_offsets: Mapping[int, int]       # slot del ActivationRecord -> offset (locales)
    temp_offsets: Mapping[int, int]        # indice de temporal -> offset de su home
    arg_stash: tuple[int, ...]             # offset de cada casilla de argumento pendiente, por profundidad
    incoming_bytes: int                    # bytes de argumentos que el que llama tiene que limpiar

    def offset_of(self, kind: StorageKind, slot: int) -> int:
        """offset de una variable del propio frame (THIS, PARAM o LOCAL)."""
        if kind is StorageKind.THIS:
            if self.receiver is None:
                raise ValueError(f"{self.label} no tiene this")
            return self.receiver
        table = {StorageKind.PARAM: self.param_offsets, StorageKind.LOCAL: self.local_offsets}.get(kind)
        if table is None or slot not in table:
            raise ValueError(f"{self.label} no tiene {kind.name} en el slot {slot}")
        return table[slot]

    def slot_offset(self, slot: int) -> int:
        """offset de un slot del ActivationRecord sin saber su tipo (lo que trae un StorageRef NONLOCAL)."""
        if slot in self.param_offsets:
            return self.param_offsets[slot]
        if slot in self.local_offsets:
            return self.local_offsets[slot]
        if slot == 0 and self.receiver is not None:   # this siempre es el slot 0 de un metodo
            return self.receiver
        raise ValueError(f"{self.label} no tiene el slot {slot}")

    def temp_offset(self, index: int) -> int:
        if index not in self.temp_offsets:
            raise ValueError(f"{self.label} no tiene home para t{index}")
        return self.temp_offsets[index]


class FramePlanner:
    @staticmethod
    def plan(function: IRFunction, layout: "RuntimeLayout") -> FramePlan:
        record = layout.records.get(function.label)
        if record is None:
            raise ValueError(f"no hay registro de activacion para {function.label}")

        # entrantes: static link, this, params (en ese orden, una palabra cada uno)
        next_arg = 0
        static_link = receiver = None
        if record.static_link:
            static_link, next_arg = incoming_arg_offset(next_arg), next_arg + 1
        param_offsets: dict[int, int] = {}
        local_offsets: dict[int, int] = {}
        local_index = 0
        for slot in record.slots:
            if slot.kind is StorageKind.THIS:
                receiver, next_arg = incoming_arg_offset(next_arg), next_arg + 1
            elif slot.kind is StorageKind.PARAM:
                param_offsets[slot.slot], next_arg = incoming_arg_offset(next_arg), next_arg + 1
            else:
                local_offsets[slot.slot], local_index = local_area_offset(local_index), local_index + 1

        return _finish(function.label, function.instructions, function.created_temps, local_index,
                       static_link, receiver, param_offsets, local_offsets, next_arg)

    @staticmethod
    def plan_entry(fragment: IRFragment, label: str = "main") -> FramePlan:
        """el codigo global: sin entrantes ni locales (sus variables van en __globals)."""
        return _finish(label, fragment.instructions, fragment.created_temps, 0, None, None, {}, {}, 0)


ENTRY_LABEL = "main"


def plan_program(program: IRProgram, layout: "RuntimeLayout") -> dict[str, FramePlan]:
    """plan de todo el programa: 'main' para el codigo global y uno por funcion (por etiqueta del ir)."""
    plans = {ENTRY_LABEL: FramePlanner.plan_entry(program.entry, ENTRY_LABEL)}
    for function in program.functions:
        plans[function.label] = FramePlanner.plan(function, layout)
    return plans


def _finish(
    label: str, instructions: tuple[TACInstruction, ...], created_temps: int, locals_count: int,
    static_link: int | None, receiver: int | None,
    param_offsets: dict[int, int], local_offsets: dict[int, int], incoming_words: int,
) -> FramePlan:
    temp_offsets = {i: local_area_offset(locals_count + i) for i in range(created_temps)}
    stash_base = locals_count + created_temps
    stash = tuple(local_area_offset(stash_base + d) for d in range(max_pending_args(instructions)))
    return FramePlan(
        label=label,
        size=WORD * (stash_base + len(stash)),
        static_link=static_link, receiver=receiver,
        param_offsets=MappingProxyType(param_offsets), local_offsets=MappingProxyType(local_offsets),
        temp_offsets=MappingProxyType(temp_offsets), arg_stash=stash,
        incoming_bytes=WORD * incoming_words,
    )


def max_pending_args(instructions: tuple[TACInstruction, ...]) -> int:
    """
    profundidad maxima de ARG sin consumir. ARG suma uno; CALL y CALL_METHOD consumen
    `argc` (en CALL_METHOD el receptor no es un ARG y no entra en argc).
    """
    depth = peak = 0
    for instr in instructions:
        if instr.opcode is Opcode.ARG:
            depth += 1
            peak = max(peak, depth)
        elif instr.opcode in (Opcode.CALL, Opcode.CALL_METHOD):
            argc = instr.meta("argc")
            if not isinstance(argc, int) or argc < 0 or argc > depth:
                raise ValueError(f"{instr.opcode.value} consume {argc!r} argumentos y solo hay {depth} pendientes")
            depth -= argc
    if depth:
        raise ValueError(f"{depth} argumentos quedaron sin consumir al terminar la funcion")
    return peak
