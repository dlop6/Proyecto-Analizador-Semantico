"""
modelo del ensamblador: instrucciones, etiquetas y datos. nadie arma texto de ensamblador
a mano; todo pasa por estos objetos y por la tabla de firmas.

SIGNATURES dice, por opcode, que combinaciones de operandos son validas
(r = registro, i = inmediato, l = etiqueta, m = memoria). agregar una instruccion al
backend es agregar una entrada aca (abierto/cerrado), nada mas.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from compiler.backend.mips.operands import Imm, LabelMem, LabelRef, Mem, Operand, Reg, validate_label

_THREE_REGS = (("r", "r", "r"),)
_REG_REG_IMM = (("r", "r", "i"),)
_COMPARE = (("r", "r", "r"),)

SIGNATURES = MappingProxyType({
    # carga y movimiento
    "li": (("r", "i"),), "la": (("r", "l"),), "move": (("r", "r"),),
    "lw": (("r", "m"),), "sw": (("r", "m"),), "lb": (("r", "m"),), "lbu": (("r", "m"),), "sb": (("r", "m"),),
    # aritmetica y logica
    "add": _THREE_REGS, "sub": _THREE_REGS, "mul": _THREE_REGS, "div": _THREE_REGS, "rem": _THREE_REGS,
    "and": _THREE_REGS, "or": _THREE_REGS, "xor": _THREE_REGS,
    "addi": _REG_REG_IMM, "andi": _REG_REG_IMM, "ori": _REG_REG_IMM, "xori": _REG_REG_IMM,
    "sll": _REG_REG_IMM, "srl": _REG_REG_IMM,
    "neg": (("r", "r"),), "not": (("r", "r"),),
    # comparaciones que dejan 0/1
    "seq": _COMPARE, "sne": _COMPARE, "slt": _COMPARE, "sle": _COMPARE, "sgt": _COMPARE, "sge": _COMPARE,
    # saltos
    "beq": (("r", "r", "l"),), "bne": (("r", "r", "l"),),
    "blt": (("r", "r", "l"),), "ble": (("r", "r", "l"),), "bgt": (("r", "r", "l"),), "bge": (("r", "r", "l"),),
    "beqz": (("r", "l"),), "bnez": (("r", "l"),),
    "j": (("l",),), "jal": (("l",),), "jr": (("r",),), "jalr": (("r",),),
    # sistema
    "syscall": ((),), "nop": ((),),
})

# opcodes que transfieren el control; emit_branch solo acepta estos
BRANCH_OPCODES = frozenset({
    "beq", "bne", "blt", "ble", "bgt", "bge", "beqz", "bnez", "j", "jal", "jr", "jalr",
})
CALL_OPCODES = frozenset({"jal", "jalr"})

DATA_DIRECTIVES = frozenset({"asciiz", "word", "space"})


def _kind(operand: Operand) -> str:
    if isinstance(operand, Reg):
        return "r"
    if isinstance(operand, Imm):
        return "i"
    if isinstance(operand, LabelRef):
        return "l"
    if isinstance(operand, (Mem, LabelMem)):
        return "m"
    raise ValueError(f"operando desconocido: {operand!r}")


@dataclass(frozen=True, slots=True)
class AssemblyInstruction:
    opcode: str
    operands: tuple[Operand, ...] = ()
    comment: str | None = None

    def __post_init__(self) -> None:
        allowed = SIGNATURES.get(self.opcode)
        if allowed is None:
            raise ValueError(f"instruccion mips no permitida: {self.opcode!r}")
        shape = tuple(_kind(op) for op in self.operands)
        if shape not in allowed:
            raise ValueError(f"operandos invalidos para {self.opcode}: {', '.join(map(str, self.operands))}")

    def render(self) -> str:
        text = f"    {self.opcode}" + (f" {', '.join(map(str, self.operands))}" if self.operands else "")
        return f"{text}    # {self.comment}" if self.comment else text


@dataclass(frozen=True, slots=True)
class LabelDef:
    name: str

    def __post_init__(self) -> None:
        validate_label(self.name)

    def render(self) -> str:
        return f"{self.name}:"


TextItem = AssemblyInstruction | LabelDef


@dataclass(frozen=True, slots=True)
class DataItem:
    label: str
    directive: str
    value: int | str | tuple[int | str, ...]

    def __post_init__(self) -> None:
        validate_label(self.label)
        if self.directive not in DATA_DIRECTIVES:
            raise ValueError(f"directiva de datos no permitida: {self.directive!r}")
        if self.directive == "asciiz" and not isinstance(self.value, str):
            raise ValueError(".asciiz espera un string")
        if self.directive == "space" and (not isinstance(self.value, int) or self.value < 0 or self.value % 4):
            raise ValueError(".space espera un tamaño en bytes multiplo de 4")
        if self.directive == "word" and not self._valid_words():
            raise ValueError(".word espera enteros o etiquetas")

    def _valid_words(self) -> bool:
        values = self.value if isinstance(self.value, tuple) else (self.value,)
        for item in values:
            if isinstance(item, bool):
                return False
            if isinstance(item, str):
                validate_label(item)
            elif not isinstance(item, int):
                return False
        return bool(values)

    def render(self) -> str:
        if self.directive == "asciiz":
            return f'{self.label}: .asciiz "{_escape(self.value)}"'
        if self.directive == "space":
            return f"{self.label}: .space {self.value}"
        values = self.value if isinstance(self.value, tuple) else (self.value,)
        return f"{self.label}: .word {', '.join(map(str, values))}"


_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}


def _escape(text: str) -> str:
    out = []
    for char in text:
        if char in _ESCAPES:
            out.append(_ESCAPES[char])
        elif 32 <= ord(char) < 127:
            out.append(char)
        else:
            raise ValueError(f"caracter no soportado en .asciiz: {char!r} (solo ascii imprimible)")
    return "".join(out)


@dataclass(frozen=True, slots=True)
class AssemblyProgram:
    data: tuple[DataItem, ...]
    text: tuple[TextItem, ...]

    def render(self) -> str:
        lines = [".data", *(item.render() for item in self.data), "", ".text", *(item.render() for item in self.text)]
        return "\n".join(lines) + "\n"
