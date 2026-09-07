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

from flask import Flask, jsonify, render_template, request

from compiler.compiler_service import compile_source

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/compile")
def api_compile():
    body = request.get_json(silent=True) or {}
    source = body.get("source", "")
    if not isinstance(source, str):
        return jsonify({"error": "'source' debe ser un string"}), 400

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
    })


if __name__ == "__main__":
    app.run(debug=True)
