"""
optimizador por mirilla (persona 3): las seis transformaciones acordadas en el pdf, sobre
el ensamblador ESTRUCTURADO (AssemblyProgram con AssemblyInstruction/LabelDef), nunca
sobre texto.

  R1  move r, r                 -> se elimina (no tiene efecto)
  R2  move r, s ; move r, s     -> se elimina la segunda (adyacentes, sin etiqueta en medio)
  R3  addiu r, s, 0             -> move r, s (si r == s, despues R1 la elimina)
  R4  beq r, r, L               -> j L (la condicion siempre es verdadera)
  R5  bne r, r, L               -> se elimina (la condicion nunca es verdadera)
  R6  j L ; L:                  -> se elimina el j (L es la proxima etiqueta ejecutable:
                                   solo etiquetas entre el j y la instruccion siguiente)

seguridad:
- R1-R5 miran una o dos instrucciones adyacentes del mismo bloque: una etiqueta entre medio
  corta la ventana (alguien puede saltar ahi). no se mueve nada a traves de etiquetas,
  saltos, llamadas ni limites de funcion, y no se cambia ninguna etiqueta.
- R2 solo aplica si r != s (si no, ya es R1) y la primera no cambia s.
- R6 solo quita el salto si su destino es una de las etiquetas que siguen inmediatamente:
  la ejecucion llega al mismo lugar cayendo de largo.
- se repiten las pasadas hasta que ninguna regla aplique (una regla puede habilitar otra:
  R3 deja un move r, r que R1 elimina). cada pasada achica o reescribe, asi que termina.

la seccion .data no se toca. PeepholeOptimizer.optimize(programa) devuelve el programa
optimizado y un informe con cuantas veces aplico cada regla (lo muestra la gui y lo usan
los tests de equivalencia en mars).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType

from compiler.backend.mips.model import AssemblyInstruction, AssemblyProgram, LabelDef, TextItem
from compiler.backend.mips.operands import Imm, LabelRef, Reg

RULES = MappingProxyType({
    "R1": "move r, r -> eliminar",
    "R2": "move r, s ; move r, s -> eliminar la segunda",
    "R3": "addiu r, s, 0 -> move r, s",
    "R4": "beq r, r, L -> j L",
    "R5": "bne r, r, L -> eliminar",
    "R6": "j L ; L: -> eliminar el j",
})


@dataclass
class PeepholeReport:
    applied: dict[str, int] = field(default_factory=lambda: {rule: 0 for rule in RULES})
    passes: int = 0
    before: int = 0   # instrucciones (sin contar etiquetas) antes de optimizar
    after: int = 0

    @property
    def total(self) -> int:
        return sum(self.applied.values())

    def summary(self) -> str:
        used = ", ".join(f"{rule}x{count}" for rule, count in self.applied.items() if count) or "ninguna"
        return f"mirilla: {self.before} -> {self.after} instrucciones ({used})"


class PeepholeOptimizer:

    @classmethod
    def optimize(cls, program: AssemblyProgram) -> tuple[AssemblyProgram, PeepholeReport]:
        report = PeepholeReport(before=_count(program.text))
        text = list(program.text)
        while True:
            report.passes += 1
            text, changed = _one_pass(text, report.applied)
            if not changed:
                break
        report.after = _count(text)
        return AssemblyProgram(program.data, tuple(text)), report


def _one_pass(items: list[TextItem], applied: dict[str, int]) -> tuple[list[TextItem], bool]:
    out: list[TextItem] = []
    changed = False
    index = 0
    while index < len(items):
        item = items[index]
        if isinstance(item, AssemblyInstruction):
            rule, replacement = _rewrite(item, out[-1] if out else None, items, index)
            if rule is not None:
                applied[rule] += 1
                changed = True
                if replacement is not None:
                    out.append(replacement)
                index += 1
                continue
        out.append(item)
        index += 1
    return out, changed


def _rewrite(instr: AssemblyInstruction, previous: TextItem | None, items: list[TextItem], index: int):
    """(regla, reemplazo) si alguna regla aplica a `instr`; reemplazo None = se elimina."""
    op, args = instr.opcode, instr.operands
    if op == "move" and args[0] == args[1]:
        return "R1", None
    if op == "move" and _same_move(previous, instr):
        return "R2", None
    if op == "addiu" and args[2] == Imm(0):
        return "R3", AssemblyInstruction("move", (args[0], args[1]), instr.comment)
    if op == "beq" and _same_reg(args[0], args[1]):
        return "R4", AssemblyInstruction("j", (args[2],), instr.comment)
    if op == "bne" and _same_reg(args[0], args[1]):
        return "R5", None
    if op == "j" and isinstance(args[0], LabelRef) and args[0].name in _labels_right_after(items, index):
        return "R6", None
    return None, None


def _same_move(previous: TextItem | None, instr: AssemblyInstruction) -> bool:
    # previous es lo ultimo que quedo en la salida: si es una etiqueta, la ventana se corta
    return (
        isinstance(previous, AssemblyInstruction)
        and previous.opcode == "move"
        and previous.operands == instr.operands
        and previous.operands[0] != previous.operands[1]
    )


def _same_reg(a, b) -> bool:
    return isinstance(a, Reg) and a == b


def _labels_right_after(items: list[TextItem], index: int) -> set[str]:
    labels = set()
    for item in items[index + 1:]:
        if not isinstance(item, LabelDef):
            break
        labels.add(item.name)
    return labels


def _count(items) -> int:
    return sum(isinstance(item, AssemblyInstruction) for item in items)
