"""
ide minimo (flask, una sola pantalla): pega codigo compiscript, lo compila, muestra
diagnosticos y el ast como svg. sin autenticacion, sin persistencia, sin autocompletado,
sin debugger -- alcance exacto que pide el pdf para la etapa de integracion.

CERO reglas semanticas aca (srp / gate c): la unica logica real de este modulo es tomar
el codigo fuente del request y pasarselo a compiler_service.compile_source, que es el
unico compositor del pipeline (frontend -> core -> extended -> visualizacion). este
archivo no importa frontend/core_semantics/extended_semantics/ast_visualizer por su
cuenta.
"""
from __future__ import annotations

from werkzeug.exceptions import RequestEntityTooLarge

from flask import Flask, jsonify, render_template, request

from compiler.compiler_service import compile_source
from compiler.frontend import MAX_SOURCE_BYTES

app = Flask(__name__)
# Margen fijo para las llaves, nombre de campo y comillas del objeto JSON. El
# compilador conserva MAX_SOURCE_BYTES como segunda defensa sobre el string ya
# decodificado.
JSON_ENVELOPE_BYTES = 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_SOURCE_BYTES + JSON_ENVELOPE_BYTES


def _error_response(message: str, status: int):
    return jsonify({"success": False, "diagnostics": [], "ast_svg": None, "error": message}), status


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return _error_response("el request excede el tamano maximo permitido", 413)


@app.get("/")
def index():
    return render_template("index.html")


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
        "ast_svg": result.ast_svg,
        "error": None,
    })


if __name__ == "__main__":
    app.run(debug=True)
