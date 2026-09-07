"""
representacion visual del ast propio de compiscript, via Graphviz (SVG). parte de la
integracion (persona 3): no depende de nada mas que ast_nodes.py -- no conoce tipos,
simbolos ni diagnosticos, asi que corre sobre cualquier ast, tenga o no errores
semanticos.

recorre el ast con la misma introspeccion generica que usa AstVisitor.generic_visit
(dataclasses.fields), en vez de mantener un caso por tipo de nodo -- un nodo nuevo en
ast_nodes.py se dibuja solo, sin tocar este archivo (ocp).
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from itertools import count
from typing import Iterator

import graphviz

from compiler.ast_nodes import Node, Program

# atributos que, si el nodo los tiene y son un valor simple, se muestran en la etiqueta
# para hacer el diagrama legible sin abrir el codigo fuente al lado (ej: el nombre de un
# Identifier, el operador de un BinaryOp, el valor de un literal).
_LABEL_ATTRS = ("name", "op", "value", "class_name", "base_name", "keyword")


def _build_graph() -> "graphviz.Digraph":
    return graphviz.Digraph(
        name="AST",
        graph_attr={"rankdir": "TB"},
        node_attr={"shape": "box", "fontname": "monospace", "fontsize": "10"},
        edge_attr={"fontname": "monospace", "fontsize": "9"},
    )


def _label_for(node: Node) -> str:
    type_name = type(node).__name__
    for attr in _LABEL_ATTRS:
        if hasattr(node, attr):
            value = getattr(node, attr)
            if isinstance(value, (str, int, bool)):
                return f"{type_name}\n{value!r}\n({node.line}:{node.column})"
    return f"{type_name}\n({node.line}:{node.column})"


def _add_node(graph: "graphviz.Digraph", node: Node, ids: Iterator[int], parent_id: str | None, edge_label: str) -> None:
    node_id = f"n{next(ids)}"
    graph.node(node_id, label=_label_for(node))
    if parent_id is not None:
        graph.edge(parent_id, node_id, label=edge_label)
    if not is_dataclass(node):
        return
    for field in fields(node):
        _add_field(graph, getattr(node, field.name), ids, node_id, field.name)


def _add_field(graph: "graphviz.Digraph", value: object, ids: Iterator[int], parent_id: str, field_name: str) -> None:
    if isinstance(value, Node):
        _add_node(graph, value, ids, parent_id, field_name)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, Node):
                _add_node(graph, item, ids, parent_id, f"{field_name}[{index}]")


def build_graph(program: Program) -> "graphviz.Digraph":
    """construye el objeto Digraph completo, para quien quiera manipularlo directo."""
    graph = _build_graph()
    _add_node(graph, program, count(), None, "")
    return graph


def to_dot(program: Program) -> str:
    """fuente DOT del ast, sin invocar el binario 'dot' -- util para tests sin graphviz instalado."""
    return build_graph(program).source


def render_svg(program: Program) -> str:
    """
    corre el binario 'dot' (via el paquete graphviz) y devuelve el SVG como texto.
    lanza graphviz.backend.ExecutableNotFound si 'dot' no esta en el PATH -- quien
    llame (compiler_service.compile_source) decide como degradar ese caso.
    """
    return build_graph(program).pipe(format="svg", encoding="utf-8")
