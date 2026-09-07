"""
ide minimo (flask, una sola pantalla): pega codigo compiscript, lo compila, muestra
diagnosticos, el ast como svg y la tabla de simbolos. sin autenticacion, sin
persistencia, sin autocompletado, sin debugger -- alcance exacto que pide el pdf
para la etapa de integracion.

CERO reglas semanticas aca (srp / gate c): la unica logica real de este modulo es tomar
el codigo fuente del request y pasarselo a compiler_service.compile_source, que es el
unico compositor del pipeline (frontend -> core -> extended -> visualizacion). este
archivo no importa frontend/core_semantics/extended_semantics/ast_visualizer por su
cuenta. la serializacion de la tabla de simbolos a json SI vive aca (es presentacion
pura, no logica semantica): recorre Scope.children (arbol ya armado por scopes.py) y
listas planas de campos/metodos por clase, no reinterpreta ninguna regla.
"""
from __future__ import annotations

from werkzeug.exceptions import RequestEntityTooLarge

from flask import Flask, jsonify, render_template, request

from compiler.compiler_service import compile_source
from compiler.frontend import MAX_SOURCE_BYTES
from compiler.scopes import Scope, SymbolTable
from compiler.symbols import ClassSymbol, FunctionSymbol, Symbol

app = Flask(__name__)
# Margen fijo para las llaves, nombre de campo y comillas del objeto JSON. El
# compilador conserva MAX_SOURCE_BYTES como segunda defensa sobre el string ya
# decodificado.
JSON_ENVELOPE_BYTES = 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_SOURCE_BYTES + JSON_ENVELOPE_BYTES


def _serialize_symbol(sym: Symbol) -> dict:
    """
    representacion minima y uniforme de un simbolo para la ui: nombre, categoria
    (variable/funcion/clase), tipo como texto, y detalle segun su categoria. si
    algun dia se agrega un tipo de simbolo nuevo, este es el unico lugar a tocar.
    """
    base = {
        "name": sym.name,
        "line": sym.line,
        "column": sym.column,
        "type": str(sym.type) if sym.type is not None else None,
    }
    if isinstance(sym, FunctionSymbol):
        base["kind"] = "function"
        base["params"] = [f"{p.name}: {p.type}" for p in sym.params]
        base["return_type"] = str(sym.return_type) if sym.return_type is not None else None
        base["is_constructor"] = sym.is_constructor
        base["is_method"] = sym.is_method
    elif isinstance(sym, ClassSymbol):
        base["kind"] = "class"
        base["parent_name"] = sym.parent_name
        base["fields"] = [_serialize_symbol(f) for f in sym.fields.values()]
        base["methods"] = [_serialize_symbol(m) for m in sym.methods.values()]
    else:
        base["kind"] = "variable"
        base["is_const"] = getattr(sym, "is_const", False)
        base["is_param"] = getattr(sym, "is_param", False)
    return base


def _serialize_scope(scope: Scope) -> dict:
    """nodo del arbol de scopes: su tipo, nombre legible, simbolos propios e hijos anidados."""
    return {
        "kind": scope.kind.name,
        "name": scope.name,
        "symbols": [_serialize_symbol(s) for s in scope.symbols.values()],
        "children": [_serialize_scope(child) for child in scope.children],
    }


def _serialize_symbol_table(table: SymbolTable) -> dict:
    """la tabla completa como un solo arbol, listo para dibujarse en la ui sin logica extra."""
    return _serialize_scope(table.global_scope)


def _error_response(message: str, status: int):
    return jsonify({
        "success": False, "diagnostics": [], "ast_svg": None, "symbols": None, "error": message,
    }), status


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return _error_response("el request excede el tamano maximo permitido", 413)


@app.get("/")
def index():
    return render_template("index.html", max_source_bytes=MAX_SOURCE_BYTES)


@app.post("/api/compile")
def api_compile():
    if request.is_json:
        body = request.get_json(silent=True)
        if body is None:
            return _error_response("JSON invalido", 400)
    else:
        body = {}
    source = body.get("source", "")
    if not isinstance(source, str):
        return _error_response("'source' debe ser un string", 400)

    result = compile_source(source)
    return jsonify({
        "success": result.success,
        "diagnostics": [
            {
                "code": diag.code,
                "message": diag.message,
                "line": diag.line,
                "column": diag.column,
                "severity": diag.severity.value,
            }
            for diag in result.diagnostics
        ],
        "symbols": _serialize_symbol_table(result.symbols),
        "ast_svg": result.ast_svg,
        "error": None,
    })


if __name__ == "__main__":
    app.run(debug=True)
