"""
unica fuente de etiquetas de una compilacion. dos familias que no pueden chocar entre si:

- control de flujo:  L_<prefijo>_<n>    (ej. L_if_else_0, L_while_end_3)
  n es un contador global de la compilacion, compartido por todos los prefijos, asi
  ninguna etiqueta se repite aunque dos construcciones usen el mismo prefijo.
- funciones:         fn::<ruta>[#k]     (ej. fn::factorial, fn::f.g, fn::Perro.hablar)
  si la misma ruta aparece dos veces (dos anidadas homonimas en bloques hermanos) la
  segunda queda fn::f.g#2, la tercera #3, etc.

determinista: la misma secuencia de pedidos da siempre las mismas etiquetas. una
instancia por compilacion, sin estado global.
"""
from __future__ import annotations

import re

_PREFIX = re.compile(r"^[a-z_]+$")
_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


class LabelManager:
    def __init__(self) -> None:
        self._counter = 0
        self._issued: set[str] = set()

    def new_label(self, prefix: str) -> str:
        if not _PREFIX.match(prefix):
            raise ValueError(f"prefijo de etiqueta invalido: {prefix!r} (solo minusculas y _)")
        label = f"L_{prefix}_{self._counter}"
        self._counter += 1
        self._issued.add(label)
        return label

    def function_label(self, path: str) -> str:
        if not _PATH.match(path):
            raise ValueError(f"ruta de funcion invalida: {path!r}")
        base = f"fn::{path}"
        label, suffix = base, 2
        while label in self._issued:
            label = f"{base}#{suffix}"
            suffix += 1
        self._issued.add(label)
        return label

    def owns(self, label: str) -> bool:
        """True si esta etiqueta la emitio esta compilacion (el builder rechaza las ajenas)."""
        return label in self._issued
