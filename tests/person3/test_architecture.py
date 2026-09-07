"""
test de regresion estructural para los modulos de la semantica extendida, analogo a
tests/person2/test_architecture.py: capas en dag estricto, y el catalogo CPS-2xx propio
no invade el rango del frontend ni el de la semantica core.
"""
import ast
import re
from pathlib import Path

from compiler.core_semantic_visitor import _MESSAGES as core_messages
from compiler.extended_semantic_visitor import _MESSAGES as extended_messages

COMPILER_DIR = Path(__file__).resolve().parents[2] / "compiler"

# capas de la semantica extendida: los modulos de reglas son puros (types.py, symbols.py,
# y function_rules.py -- class_rules.py reusa check_call en vez de duplicarlo);
# extended_semantic_visitor.py es el unico que coordina y el unico que conoce
# diagnostics.py/ast_nodes.py; extended_semantics.py es la fachada y el unico que conoce
# core_semantics.py.
_ALLOWED_IMPORTS = {
    "class_rules": {"function_rules", "symbols", "types"},
    "array_rules": {"types"},
    "extended_semantic_visitor": {
        "array_rules", "ast_nodes", "class_rules", "diagnostics", "scopes", "symbols", "types",
    },
    "extended_semantics": {"ast_nodes", "core_semantics", "diagnostics", "extended_semantic_visitor", "scopes"},
}


def _local_imports(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 and node.module.startswith("compiler."):
            names.add(node.module.split(".")[1])
    return names


def test_modulos_de_semantica_extendida_respetan_las_capas_permitidas():
    for module_name, allowed in _ALLOWED_IMPORTS.items():
        py_file = COMPILER_DIR / f"{module_name}.py"
        assert py_file.exists(), f"falta {module_name}.py"
        found = _local_imports(py_file) - {module_name}
        invalido = found - allowed
        assert not invalido, f"{module_name}.py importa de {invalido}, no permitido (solo {allowed})"


def test_reglas_puras_no_dependen_de_diagnostics():
    for module_name in ("class_rules", "array_rules"):
        found = _local_imports(COMPILER_DIR / f"{module_name}.py")
        assert "diagnostics" not in found, f"{module_name}.py no deberia depender de diagnostics.py"


def test_catalogo_cps2xx_tiene_formato_valido_y_no_se_sale_de_su_rango():
    patron = re.compile(r"^CPS-2\d{2}$")
    for code in extended_messages:
        assert patron.match(code), f"codigo con formato invalido para la semantica extendida: {code}"


def test_catalogo_cps2xx_no_se_solapa_con_el_del_frontend():
    from compiler.diagnostics import _MESSAGES as frontend_messages
    assert set(extended_messages) & set(frontend_messages) == set()


def test_catalogo_cps2xx_no_se_solapa_con_el_de_la_semantica_core():
    assert set(extended_messages) & set(core_messages) == set()
