#!/bin/bash
# ------------------------------------------------------------
#  Probador de Audios (Mac) - arranque
#  Lo ejecuta la app "Probador de Audios.app". No hace falta abrirlo a mano.
#  Las líneas que empiezan con "ESTADO:" se muestran en la ventana de la app.
# ------------------------------------------------------------
AQUI="$(cd "$(dirname "$0")" && pwd)"

DATOS_APP="$HOME/Library/Application Support/ProbadorAudios"
mkdir -p "$DATOS_APP"
export PROBADOR_DATOS="$DATOS_APP"
export UV_CACHE_DIR="$DATOS_APP/uv-cache"
export UV_PYTHON_INSTALL_DIR="$DATOS_APP/python"
export UV_PYTHON_BIN_DIR="$DATOS_APP/python-bin"
export UV_PYTHON_PREFERENCE="only-managed"
export UV_NO_CONFIG=1
export UV_NO_PROGRESS=1
export PYTHONUNBUFFERED=1
UV="$DATOS_APP/bin/uv"

if [ ! -x "$UV" ]; then
  echo "ESTADO: Instalando el motor de la app (solo la primera vez, 1 o 2 minutos)…"
  instalador="$(mktemp "${TMPDIR:-/tmp}/probador.XXXXXX")"
  curl -LsSf https://astral.sh/uv/install.sh -o "$instalador" ||
    curl -LsSf https://github.com/astral-sh/uv/releases/latest/download/uv-installer.sh -o "$instalador"
  env UV_UNMANAGED_INSTALL="$DATOS_APP/bin" sh "$instalador"
  rm -f "$instalador"
  if [ ! -x "$UV" ]; then
    echo "ERROR: No se pudo instalar el motor de la app. Revisa tu conexión a internet y vuelve a abrirla."
    exit 1
  fi
fi

echo "ESTADO: Preparando la app (la primera vez descarga componentes y tarda unos minutos)…"
exec "$UV" run --python 3.12 "$AQUI/app/app.py" --sin-navegador
