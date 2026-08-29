# unico punto de acoplamiento con lo que genera antlr en todo el proyecto.
# si algun dia cambia la ubicacion o la version, se toca nada mas este archivo.
from .CompiscriptLexer import CompiscriptLexer
from .CompiscriptParser import CompiscriptParser
from .CompiscriptVisitor import CompiscriptVisitor

__all__ = ["CompiscriptLexer", "CompiscriptParser", "CompiscriptVisitor"]
