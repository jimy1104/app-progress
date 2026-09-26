#!/bin/bash
# Arranque de Gestión de Logística en Azure App Service.
#
# Funciona aunque el despliegue haya quedado incompleto:
#   - si Azure construyó el sitio (antenv), usa esas librerías;
#   - si no las instaló, las instala UNA vez en /home/site/deps (persiste
#     entre reinicios) y las reutiliza;
#   - se ubica solo en la carpeta donde está wsgi.py.
#
# Comando de inicio (Portal → Configuración → General), en una sola línea:
#   bash -c 'W=$(find "$PWD" /home/site/wwwroot -maxdepth 4 -name arranque_azure.sh -not -path "*/antenv/*" 2>/dev/null | head -1); if [ -z "$W" ]; then Z=$(ls /home/site/wwwroot/*.zip 2>/dev/null | head -1); [ -n "$Z" ] && python -m zipfile -e "$Z" /home/site/wwwroot; W=$(find /home/site/wwwroot -maxdepth 4 -name arranque_azure.sh 2>/dev/null | head -1); fi; exec bash "$W"'
set -e
cd "$(dirname "$0")"
echo "[arranque] carpeta de la app: $PWD"

if ! python -c "import flask, openpyxl, fitz, gunicorn" 2>/dev/null; then
  DEPS=/home/site/deps
  HUELLA=$(md5sum requirements.txt | cut -c1-12)
  if [ ! -f "$DEPS/.listo-$HUELLA" ]; then
    echo "[arranque] instalando librerías en $DEPS (solo la primera vez, 2 a 5 minutos)…"
    rm -rf "$DEPS" && mkdir -p "$DEPS"
    python -m pip install --no-cache-dir --disable-pip-version-check --target "$DEPS" -r requirements.txt
    touch "$DEPS/.listo-$HUELLA"
  fi
  export PYTHONPATH="$DEPS${PYTHONPATH:+:$PYTHONPATH}"
fi

export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
exec python -m gunicorn -c gunicorn.conf.py --bind="0.0.0.0:${PORT:-8000}" --timeout 600 wsgi:app
