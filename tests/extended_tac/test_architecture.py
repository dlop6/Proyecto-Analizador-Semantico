"""
reglas de capas del tac extendido: las mismas del core (no toca antlr ni el frontend, no
repite type checking, no crea otra tabla de simbolos ni otros managers y no arma texto tac
a mano) y ademas no recalcula la jerarquia de clases: todo sale del ClassLayout aplanado.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULES = sorted(
    ROOT / "compiler" / "tac" / name
    for name in ("extended_generator.py", "array_lowering.py", "object_lowering.py", "exception_lowering.py")
)

FORBIDDEN_PREFIXES = (
    "antlr4", "compiler.generated", "compiler.frontend", "compiler.ast_builder", "compiler.symbol_collector",
    "compiler.core_semantic_visitor", "compiler.extended_semantic_visitor",
    "compiler.expression_rules", "compiler.function_rules", "compiler.control_flow_rules",
    "compiler.class_rules", "compiler.array_rules",
    "compiler.ir.temp_manager", "compiler.ir.label_manager", "compiler.ir.serializer",
    "compiler.compiler_service", "flask", "ide",
)
FORBIDDEN_CALLS = {
    "SymbolTable", "Scope", "TempManager", "LabelManager", "TACInstruction", "push", "prepare",
    "lookup_member", "is_subclass",
}
FORBIDDEN_TEXT_PREFIXES = (
    "MOV ", "BIN ", "IF_FALSE ", "GOTO ", "CALL ", "t0 =", "NEW_OBJ ", "NEW_ARR ", "ARR_SET ", "CALL_METHOD ",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def test_estan_los_cuatro_entregables():
    assert all(path.exists() for path in MODULES)


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_importa_antlr_frontend_reglas_semanticas_ni_gui(path):
    for module in _imports(path):
        assert not module.startswith(FORBIDDEN_PREFIXES), f"{path.name} importa {module}"


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_crea_tablas_managers_ni_recalcula_la_jerarquia(path):
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            assert name not in FORBIDDEN_CALLS, f"{path.name} llama a {name}"
        if isinstance(node, ast.Attribute):
            assert node.attr != "parent", f"{path.name} recorre la jerarquia con .parent"


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_arma_texto_tac_a_mano(path):
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not node.value.startswith(FORBIDDEN_TEXT_PREFIXES), f"{path.name}: {node.value!r}"


def test_solo_el_compositor_del_pipeline_usa_el_generador_extendido():
    for path in sorted((ROOT / "compiler").rglob("*.py")):
        if path.name == "compiler_service.py" or path.parent.name == "tac":
            continue
        assert not any(m.startswith("compiler.tac") for m in _imports(path)), path.name
    assert "compiler.tac.extended_generator" in _imports(ROOT / "compiler" / "compiler_service.py")
    assert not any(m.startswith("compiler.tac") for m in _imports(ROOT / "ide" / "app.py"))
