#!/usr/bin/env bash
# Crea .venv en la raíz del workspace e instala las dependencias de extracción de PDF.
set -euo pipefail
cd "$(dirname "$0")/../../../.."
# recrea el venv si no funciona (p. ej. si se movió la carpeta del proyecto)
if ! .venv/bin/python -c "import sys" >/dev/null 2>&1; then
  rm -rf .venv
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --quiet --upgrade pip "pypdf[image]"
echo "OK: usa .venv/bin/python para ejecutar los scripts."
