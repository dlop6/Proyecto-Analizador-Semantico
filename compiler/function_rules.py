"""
reglas de funciones: validacion de llamadas y de 'return', parte de la semantica core.

las firmas (parametros, tipo de retorno explicito) ya vienen resueltas por
symbol_collector.py -- este modulo no las reconstruye, solo compara los tipos que le
pasa core_semantic_visitor.py. igual que expression_rules.py, no escribe diagnosticos
directamente: devuelve codigos que el visitor traduce con el catalogo CPS-1xx.

el unico estado que vive aca es ReturnTracker, que acumula los tipos de los 'return'
de una funcion SIN anotacion de retorno mientras dura la visita de su cuerpo (regla 11:
"si no declara tipo, se infiere un unico tipo comun"). un tracker por funcion, en la pila
del visitor -- no es estado global ni se comparte entre compilaciones.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from compiler.symbols import FunctionSymbol
from compiler.types import ClassHierarchy, ERROR, ErrorType, Type, VOID, common_type, is_assignable


def check_call(
    name: str, function: FunctionSymbol, arg_types: list[Type], hierarchy: ClassHierarchy | None = None,
) -> tuple[Type, "str | None", "str | None"]:
    """valida aridad y compatibilidad posicional de una llamada ya resuelta a `function`."""
    if len(arg_types) != function.arity:
        return ERROR, "CPS-111", name

    for index, (param, arg_type) in enumerate(zip(function.params, arg_types), start=1):
        if isinstance(arg_type, ErrorType):
            continue
        if param.type is not None and not is_assignable(param.type, arg_type, hierarchy):
            return ERROR, "CPS-112", f"{index} de '{name}'"

    if function.return_type is None:
        # el retorno de `function` todavia no se infirio (llamada recursiva o adelantada a
        # una funcion sin anotacion cuyo cuerpo no se termino de recorrer). se devuelve
        # ERROR para no cascadear un tipo incorrecto -- limitacion documentada en el readme,
        # el proyecto no exige resolver ese punto fijo mutuo.
        return ERROR, None, None
    return function.return_type, None, None


@dataclass
class ReturnTracker:
    """acumula los 'return' de una funcion mientras se recorre su cuerpo."""
    function: FunctionSymbol
    declared: Type | None  # None si la funcion no tiene anotacion de retorno
    seen_types: list[Type] = field(default_factory=list)


def check_return(tracker: ReturnTracker, value_type: Type | None, hierarchy: ClassHierarchy | None = None) -> "str | None":
    """
    valida (si `tracker.function` declara tipo) o acumula (si no) el tipo de un 'return'.
    `value_type` es None para un 'return;' sin valor.
    """
    if tracker.declared is not None:
        actual = value_type if value_type is not None else VOID
        if not is_assignable(tracker.declared, actual, hierarchy):
            return "CPS-113"
        return None

    if value_type is not None:
        tracker.seen_types.append(value_type)
    return None


def finalize_return_type(tracker: ReturnTracker, hierarchy: ClassHierarchy | None = None) -> "str | None":
    """
    al cerrar el cuerpo de una funcion SIN anotacion, calcula su tipo de retorno inferido
    y lo escribe en `tracker.function.return_type` (in-place, es el mismo FunctionSymbol
    que usan las llamadas). sin 'return' con valor, la funcion es VOID.
    """
    if tracker.declared is not None:
        return None
    if not tracker.seen_types:
        tracker.function.return_type = VOID
        return None

    result = tracker.seen_types[0]
    for candidate in tracker.seen_types[1:]:
        joined = common_type(result, candidate, hierarchy)
        if joined is None:
            tracker.function.return_type = ERROR
            return "CPS-114"
        result = joined
    tracker.function.return_type = result
    return None
