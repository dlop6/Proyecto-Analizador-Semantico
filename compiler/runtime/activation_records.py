"""
registros de activacion y layouts de clase: valores inmutables que describen como se
acomoda la memoria abstracta de una funcion y de un objeto. no calculan nada, solo
validan sus invariantes; quien los arma es runtime_layout.py.

frame de una funcion (slots abstractos, no bytes):
    [this]  [params en orden]  [locales en orden de declaracion]
this solo existe en metodos y constructores, y siempre va en el slot 0.
"""
from __future__ import annotations

from dataclasses import dataclass

from compiler.runtime.storage import StorageKind

# orden obligatorio dentro de un frame: this, despues params, despues locales
_FRAME_ORDER = {StorageKind.THIS: 0, StorageKind.PARAM: 1, StorageKind.LOCAL: 2}


def _check_consecutive(slots: list[int], what: str) -> None:
    if slots != list(range(len(slots))):
        raise ValueError(f"los slots de {what} tienen que ir 0..n-1 sin huecos: {slots}")


@dataclass(frozen=True, slots=True)
class FrameSlot:
    slot: int
    name: str
    kind: StorageKind


@dataclass(frozen=True, slots=True)
class ActivationRecord:
    label: str
    lexical_depth: int          # funciones que la encierran (0 = top-level o metodo)
    static_link: bool           # necesita llegar al frame de una funcion que la encierra
    is_method: bool             # metodo o constructor: trae this en el slot 0
    owner_class: str | None
    slots: tuple[FrameSlot, ...]

    def __post_init__(self) -> None:
        if self.lexical_depth < 0:
            raise ValueError("lexical_depth no puede ser negativo")
        if self.static_link and self.lexical_depth == 0:
            raise ValueError("una funcion sin funcion que la encierre no tiene a donde apuntar el static link")
        _check_consecutive([s.slot for s in self.slots], f"frame de {self.label}")
        ranks = []
        for s in self.slots:
            if s.kind not in _FRAME_ORDER:
                raise ValueError(f"{s.kind.name} no vive en un frame")
            ranks.append(_FRAME_ORDER[s.kind])
        if ranks != sorted(ranks):
            raise ValueError("el frame tiene que ser this, params y locales, en ese orden")
        has_this = bool(self.slots) and self.slots[0].kind is StorageKind.THIS
        if has_this != self.is_method:
            raise ValueError("this va en el slot 0 si y solo si es metodo o constructor")
        if ranks.count(_FRAME_ORDER[StorageKind.THIS]) > 1:
            raise ValueError("un frame tiene a lo sumo un this")

    @property
    def param_count(self) -> int:
        return sum(1 for s in self.slots if s.kind is StorageKind.PARAM)

    @property
    def frame_size(self) -> int:
        return len(self.slots)


@dataclass(frozen=True, slots=True)
class FieldEntry:
    slot: int
    name: str
    owner_class: str  # clase que declaro el campo (puede ser un ancestro)


@dataclass(frozen=True, slots=True)
class MethodEntry:
    name: str
    slot: int
    impl_label: str   # implementacion que corre para esta clase (la propia o la heredada)
    owner_class: str  # clase que provee esa implementacion


@dataclass(frozen=True, slots=True)
class ClassLayout:
    class_name: str
    parent_name: str | None
    fields: tuple[FieldEntry, ...]    # heredados primero, propios despues
    methods: tuple[MethodEntry, ...]  # tabla de despacho completa, por slot
    constructor_label: str | None     # el propio o el del ancestro mas cercano; None si ninguno

    def __post_init__(self) -> None:
        _check_consecutive([f.slot for f in self.fields], f"campos de {self.class_name}")
        _check_consecutive([m.slot for m in self.methods], f"metodos de {self.class_name}")
        names = [m.name for m in self.methods]
        if len(names) != len(set(names)):
            raise ValueError(f"metodo repetido en la tabla de despacho de {self.class_name}")

    def field_named(self, name: str) -> FieldEntry | None:
        # con ocultamiento hay dos campos con el mismo nombre: gana el mas derivado,
        # igual que ClassSymbol.lookup_member
        for entry in reversed(self.fields):
            if entry.name == name:
                return entry
        return None

    def method_named(self, name: str) -> MethodEntry | None:
        return next((m for m in self.methods if m.name == name), None)

    def method_at(self, slot: int) -> MethodEntry:
        return self.methods[slot]

    @property
    def size(self) -> int:
        return len(self.fields)
