"""
donde vive cada valor en tiempo de ejecucion, en slots abstractos (no bytes: no hay
arquitectura objetivo y generar codigo objeto esta fuera de alcance).

un StorageRef describe como se llega a un valor desde un punto concreto del codigo:
- GLOBAL: area global, slot fijo.
- LOCAL / PARAM / THIS: el frame de la funcion actual (this siempre en el slot 0).
- NONLOCAL: el frame de una funcion que encierra a la actual; lexical_depth dice cuantos
  saltos de static link hay que dar.
- FIELD: un atributo dentro de un objeto (field_slot del layout de la clase).

capa mas baja del ir: no importa nada del compilador.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StorageKind(Enum):
    GLOBAL = "global"
    LOCAL = "local"
    PARAM = "param"
    THIS = "this"
    FIELD = "field"
    NONLOCAL = "nonlocal"


# los que viven en el frame de la funcion que los declara
FRAME_KINDS = frozenset({StorageKind.LOCAL, StorageKind.PARAM, StorageKind.THIS})


@dataclass(frozen=True, slots=True)
class StorageRef:
    kind: StorageKind
    slot: int
    lexical_depth: int = 0
    name: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.slot, int) or isinstance(self.slot, bool) or self.slot < 0:
            raise ValueError(f"slot invalido: {self.slot!r}")
        if not self.name:
            raise ValueError("un StorageRef necesita el nombre del valor al que apunta")
        if self.kind is StorageKind.NONLOCAL:
            if self.lexical_depth < 1:
                raise ValueError("un acceso nonlocal tiene que subir al menos un frame")
        elif self.lexical_depth != 0:
            raise ValueError(f"lexical_depth solo aplica a NONLOCAL, no a {self.kind.name}")
