"""
helper para correr ensamblador en mars 4.5 desde los tests.

mars devuelve exit code 0 aunque falle el ensamblado o la ejecucion, asi que el estado
se saca leyendo stdout/stderr. el limite de pasos es obligatorio: sin el, un bucle
infinito colgaria la suite. si falta java o el jar, falla con instrucciones (no se salta).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

JAR_PATH = Path(__file__).resolve().parents[2] / "tools" / "Mars4_5.jar"
DEFAULT_MAX_STEPS = 200_000
_TIMEOUT_SECONDS = 60

_ERROR_LINE = re.compile(r"^Error in .* line \d+", re.MULTILINE)
_RUNTIME_EXCEPTION = re.compile(r"Runtime exception")
_STEP_LIMIT = re.compile(r"maximum step limit", re.IGNORECASE)
_REGISTER_LINE = re.compile(r"^(\$\w+)\s+(-?\d+|0x[0-9a-fA-F]+)\s*$")


@dataclass(frozen=True)
class MarsResult:
    stdout: str          # lo que imprimio el programa (sin lineas de registros)
    registers: dict[str, int] = field(default_factory=dict)
    raw: str = ""        # salida completa de mars, para mensajes de falla
    assembly_error: bool = False
    runtime_error: bool = False
    step_limit_hit: bool = False

    @property
    def ok(self) -> bool:
        return not (self.assembly_error or self.runtime_error or self.step_limit_hit)


class MarsUnavailable(AssertionError):
    """java o el jar no estan: el test debe fallar, no saltarse."""


def _require_environment() -> str:
    java = shutil.which("java")
    if java is None:
        raise MarsUnavailable("falta java en el PATH (mars 4.5 lo necesita)")
    if not JAR_PATH.is_file():
        raise MarsUnavailable(f"falta {JAR_PATH}: correr tools/fetch_mars.sh o tools/fetch_mars.ps1")
    return java


def _parse_register(value: str) -> int:
    number = int(value, 16) if value.lower().startswith("0x") else int(value)
    # mars imprime en hex sin signo cuando se lo pide asi, se normaliza a 32 bits con signo
    return number - (1 << 32) if number >= (1 << 31) else number


def run_mars(source: str, registers: tuple[str, ...] = (), max_steps: int = DEFAULT_MAX_STEPS) -> MarsResult:
    """ensambla y corre `source`. `registers` son nombres tipo '$sp' a leer al terminar."""
    if max_steps <= 0:
        raise ValueError("el limite de pasos es obligatorio y positivo")
    java = _require_environment()
    with tempfile.TemporaryDirectory() as tmp:
        asm = Path(tmp) / "program.asm"
        asm.write_text(source, encoding="utf-8")
        command = [java, "-Djava.awt.headless=true", "-jar", str(JAR_PATH), "nc", str(asm), str(max_steps), *registers]
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS, check=False,
        )
    raw = completed.stdout + completed.stderr
    return _interpret(raw, registers)


def _failed(text: str) -> bool:
    return bool(_ERROR_LINE.search(text) or _STEP_LIMIT.search(text))


def _interpret(raw: str, wanted: tuple[str, ...]) -> MarsResult:
    registers: dict[str, int] = {}
    program_lines: list[str] = []
    for line in raw.splitlines(keepends=True):
        match = _REGISTER_LINE.match(line.strip())
        if match and match.group(1) in wanted:
            registers[match.group(1)] = _parse_register(match.group(2))
        else:
            program_lines.append(line)
    text = "".join(program_lines)
    # mars siempre agrega un salto de linea al terminar; no es del programa
    if not _failed(text) and text.endswith("\n"):
        text = text[:-1]
    # un error de ensamblado y uno de ejecucion empiezan igual ("Error in ... line n");
    # el de ejecucion es el unico que menciona "Runtime exception"
    has_error = bool(_ERROR_LINE.search(text))
    runtime = has_error and bool(_RUNTIME_EXCEPTION.search(text))
    return MarsResult(
        stdout=text, registers=registers, raw=raw,
        assembly_error=has_error and not runtime, runtime_error=runtime,
        step_limit_hit=bool(_STEP_LIMIT.search(text)),
    )
