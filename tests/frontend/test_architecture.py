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


def _local_imports(py_file: Path) -> set[str]:
    """nombres de modulos hermanos (dentro de compiler/) que importa este archivo."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            # imports relativos tipo "from . import x" o "from .types import y"
            if node.module and node.level >= 1:
                names.add(node.module.split(".")[0])
            elif node.level >= 1 and node.module is None:
                for alias in node.names:
                    names.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("compiler."):
                    names.add(alias.name.split(".")[1])
    return names


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
