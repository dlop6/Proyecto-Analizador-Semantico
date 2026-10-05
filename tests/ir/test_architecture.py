"""
reglas de capas del ir (pdf, isp/dip): nadie fuera del frontend toca antlr, y la
semantica no depende del ir. solo cuentan los imports de runtime: lo que esta bajo
`if TYPE_CHECKING:` es para anotaciones y no genera dependencia.
"""
import ast
from pathlib import Path

import pytest

COMPILER = Path(__file__).resolve().parents[2] / "compiler"
IR_MODULES = sorted((COMPILER / "ir").glob("*.py")) + sorted((COMPILER / "runtime").glob("*.py"))
SEMANTIC_MODULES = sorted(p for p in COMPILER.glob("*.py") if p.name != "compiler_service.py")


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
    assert len(IR_MODULES) >= 9
    assert any(p.name == "frontend.py" for p in SEMANTIC_MODULES)


@pytest.mark.parametrize("py_file", IR_MODULES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_ir_y_runtime_no_importan_antlr(py_file):
    for module in _runtime_imports(py_file):
        assert not module.startswith("antlr4"), f"{py_file.name} importa {module}"
        assert not module.startswith("compiler.generated"), f"{py_file.name} importa {module}"


@pytest.mark.parametrize("py_file", SEMANTIC_MODULES, ids=lambda p: p.name)
def test_la_semantica_no_depende_del_ir(py_file):
    for module in _runtime_imports(py_file):
        assert not module.startswith(("compiler.ir", "compiler.runtime")), f"{py_file.name} importa {module}"


def test_storage_y_label_manager_son_hojas():
    for leaf in ("runtime/storage.py", "ir/label_manager.py", "ir/opcodes.py"):
        imports = {m for m in _runtime_imports(COMPILER / leaf) if m.startswith("compiler")}
        assert imports == set(), f"{leaf} importa {imports}"
