#!/usr/bin/env bash
# baja mars 4.5 (simulador mips) y verifica su hash. se corre desde la raiz: ./tools/fetch_mars.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JAR_PATH="$SCRIPT_DIR/Mars4_5.jar"
JAR_URL="https://github.com/dpetersanderson/MARS/releases/download/v.4.5.1/Mars4_5.jar"
# mismo hash pinneado que en el script de windows
EXPECTED_SHA256="ac340b676ba2b62246b9df77e62f81ad4447bcfd329ab539716bcd09950b7096"

if [ ! -f "$JAR_PATH" ]; then
  echo "descargando mars 4.5..."
  curl -sSLf -o "$JAR_PATH" "$JAR_URL"
fi

actual_hash="$(sha256sum "$JAR_PATH" | cut -d' ' -f1)"
if [ "$actual_hash" != "$EXPECTED_SHA256" ]; then
  rm -f "$JAR_PATH"
  echo "error: sha256 del jar no coincide (esperado $EXPECTED_SHA256, obtuvo $actual_hash). se aborta." >&2
  exit 1
fi
echo "mars verificado ok: $actual_hash"
