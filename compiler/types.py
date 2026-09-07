"""
sistema de tipos de compiscript, parte del frontend.

por decision explicita del proyecto NO se agrega float a la gramatica, asi que integer
es el unico tipo numerico. esto no es un descuido: numeric_result y common_type se dejan
con semantica honesta para ese escenario, documentado en cada funcion.

este modulo no importa symbols.py ni ast_nodes.py -> sin ciclos, capa mas baja del proyecto.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Type:
    """base de toda la jerarquia de tipos. inmutable siempre (a diferencia de los nodos del ast)."""


@dataclass(frozen=True, slots=True)
class PrimitiveType(Type):
    name: str

    def __str__(self) -> str:
        return self.name


# singletons: un solo objeto por tipo primitivo, comparten identidad y hash gratis
INTEGER = PrimitiveType("integer")
STRING = PrimitiveType("string")
BOOLEAN = PrimitiveType("boolean")


@dataclass(frozen=True, slots=True)
class NullType(Type):
    def __str__(self) -> str:
        return "null"


@dataclass(frozen=True, slots=True)
class VoidType(Type):
    """tipo de una funcion sin anotacion de retorno / sin return con valor."""
    def __str__(self) -> str:
        return "void"


@dataclass(frozen=True, slots=True)
class ErrorType(Type):
    """
    tipo comodin para cuando algo ya fallo antes. se absorbe en todas las comparaciones
    para no cascadear un error de tipos en veinte diagnosticos mas.
    """
    def __str__(self) -> str:
        return "<error>"


@dataclass(frozen=True, slots=True)
class ClassType(Type):
    """
    tipo nominal de una clase. se identifica SOLO por nombre, no guarda referencia al
    ClassSymbol -> lo hace hashable/comparable sin depender de symbols.py (evita el ciclo).
    """
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class ArrayType(Type):
    """T[] -> ArrayType(T). T[][] -> ArrayType(ArrayType(T)). igualdad estructural gratis por dataclass."""
    element: Type

    def __str__(self) -> str:
        return f"{self.element}[]"


@dataclass(frozen=True, slots=True)
class EmptyArrayType(Type):
    """
    tipo del literal [] antes de tener contexto. actua como bottom type de los arreglos:
    es asignable a cualquier ArrayType, asi 'let a: integer[] = [];' funciona sin necesitar
    inferencia bidireccional de verdad (eso seria mas alla de lo que pide el proyecto).
    """
    def __str__(self) -> str:
        return "[]"


EMPTY_ARRAY = EmptyArrayType()
ERROR = ErrorType()
NULL = NullType()
VOID = VoidType()


class ClassHierarchy(Protocol):
    """
    protocolo minimo (un solo metodo) para que types.py pueda razonar sobre herencia
    sin importar symbols.py. quien tenga la tabla de simbolos real lo implementa.
    """
    def is_subclass(self, sub_name: str, super_name: str) -> bool:
        ...

    def ancestors(self, name: str) -> list[str]:
        """Cadena nominal desde `name` hasta su raiz conocida, inclusiva."""
        ...


def same_type(a: Type, b: Type) -> bool:
    """igualdad estructural exacta. no mira herencia ni conversiones, es la relacion base."""
    return a == b


def _is_reference_type(t: Type) -> bool:
    return isinstance(t, (ClassType, ArrayType, EmptyArrayType))


def is_assignable(target: Type, source: Type, hierarchy: ClassHierarchy | None = None) -> bool:
    """
    ¿se puede asignar un valor de tipo `source` a algo declarado como `target`?
    reflexiva, y con las reglas del proyecto: integer->float no aplica (no hay float),
    null solo entra en tipos de referencia, subclase->padre si se pasa la jerarquia,
    y arreglos invariantes (Array[Perro] NO es Array[Animal], evita el array-store problem).
    """
    if same_type(target, source):
        return True

    # un error ya reportado no debe generar una cascada de errores nuevos
    if isinstance(target, ErrorType) or isinstance(source, ErrorType):
        return True

    if isinstance(source, NullType) and _is_reference_type(target):
        return True

    if isinstance(target, ClassType) and isinstance(source, ClassType):
        if hierarchy is not None:
            return hierarchy.is_subclass(source.name, target.name)
        return False  # sin jerarquia disponible, solo vale la igualdad de nombre (ya cubierta arriba)

    if isinstance(target, ArrayType) and isinstance(source, EmptyArrayType):
        return True

    # arrays invariantes: NO se recorre recursivamente con is_assignable, tiene que ser exactamente igual
    return False


def numeric_result(a: Type, b: Type) -> Type | None:
    """
    tipo resultante de aplicar +, -, *, / o % entre `a` y `b`, o None si la operacion no aplica.
    con integer como unico numerico esto es simple, pero es EL punto central de la regla:
    si el dia de mañana se agrega float, se cambia esta funcion y ya. no maneja
    string+string (esa es una regla del operador +, no de "lo numerico" -> le toca a la semantica core).
    """
    if isinstance(a, ErrorType) or isinstance(b, ErrorType):
        return ERROR
    if isinstance(a, PrimitiveType) and isinstance(b, PrimitiveType) and a is INTEGER and b is INTEGER:
        return INTEGER
    return None


def common_type(a: Type, b: Type, hierarchy: ClassHierarchy | None = None) -> Type | None:
    """
    supertipo comun mas especifico (join) de `a` y `b`, o None si no existe.
    lo usan: el operador ternario, el tipo de los literales de arreglo, y unificar con null.
    """
    if same_type(a, b):
        return a
    if isinstance(a, ErrorType) or isinstance(b, ErrorType):
        return ERROR

    if isinstance(a, NullType) and _is_reference_type(b):
        return b
    if isinstance(b, NullType) and _is_reference_type(a):
        return a

    if isinstance(a, EmptyArrayType) and isinstance(b, ArrayType):
        return b
    if isinstance(b, EmptyArrayType) and isinstance(a, ArrayType):
        return a

    if isinstance(a, ClassType) and isinstance(b, ClassType) and hierarchy is not None:
        return _closest_common_ancestor(a, b, hierarchy)

    # los arrays son invariantes, asi que dos arrays distintos no tienen join salvo que sean iguales
    # (ya cubierto por same_type arriba)
    return None


def _closest_common_ancestor(a: ClassType, b: ClassType, hierarchy: ClassHierarchy) -> ClassType | None:
    """
    sube por la cadena de `a` (via is_subclass) buscando el primer ancestro que tambien
    lo sea de `b`. es lineal, no hace falta nada mas fino para el alcance del proyecto.
    """
    ancestors = getattr(hierarchy, "ancestors", None)
    if ancestors is not None:
        ancestors_of_a = set(ancestors(a.name))
        for name in ancestors(b.name):
            if name in ancestors_of_a:
                return ClassType(name)
        return None

    # Compatibilidad con implementaciones antiguas del protocolo: aun pueden resolver
    # la relacion directa, pero no hermanas sin exponer la cadena completa.
    if hierarchy.is_subclass(a.name, b.name):
        return b
    if hierarchy.is_subclass(b.name, a.name):
        return a
    return None
