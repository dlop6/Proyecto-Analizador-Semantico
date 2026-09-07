"""
reglas de tipos para clases: acceso a miembros, llamadas a metodos, 'new' y override de
metodos heredados. parte de la semantica extendida (persona 3).

funciones puras, mismo espiritu que expression_rules.py/function_rules.py: reciben tipos
y simbolos ya resueltos (nunca el ast, nunca los scopes -- eso lo camina
extended_semantic_visitor.py) y devuelven el tipo resultante junto con un codigo de
diagnostico opcional. no escriben diagnosticos ellas mismas ni conocen diagnostics.py.

las llamadas a constructor y a metodo son, en esencia, el mismo problema que
function_rules.check_call (aridad + compatibilidad posicional de argumentos) una vez que
se resolvio a que FunctionSymbol se esta llamando -- asi que se reusa esa funcion en vez
de duplicar el loop de validacion, y solo se remapean los codigos CPS-1xx que devuelve a
los CPS-2xx propios de esta etapa (el catalogo de mensajes de cada etapa es exclusivo,
ver docstring de extended_semantic_visitor.py).
"""
from __future__ import annotations

from compiler.function_rules import check_call
from compiler.symbols import CONSTRUCTOR_NAME, ClassSymbol, FunctionSymbol, VariableSymbol
from compiler.types import ClassType, ERROR, ErrorType, Type

# remapeo de los codigos que puede devolver function_rules.check_call (rango CPS-1xx,
# propiedad de la semantica core) a los codigos propios de esta etapa (CPS-2xx).
_CONSTRUCTOR_CODES = {"CPS-111": "CPS-210", "CPS-112": "CPS-211"}
_METHOD_CODES = {"CPS-111": "CPS-212", "CPS-112": "CPS-213"}

# resultado de una regla: (tipo resultante, codigo de diagnostico o None, detail)
CheckResult = tuple[Type, "str | None", "str | None"]


def check_property_access(
    obj_type: Type, member_name: str, classes: dict[str, ClassSymbol],
) -> CheckResult:
    """
    tipo de `obj.member_name` para lectura (o, reusado por el visitor, como paso previo
    a validar el destino de una asignacion). busca con ClassSymbol.lookup_member, que ya
    sube por la cadena de herencia.
    """
    if isinstance(obj_type, ErrorType):
        return ERROR, None, None
    if not isinstance(obj_type, ClassType):
        return ERROR, "CPS-208", member_name

    cls = classes.get(obj_type.name)
    if cls is None:
        return ERROR, None, None  # clase invalida, ya reportado en otro lado (defensivo)

    member = cls.lookup_member(member_name)
    if member is None:
        return ERROR, "CPS-200", member_name
    if isinstance(member, VariableSymbol):
        return (member.type if member.type is not None else ERROR), None, None
    # Compiscript no tiene metodos de primera clase; el visitor de llamadas usa
    # check_method_call, asi que este diagnostico solo representa una lectura real.
    return ERROR, "CPS-215", member_name


def check_method_call(
    obj_type: Type, method_name: str, arg_types: list[Type],
    classes: dict[str, ClassSymbol], hierarchy=None,
) -> CheckResult:
    """valida una llamada a metodo `obj.method_name(args)` ya resuelta a una clase."""
    if isinstance(obj_type, ErrorType):
        return ERROR, None, None
    if not isinstance(obj_type, ClassType):
        return ERROR, "CPS-208", method_name

    cls = classes.get(obj_type.name)
    if cls is None:
        return ERROR, None, None

    member = cls.lookup_member(method_name)
    if member is None:
        return ERROR, "CPS-200", method_name
    if not isinstance(member, FunctionSymbol):
        return ERROR, "CPS-201", method_name

    result, core_code, detail = check_call(method_name, member, arg_types, hierarchy)
    code = _METHOD_CODES.get(core_code, core_code)
    return result, code, detail


def check_new_call(
    class_name: str, cls: ClassSymbol | None, arg_types: list[Type], hierarchy=None,
) -> CheckResult:
    """
    valida `new Clase(args)` contra el constructor propio de `cls`. La regla 12 del PDF
    del proyecto indica que, si una clase no tiene constructor, solo admite cero
    argumentos; por eso no se hereda el constructor del padre. El tipo resultante SIEMPRE es
    ClassType(class_name) -- a diferencia de una llamada a funcion, el uso incorrecto de
    los argumentos no cambia que 'new Clase(...)' produzca un valor de tipo Clase.
    """
    result_type = ClassType(class_name)
    if cls is None:
        return ERROR, None, None  # clase no declarada, ya reportado por el frontend (CPS-023)

    constructor = cls.constructor
    if not isinstance(constructor, FunctionSymbol):
        if len(arg_types) != 0:
            return result_type, "CPS-210", class_name
        return result_type, None, None

    _, core_code, detail = check_call(class_name, constructor, arg_types, hierarchy)
    code = _CONSTRUCTOR_CODES.get(core_code, core_code)
    return result_type, code, detail


def check_override(sub: FunctionSymbol, parent: FunctionSymbol) -> "str | None":
    """
    'firma exacta' al sobrescribir: misma aridad, mismos tipos de parametro en el mismo
    orden, mismo tipo de retorno. sin variancia -- el enunciado pide firma exacta, no
    covarianza/contravarianza (yagni).
    """
    if sub.arity != parent.arity:
        return "CPS-202"
    for sub_param, parent_param in zip(sub.params, parent.params):
        if sub_param.type != parent_param.type:
            return "CPS-202"
    if sub.return_type != parent.return_type:
        return "CPS-202"
    return None
