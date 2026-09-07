"""
test de regresion estructural para los modulos de la semantica core, analogo a
tests/frontend/test_architecture.py: capas en dag estricto, y el catalogo CPS-1xx
propio no invade el rango del frontend ni se sale del suyo.
"""
import ast
import re
from pathlib import Path

from compiler.core_semantic_visitor import _MESSAGES as core_messages

COMPILER_DIR = Path(__file__).resolve().parents[2] / "compiler"

# capas de la semantica core: los modulos de reglas son puros (solo types.py, symbols.py
# y ast_nodes.py cuando necesitan isinstance de statements); core_semantic_visitor.py es
# el unico que coordina y el unico que conoce diagnostics.py; core_semantics.py es la
# fachada y el unico que conoce frontend.py.
_ALLOWED_IMPORTS = {
    "expression_rules": {"types"},
    "function_rules": {"types", "symbols"},
    "control_flow_rules": {"types", "ast_nodes"},
    "core_semantic_visitor": {
        "ast_nodes", "control_flow_rules", "diagnostics", "expression_rules",
        "function_rules", "scopes", "symbols", "types",
    },
    "core_semantics": {"ast_nodes", "core_semantic_visitor", "diagnostics", "frontend", "scopes"},
}


def _local_imports(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 and node.module.startswith("compiler."):
            names.add(node.module.split(".")[1])
    return names


def test_modulos_de_semantica_core_respetan_las_capas_permitidas():
    for module_name, allowed in _ALLOWED_IMPORTS.items():
        py_file = COMPILER_DIR / f"{module_name}.py"
        assert py_file.exists(), f"falta {module_name}.py"
        found = _local_imports(py_file) - {module_name}
        invalido = found - allowed
        assert not invalido, f"{module_name}.py importa de {invalido}, no permitido (solo {allowed})"


def test_reglas_puras_no_dependen_de_diagnostics():
    for module_name in ("expression_rules", "function_rules", "control_flow_rules"):
        found = _local_imports(COMPILER_DIR / f"{module_name}.py")
        assert "diagnostics" not in found, f"{module_name}.py no deberia depender de diagnostics.py"


def test_catalogo_cps1xx_tiene_formato_valido_y_no_se_sale_de_su_rango():
    patron = re.compile(r"^CPS-1\d{2}$")
    for code in core_messages:
        assert patron.match(code), f"codigo con formato invalido para la semantica core: {code}"


def test_catalogo_cps1xx_no_se_solapa_con_el_del_frontend():
    from compiler.diagnostics import _MESSAGES as frontend_messages
    assert set(core_messages) & set(frontend_messages) == set()
