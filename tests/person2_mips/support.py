"""
helpers de las pruebas del backend core: fuente .cps -> ir real -> CoreMipsBackend -> mars.
reusa el pipeline y el runner de mars de la base (tests/mips_base) en vez de duplicarlos.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from compiler.backend.mips.core_backend import CoreMipsBackend
from compiler.backend.mips.operands import A0, FP, T, V0, Imm, LabelRef, Mem

from tests.mips_base.mars_runner import MarsResult, run_mars
from tests.mips_base.pipeline import ir_for

MAX_STEPS = 3_000_000
INITIAL_SP = 0x7FFFEFFC


def backend_for(source: str, backend_class=CoreMipsBackend) -> CoreMipsBackend:
    program, layout = ir_for(source)
    return backend_class(program, layout)


def assemble(source: str, backend_class=CoreMipsBackend) -> str:
    return backend_for(source, backend_class).build().render()


def run(source: str, registers: tuple[str, ...] = (), backend_class=CoreMipsBackend) -> MarsResult:
    return run_mars(assemble(source, backend_class), registers=registers, max_steps=MAX_STEPS)


def output(source: str, backend_class=CoreMipsBackend) -> list[str]:
    """lineas que imprimio el programa; falla con la salida completa de mars si algo salio mal."""
    result = run(source, backend_class=backend_class)
    assert result.ok, result.raw
    return result.stdout.splitlines()


class TracingBackend(CoreMipsBackend):
    """
    instrumenta la ejecucion para reconstruir el arbol de activacion desde mars:
      - el llamado, apenas arma su frame, imprime "enter <fn> <params...>" leyendolos de su
        propio registro de activacion (offset($fp) del FramePlan);
      - el que llama, al volver, imprime "exit <fn> <$v0>".
    es una subclase de prueba (abierto/cerrado): el backend del producto no se toca. solo
    usa syscalls, que no tocan los $t, asi que no hace falta sincronizar el allocator.
    """

    def lower_func_begin(self, instr):
        super().lower_func_begin(instr)
        name, plan = instr.arg1.name, self.plans[instr.arg1.name]
        self._text(f"enter {name}")
        for offset in sorted(plan.param_offsets.values()):
            self._text(" ")
            self.builder.emit("lw", A0, Mem(offset, FP))
            self._syscall(1)
        # "frame <fn> <$fp> [<static link>]": donde quedo este registro de activacion
        self._text(f"\nframe {name} ")
        self.builder.emit("move", A0, FP)
        self._syscall(1)
        if plan.static_link is not None:
            self._text(" ")
            self.builder.emit("lw", A0, Mem(plan.static_link, FP))
            self._syscall(1)
        self._text("\n")

    def lower_call(self, instr):
        super().lower_call(instr)   # el valor devuelto sigue en $v0 (ya se copio a su destino)
        self.builder.emit("move", T[9], V0)   # la syscall de texto pisa $v0
        self._text(f"exit {instr.arg1.name} ")
        self.builder.emit("move", A0, T[9])
        self._syscall(1)
        self._text("\n")

    def _text(self, text: str) -> None:
        self.builder.emit("la", A0, LabelRef(self.builder.add_string(text)))
        self._syscall(4)

    def _syscall(self, code: int) -> None:
        self.builder.emit("li", V0, Imm(code))
        self.builder.emit("syscall")


@dataclass
class Activation:
    name: str
    args: tuple[str, ...] = ()
    returned: str | None = None
    children: list["Activation"] = field(default_factory=list)
    fp: int | None = None            # direccion de su registro de activacion
    static_link: int | None = None   # $fp del frame que recibio como static link

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    @property
    def label(self) -> str:
        call = f"{self.name}({', '.join(self.args)})" if self.name != "main" else "main"
        return call if self.returned is None else f"{call} -> {self.returned}"


def activation_tree(lines: list[str]) -> Activation:
    """arbol de activaciones a partir de las lineas enter/exit de una ejecucion; la raiz es main."""
    root = Activation("main")
    stack = [root]
    for line in lines:
        if not line.startswith(TRACE_PREFIXES):
            continue
        kind, name, *values = line.split()
        if kind == "frame":
            assert stack[-1].name == name
            stack[-1].fp = int(values[0])
            stack[-1].static_link = int(values[1]) if len(values) > 1 else None
        elif kind == "enter":
            node = Activation(name, tuple(values))
            stack[-1].children.append(node)
            stack.append(node)
        else:
            assert stack[-1].name == name, f"exit de {name} con {stack[-1].name} abierto"
            stack.pop().returned = values[0]
    assert stack == [root], "quedaron activaciones sin cerrar"
    return root


def render_tree(node: Activation, indent: str = "") -> list[str]:
    lines = [indent + node.label]
    for child in node.children:
        lines += render_tree(child, indent + "    ")
    return lines


def max_depth(node: Activation) -> int:
    return 1 + max((max_depth(child) for child in node.children), default=0)


def count(node: Activation) -> int:
    return 1 + sum(count(child) for child in node.children)


TRACE_PREFIXES = ("enter ", "exit ", "frame ")


def program_lines(lines: list[str]) -> list[str]:
    """lo que imprimio el programa, sin las lineas de la traza."""
    return [line for line in lines if not line.startswith(TRACE_PREFIXES)]
