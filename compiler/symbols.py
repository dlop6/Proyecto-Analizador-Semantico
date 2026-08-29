"""
clases de simbolo (persona 1). capa intermedia del proyecto: depende solo de types.py,
no conoce el ast ni los scopes (eso lo arma scopes.py, que si depende de este archivo).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from compiler.types import STRING, Type

if TYPE_CHECKING:
    # solo para anotaciones -- evita el ciclo symbols <-> scopes en tiempo de ejecucion
    from compiler.scopes import Scope

# nombre del metodo que cuenta como constructor de una clase. un solo lugar, no un
# literal repetido en ast_builder.py y symbol_collector.py.
CONSTRUCTOR_NAME = "constructor"

# nombre de la variable implicita que se inyecta en el scope de cada metodo
THIS_NAME = "this"

# compiscript no tiene tipos de excepcion propios (no hay throw en la gramatica).
# se le da string a la variable del catch para que al menos se pueda hacer print(e).
# aislado aca por si persona 2 quiere cambiar esta convencion despues.
CATCH_VAR_TYPE = STRING


@dataclass
class Symbol:
    name: str
    line: int
    column: int
    type: Type | None = None
    scope_name: str = ""  # nombre legible del scope donde vive, util para reportes de persona 3


@dataclass
class VariableSymbol(Symbol):
    is_const: bool = False
    is_param: bool = False
    is_field: bool = False
    is_implicit: bool = False       # ej: 'this' inyectado, no lo escribio el usuario
    is_iteration_var: bool = False  # variable de un foreach
    initialized: bool = False


@dataclass
class FunctionSymbol(Symbol):
    params: list[VariableSymbol] = field(default_factory=list)
    return_type: Type | None = None
    is_constructor: bool = False
    is_method: bool = False
    owner_class: str | None = None
    scope: "Scope | None" = None

    @property
    def arity(self) -> int:
        return len(self.params)


@dataclass
class ClassSymbol(Symbol):
    parent_name: str | None = None
    parent: "ClassSymbol | None" = None
    fields: dict[str, VariableSymbol] = field(default_factory=dict)
    methods: dict[str, FunctionSymbol] = field(default_factory=dict)
    constructor: FunctionSymbol | None = None  # misma referencia que methods.get(CONSTRUCTOR_NAME)
    scope: "Scope | None" = None

    def lookup_member(self, name: str) -> VariableSymbol | FunctionSymbol | None:
        """busca un atributo o metodo subiendo por la cadena de herencia."""
        cls: ClassSymbol | None = self
        while cls is not None:
            if name in cls.fields:
                return cls.fields[name]
            if name in cls.methods:
                return cls.methods[name]
            cls = cls.parent
        return None
