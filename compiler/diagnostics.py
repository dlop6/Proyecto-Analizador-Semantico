"""
manejo de diagnosticos del frontend (persona 1).

responsabilidad unica: representar errores/warnings con posicion y coleccionarlos.
no conoce el ast ni la tabla de simbolos, solo junta lo que le reportan.

rango de codigos reservado para persona 1: CPS-0xx (lexico, sintaxis, ast, simbolos, scopes).
CPS-1xx queda para persona 2 (tipos) y CPS-2xx para persona 3 (integracion/ide). no se toca eso aca.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from antlr4.error.ErrorListener import ErrorListener


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# catalogo unico de mensajes. un solo lugar para editar texto, nada de strings sueltos
# repetidos por el codigo (asi no se duplica ni se desincroniza).
_MESSAGES: dict[str, str] = {
    "CPS-000": "caracter no reconocido: {detail}",
    "CPS-001": "error de sintaxis: {detail}",
    "CPS-002": "el literal entero {detail} excede el rango de 64 bits con signo",
    "CPS-003": "literal malformado: {detail}",
    "CPS-004": "el codigo fuente excede el tamaño maximo permitido ({detail} bytes)",
    "CPS-010": "el destino de la asignacion no es valido: {detail}",
    "CPS-011": "la constante '{detail}' debe inicializarse en su declaracion",
    "CPS-012": "'break' solo puede usarse dentro de un bucle o un switch",
    "CPS-013": "'continue' solo puede usarse dentro de un bucle",
    "CPS-014": "'return' solo puede usarse dentro de una funcion",
    "CPS-020": "'{detail}' ya esta declarado en este ambito",
    "CPS-021": "la clase ya tiene un miembro llamado '{detail}'",
    "CPS-022": "parametro duplicado: '{detail}'",
    "CPS-023": "clase no declarada: '{detail}'",
    "CPS-030": "tipo desconocido: '{detail}'",
    "CPS-031": "herencia circular detectada en la clase '{detail}'",
    "CPS-032": "el constructor no debe declarar tipo de retorno",
    "CPS-033": "el atributo '{detail}' oculta uno heredado de la clase base",
    "CPS-040": "'this' solo puede usarse dentro de un metodo o constructor",
}

# codigos que por diseño son advertencia y no error, aunque el llamador no lo especifique
_WARNING_CODES = {"CPS-002", "CPS-033"}


def _format_message(code: str, detail: str | None) -> str:
    template = _MESSAGES.get(code)
    if template is None:
        # esto no deberia pasar nunca en produccion, es defensivo. si pasa, se ve clarito el codigo huerfano
        return f"[{code}] diagnostico sin mensaje registrado (detail={detail!r})"
    if detail is None:
        return template
    return template.format(detail=detail)


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """
    firma posicional exacta que exige el pdf: Diagnostic(code, message, line, column).
    severity y length son opcionales con default, no rompen ese contrato.
    """
    code: str
    message: str
    line: int
    column: int
    severity: Severity = Severity.ERROR
    length: int = 1  # cuanto subrayar, para cuando persona 3 lo pinte en el ide


class DiagnosticBag:
    """coleccion de diagnosticos de una sola compilacion. sin estado compartido entre llamadas."""

    def __init__(self) -> None:
        self._items: list[Diagnostic] = []
        self._seen: set[tuple[str, int, int]] = set()

    def add(self, diag: Diagnostic) -> None:
        # el recovery de antlr puede reportar el mismo punto varias veces, no queremos spam
        key = (diag.code, diag.line, diag.column)
        if key in self._seen:
            return
        self._seen.add(key)
        self._items.append(diag)

    def report(
        self,
        code: str,
        line: int,
        column: int,
        detail: str | None = None,
        severity: Severity | None = None,
        length: int = 1,
    ) -> Diagnostic:
        """atajo para construir el Diagnostic desde el catalogo y agregarlo de una."""
        message = _format_message(code, detail)
        sev = severity or (Severity.WARNING if code in _WARNING_CODES else Severity.ERROR)
        diag = Diagnostic(code=code, message=message, line=line, column=column, severity=sev, length=length)
        self.add(diag)
        return diag

    def error(self, code: str, line: int, column: int, detail: str | None = None, length: int = 1) -> Diagnostic:
        return self.report(code, line, column, detail, severity=Severity.ERROR, length=length)

    def warning(self, code: str, line: int, column: int, detail: str | None = None, length: int = 1) -> Diagnostic:
        return self.report(code, line, column, detail, severity=Severity.WARNING, length=length)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == Severity.ERROR for d in self._items)

    def sorted(self) -> list[Diagnostic]:
        # orden determinista: linea, columna, codigo. asi los tests no dependen del orden de insercion
        return sorted(self._items, key=lambda d: (d.line, d.column, d.code))

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self.sorted())

    def to_list(self) -> list[Diagnostic]:
        return self.sorted()


class CollectingErrorListener(ErrorListener):
    """
    listener custom para antlr. ojo: NO es el DiagnosticErrorListener que trae antlr de fabrica,
    le pusimos otro nombre a proposito para no confundirlos.

    hay que quitar los listeners default (removeErrorListeners) en el lexer y el parser
    ANTES de agregar este, si no antlr sigue escupiendo al stderr por su cuenta.
    """

    def __init__(self, bag: DiagnosticBag, is_lexer: bool) -> None:
        super().__init__()
        self._bag = bag
        self._code = "CPS-000" if is_lexer else "CPS-001"

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):  # noqa: N802 (firma de antlr)
        # antlr reporta columna 0-based, la normalizamos a 1-based como el resto del proyecto
        self._bag.report(self._code, line, column + 1, detail=msg)
