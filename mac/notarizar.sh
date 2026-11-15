#!/bin/bash
# Envía un archivo (.zip o .dmg) al servicio de notarización de Apple y espera el resultado.
# Credenciales (cualquiera de las dos opciones):
#   A) Clave API:  APPLE_API_KEY_P8 (contenido del .p8), APPLE_API_KEY_ID, APPLE_API_ISSUER_ID
#   B) Apple ID:   APPLE_ID, APPLE_APP_PASSWORD (contraseña específica para apps), APPLE_TEAM_ID
set -euo pipefail
ARCHIVO="$1"
CLAVE="${RUNNER_TEMP:-/tmp}/clave-api.p8"
if [ -n "${APPLE_API_KEY_P8:-}" ]; then
  printf '%s\n' "$APPLE_API_KEY_P8" > "$CLAVE"
  AUTH=(--key "$CLAVE" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER_ID")
  echo ">> Usando clave API de App Store Connect"
elif [ -n "${APPLE_ID:-}" ]; then
  AUTH=(--apple-id "$APPLE_ID" --password "$APPLE_APP_PASSWORD" --team-id "$APPLE_TEAM_ID")
  echo ">> Usando Apple ID con contraseña específica para apps"
else
  echo "::error::Faltan credenciales de notarización (clave API o Apple ID)."
  exit 1
fi
trap 'rm -f "$CLAVE"' EXIT

echo ">> Notarizando $ARCHIVO (suele tardar de 1 a 10 minutos)…"
RESULTADO="$(xcrun notarytool submit "$ARCHIVO" "${AUTH[@]}" --wait --timeout 45m --output-format json)"
echo "$RESULTADO"
ESTADO="$(/usr/bin/python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("status",""))' "$RESULTADO")"
ID="$(/usr/bin/python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("id",""))' "$RESULTADO")"
if [ "$ESTADO" != "Accepted" ]; then
  echo "::error::Apple rechazó la notarización ($ESTADO). Detalle:"
  [ -n "$ID" ] && xcrun notarytool log "$ID" "${AUTH[@]}" || true
  exit 1
fi
echo ">> Notarización aceptada"
