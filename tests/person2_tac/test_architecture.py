"""
reglas de capas del tac core (gate B): no toca antlr ni el frontend, no vuelve a hacer
type checking, no crea otra tabla de simbolos ni otros managers de temporales/etiquetas
y no arma texto tac a mano (eso es solo del serializer).
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TAC_MODULES = sorted(
    ROOT / "compiler" / "tac" / name
    for name in ("core_generator.py", "expression_lowering.py", "control_flow_lowering.py", "function_lowering.py")
)

FORBIDDEN_PREFIXES = (
    "antlr4", "compiler.generated", "compiler.frontend", "compiler.ast_builder", "compiler.symbol_collector",
    # type checking de proyecto 01: el ir no lo repite
    "compiler.core_semantic_visitor", "compiler.extended_semantic_visitor",
    "compiler.expression_rules", "compiler.function_rules", "compiler.control_flow_rules",
    "compiler.class_rules", "compiler.array_rules",
    # infraestructura que solo se usa a traves de IRBuilder / prepare
    "compiler.ir.temp_manager", "compiler.ir.label_manager", "compiler.ir.serializer",
)
FORBIDDEN_CALLS = {"SymbolTable", "Scope", "TempManager", "LabelManager", "TACInstruction", "push", "prepare"}


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


def _called_names(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Call):
            func = node.func
            names.add(func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", ""))
    return names


def test_estan_los_cuatro_entregables():
    assert all(path.exists() for path in TAC_MODULES)


@pytest.mark.parametrize("path", TAC_MODULES, ids=lambda p: p.name)
def test_no_importa_antlr_frontend_ni_reglas_semanticas(path):
    for module in _imports(path):
        assert not module.startswith(FORBIDDEN_PREFIXES), f"{path.name} importa {module}"


@pytest.mark.parametrize("path", TAC_MODULES, ids=lambda p: p.name)
def test_no_crea_tablas_scopes_managers_ni_instrucciones_a_mano(path):
    assert not (_called_names(path) & FORBIDDEN_CALLS), f"{path.name} llama {_called_names(path) & FORBIDDEN_CALLS}"


@pytest.mark.parametrize("path", TAC_MODULES, ids=lambda p: p.name)
def test_no_arma_texto_tac_con_strings(path):
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value.strip()
            assert not text.startswith(("MOV ", "BIN ", "IF_FALSE ", "GOTO ", "CALL ", "t0 =")), \
                f"{path.name} arma tac a mano: {node.value!r}"


def test_la_semantica_y_el_ir_base_no_dependen_del_tac():
    for path in list((ROOT / "compiler").glob("*.py")) + list((ROOT / "compiler" / "ir").glob("*.py")) \
            + list((ROOT / "compiler" / "runtime").glob("*.py")):
        if path.name == "compiler_service.py":
            continue  # el compositor del pipeline (persona 3) si puede
        assert not any(m.startswith("compiler.tac") for m in _imports(path)), f"{path.name} importa compiler.tac"


def test_generador_extensible_por_herencia():
    """persona 3 hereda de CoreTacGenerator: los ganchos tienen que existir y ser metodos."""
    from compiler.tac.core_generator import CoreTacGenerator

    for hook in ("lower_member_assignment", "lower_method_call", "emit_arguments", "jump_targets",
                 "lower_value", "lower_effect", "release", "variable_ref", "visit_FunctionDecl"):
        assert callable(getattr(CoreTacGenerator, hook)), hook
