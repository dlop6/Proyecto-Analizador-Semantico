"""
reglas de capas del backend: consume el ir y el layout, nunca el ast ni el texto, y nada
de lo anterior depende de el. solo cuentan los imports de runtime (lo que esta bajo
`if TYPE_CHECKING:` es para anotaciones).
"""
import ast
from pathlib import Path

import pytest

COMPILER = Path(__file__).resolve().parents[2] / "compiler"
BACKEND_MODULES = sorted((COMPILER / "backend").rglob("*.py"))
UPSTREAM_MODULES = (
    sorted(p for p in COMPILER.glob("*.py") if p.name != "compiler_service.py")
    + sorted((COMPILER / "ir").glob("*.py"))
    + sorted((COMPILER / "runtime").glob("*.py"))
    + sorted((COMPILER / "tac").glob("*.py"))
)

# lo unico de compiler.* que el backend puede usar: su propio paquete, el ir, los registros
# de activacion / almacenamiento (valores puros) y los tipos
ALLOWED_COMPILER_IMPORTS = (
    "compiler.backend", "compiler.ir", "compiler.runtime.activation_records", "compiler.runtime.storage",
    "compiler.types",
)
FORBIDDEN_EXTERNAL = ("antlr4", "flask", "ide")


def _runtime_imports(py_file: Path) -> set[str]:
    def walk(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.If) and isinstance(child.test, ast.Name) and child.test.id == "TYPE_CHECKING":
                continue
            yield child
            yield from walk(child)

    found: set[str] = set()
    for node in walk(ast.parse(py_file.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def test_hay_modulos_que_revisar():
    names = {p.name for p in BACKEND_MODULES}
    assert {"builder.py", "model.py", "operands.py", "abi.py", "frame_planner.py", "register_allocator.py",
            "activation.py", "helpers.py"} <= names
    assert len(UPSTREAM_MODULES) > 20


@pytest.mark.parametrize("py_file", BACKEND_MODULES, ids=lambda p: p.name)
def test_el_backend_solo_depende_del_ir_y_de_valores_puros(py_file):
    for module in _runtime_imports(py_file):
        assert not module.split(".")[0] in FORBIDDEN_EXTERNAL, f"{py_file.name} importa {module}"
        if module.startswith("compiler"):
            assert module.startswith(ALLOWED_COMPILER_IMPORTS), f"{py_file.name} importa {module}"


@pytest.mark.parametrize("py_file", UPSTREAM_MODULES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_nada_anterior_al_backend_lo_importa(py_file):
    for module in _runtime_imports(py_file):
        assert not module.startswith("compiler.backend"), f"{py_file.name} importa {module}"
