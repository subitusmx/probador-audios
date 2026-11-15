#!/bin/bash
# Envía un archivo (.zip o .dmg) al servicio de notarización de Apple y espera el resultado.
# Requiere: APPLE_API_KEY_P8 (contenido del .p8), APPLE_API_KEY_ID, APPLE_API_ISSUER_ID
set -euo pipefail
ARCHIVO="$1"
CLAVE="${RUNNER_TEMP:-/tmp}/clave-api.p8"
printf '%s\n' "$APPLE_API_KEY_P8" > "$CLAVE"
AUTH=(--key "$CLAVE" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER_ID")

echo ">> Notarizando $ARCHIVO (suele tardar de 1 a 10 minutos)…"
RESULTADO="$(xcrun notarytool submit "$ARCHIVO" "${AUTH[@]}" --wait --timeout 45m --output-format json)"
echo "$RESULTADO"
ESTADO="$(/usr/bin/python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("status",""))' "$RESULTADO")"
ID="$(/usr/bin/python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("id",""))' "$RESULTADO")"
if [ "$ESTADO" != "Accepted" ]; then
  echo "::error::Apple rechazó la notarización ($ESTADO). Detalle:"
  [ -n "$ID" ] && xcrun notarytool log "$ID" "${AUTH[@]}" || true
  rm -f "$CLAVE"
  exit 1
fi
rm -f "$CLAVE"
echo ">> Notarización aceptada"
