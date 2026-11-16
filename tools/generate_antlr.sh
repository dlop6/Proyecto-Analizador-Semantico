#!/usr/bin/env bash
# regenera lexer, parser y visitor de python a partir de program/Compiscript.g4
# se corre desde la raiz del repo: ./tools/generate_antlr.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
JAR_PATH="$SCRIPT_DIR/antlr-4.13.1-complete.jar"
JAR_URL="https://www.antlr.org/download/antlr-4.13.1-complete.jar"
# mismo hash pinneado que en el script de windows, misma fuente de verdad
EXPECTED_SHA256="bc13a9c57a8dd7d5196888211e5ede657cb64a3ce968608697e4f668251a8487"

if [ ! -f "$JAR_PATH" ]; then
  echo "descargando antlr 4.13.1..."
  curl -sSL -o "$JAR_PATH" "$JAR_URL"
fi

actual_hash="$(sha256sum "$JAR_PATH" | cut -d' ' -f1)"
if [ "$actual_hash" != "$EXPECTED_SHA256" ]; then
  rm -f "$JAR_PATH"
  echo "error: sha256 del jar no coincide (esperado $EXPECTED_SHA256, obtuvo $actual_hash). se aborta." >&2
  exit 1
fi
echo "jar verificado ok: $actual_hash"

GRAMMAR_FILE="$REPO_ROOT/program/Compiscript.g4"
OUT_DIR="$REPO_ROOT/compiler/generated"

if [ ! -f "$GRAMMAR_FILE" ]; then
  echo "error: no se encontro la gramatica en $GRAMMAR_FILE" >&2
  exit 1
fi

echo "generando lexer/parser/visitor python..."
java -Xmx500M -cp "$JAR_PATH" org.antlr.v4.Tool \
  -Dlanguage=Python3 -visitor -no-listener \
  -o "$OUT_DIR" \
  "$GRAMMAR_FILE"

for f in CompiscriptLexer.py CompiscriptParser.py CompiscriptVisitor.py; do
  if [ ! -f "$OUT_DIR/$f" ]; then
    echo "error: no se genero el archivo esperado: $f" >&2
    exit 1
  fi
done

# antlr no genera __init__.py (no sabe que esto es un paquete python), asi que lo
# reponemos siempre -- si se borra compiler/generated entero (clon limpio, o alguien
# limpiando el directorio a mano) el import compiler.generated tiene que seguir andando.
cat > "$OUT_DIR/__init__.py" <<'EOF'
# unico punto de acoplamiento con lo que genera antlr en todo el proyecto.
# si algun dia cambia la ubicacion o la version, se toca nada mas este archivo.
from .CompiscriptLexer import CompiscriptLexer
from .CompiscriptParser import CompiscriptParser
from .CompiscriptVisitor import CompiscriptVisitor

__all__ = ["CompiscriptLexer", "CompiscriptParser", "CompiscriptVisitor"]
EOF

echo "listo. lexer, parser y visitor generados en compiler/generated"
