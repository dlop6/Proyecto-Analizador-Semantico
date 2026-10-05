"""
test de regresion estructural: el grafo de dependencias entre modulos de compiler/
tiene que ser un dag estricto, sin ciclos. si alguien mete un import que rompe la
capa (por ejemplo types.py importando symbols.py), este test lo agarra.
"""
import ast
from pathlib import Path

COMPILER_DIR = Path(__file__).resolve().parents[2] / "compiler"

# capas permitidas: cada modulo solo puede importar de los que estan a su derecha o mas abajo.
# esto es literal la arquitectura descrita en el plan:
# frontend -> symbol_collector -> {scopes -> symbols -> types} + {ast_builder -> ast_nodes -> types} + diagnostics
_ALLOWED_IMPORTS = {
    "types": set(),
    "diagnostics": set(),
    "ast_nodes": {"types"},
    "symbols": {"types"},
    "scopes": {"symbols", "types"},
    "ast_builder": {"ast_nodes", "types", "diagnostics", "generated"},
    "symbol_collector": {"ast_nodes", "scopes", "symbols", "types", "diagnostics"},
    "frontend": {"ast_builder", "ast_nodes", "symbol_collector", "scopes", "symbols",
                 "types", "diagnostics", "generated"},
}


def _is_type_checking_block(node: ast.AST) -> bool:
    # lo de adentro de `if TYPE_CHECKING:` es solo para anotaciones, no es dependencia real
    return isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"


def _runtime_nodes(node: ast.AST):
    for child in ast.iter_child_nodes(node):
        if _is_type_checking_block(child):
            continue
        yield child
        yield from _runtime_nodes(child)


def _local_imports(py_file: Path) -> set[str]:
    """nombres de modulos hermanos (dentro de compiler/) que importa este archivo en runtime."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in _runtime_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and node.module.startswith("compiler."):
                names.add(node.module.split(".")[1])
            elif node.level >= 1 and node.module:
                names.add(node.module.split(".")[0])
            elif node.level >= 1:
                names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("compiler."):
                    names.add(alias.name.split(".")[1])
    return names


def test_el_detector_ve_los_imports_reales():
    # antes este detector no veia `from compiler.x import y` y el test pasaba en vacio
    assert {"ast_builder", "symbol_collector", "generated"} <= _local_imports(COMPILER_DIR / "frontend.py")
    assert _local_imports(COMPILER_DIR / "scopes.py") == {"symbols"}


def test_sin_ciclos_de_import_entre_modulos_de_compiler():
    for module_name, allowed in _ALLOWED_IMPORTS.items():
        py_file = COMPILER_DIR / f"{module_name}.py"
        if not py_file.exists():
            continue  # se van agregando conforme avanzan las fases del plan
        found = _local_imports(py_file)
        found -= {module_name}  # ignorar self-import trivial si lo hubiera
        invalido = found - allowed
        assert not invalido, (
            f"{module_name}.py importa de {invalido}, lo cual no esta permitido por la "
            f"arquitectura en capas (solo puede importar de {allowed})"
        )


def test_types_no_depende_de_symbols_ni_ast_nodes():
    types_file = COMPILER_DIR / "types.py"
    found = _local_imports(types_file)
    assert "symbols" not in found
    assert "ast_nodes" not in found
