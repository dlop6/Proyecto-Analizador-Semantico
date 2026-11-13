"""
contrato de los helpers de runtime: rutinas en ensamblador que el codigo generado llama
para lo que no se resuelve en linea (heap, chequeos, strings). aca solo se define el
contrato; los cuerpos los escribe quien haga el runtime.

siguen la MISMA convencion de llamada que todo lo demas (ver abi.py): argumentos en la
pila en orden, resultado en $v0, $v1 = 0 normal o 1 con el mensaje de error en $v0.
`can_fail` dice si el que llama tiene que revisar $v1 despues.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class HelperContract:
    name: str          # etiqueta en el ensamblador
    params: int        # cantidad de argumentos (una palabra cada uno)
    returns: bool      # deja un valor en $v0
    can_fail: bool     # puede devolver $v1 = 1
    description: str


_CONTRACTS = (
    HelperContract("rt_alloc", 1, True, False, "reserva n bytes en el heap, en cero; devuelve el puntero"),
    HelperContract("rt_check_null", 1, False, True, "falla si el puntero es null"),
    HelperContract("rt_check_bounds", 2, False, True, "(arreglo, indice): falla si el indice esta fuera de rango"),
    HelperContract("rt_check_divisor", 1, False, True, "falla si el divisor es cero"),
    HelperContract("rt_int_to_string", 1, True, False, "integer -> puntero a string nuevo"),
    HelperContract("rt_concat", 2, True, False, "(a, b) strings -> puntero a la concatenacion"),
    HelperContract("rt_string_equals", 2, True, False, "(a, b) strings -> 1 si tienen el mismo contenido, 0 si no"),
    HelperContract("rt_print_boolean", 1, False, False, "imprime true o false"),
    HelperContract("rt_uncaught_error", 1, False, False, "imprime el mensaje de un error no capturado y termina"),
)

HELPERS = MappingProxyType({contract.name: contract for contract in _CONTRACTS})
