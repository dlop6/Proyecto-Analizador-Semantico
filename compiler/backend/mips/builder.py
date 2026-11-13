"""
MipsBuilder: unico punto por donde se emite ensamblador. valida cada instruccion contra la
tabla de firmas, cuida que no haya etiquetas repetidas ni saltos a etiquetas inexistentes
y renderiza de forma determinista (mismo programa -> mismo texto, byte a byte).

mars arranca en la primera instruccion de .text, asi que el builder exige que lo primero
que se emita sea la etiqueta de entrada.
"""
from __future__ import annotations

from compiler.backend.mips.model import (
    BRANCH_OPCODES, AssemblyInstruction, AssemblyProgram, DataItem, LabelDef, TextItem,
)
from compiler.backend.mips.operands import LabelMem, LabelRef, Operand, string_label


class MipsBuilder:
    def __init__(self, entry_label: str = "main") -> None:
        self._entry = entry_label
        self._text: list[TextItem] = []
        self._data: list[DataItem] = []
        self._defined: set[str] = set()
        self._strings: dict[str, str] = {}

    # ---------- texto ----------

    def emit(self, opcode: str, *operands: Operand, comment: str | None = None) -> None:
        self._text.append(AssemblyInstruction(opcode, tuple(operands), comment))

    def emit_branch(self, opcode: str, *operands: Operand, comment: str | None = None) -> None:
        if opcode not in BRANCH_OPCODES:
            raise ValueError(f"{opcode!r} no es una instruccion de salto")
        self.emit(opcode, *operands, comment=comment)

    def mark(self, label: str) -> None:
        item = LabelDef(label)
        self._define(item.name)
        self._text.append(item)

    # ---------- datos ----------

    def add_data(self, label: str, directive: str, value: int | str | tuple[int | str, ...]) -> None:
        item = DataItem(label, directive, value)
        self._define(item.label)
        self._data.append(item)

    def add_string(self, text: str) -> str:
        """etiqueta de un literal; el mismo contenido reusa la etiqueta de su primera aparicion."""
        if text not in self._strings:
            label = string_label(len(self._strings))
            self.add_data(label, "asciiz", text)
            self._strings[text] = label
        return self._strings[text]

    # ---------- salida ----------

    def build(self) -> AssemblyProgram:
        self._check_entry()
        self._check_references()
        return AssemblyProgram(tuple(self._data), tuple(self._text))

    def render(self) -> str:
        return self.build().render()

    # ---------- internos ----------

    def _define(self, label: str) -> None:
        if label in self._defined:
            raise ValueError(f"etiqueta definida dos veces: {label}")
        self._defined.add(label)

    def _check_entry(self) -> None:
        if not self._text or self._text[0] != LabelDef(self._entry):
            raise ValueError(f"lo primero en .text tiene que ser la etiqueta de entrada '{self._entry}'")

    def _check_references(self) -> None:
        for item in self._text:
            if not isinstance(item, AssemblyInstruction):
                continue
            for operand in item.operands:
                name = operand.name if isinstance(operand, LabelRef) else operand.label if isinstance(operand, LabelMem) else None
                if name is not None and name not in self._defined:
                    raise ValueError(f"{item.opcode} apunta a la etiqueta inexistente '{name}'")
        for item in self._data:
            values = item.value if isinstance(item.value, tuple) else (item.value,)
            if item.directive == "word":
                for value in values:
                    if isinstance(value, str) and value not in self._defined:
                        raise ValueError(f".word apunta a la etiqueta inexistente '{value}'")
