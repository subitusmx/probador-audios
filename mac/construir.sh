#!/bin/bash
# Arma "Probador de Audios.app" (y la firma si hay identidad de Developer ID).
# Uso: VERSION=1.0.0 BUILD=12 MAC_IDENTIDAD="Developer ID Application: ..." mac/construir.sh
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${VERSION:-0.0.0}"
BUILD="${BUILD:-1}"
SALIDA="dist"
APP="$SALIDA/Probador de Audios.app"

rm -rf "$SALIDA"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

echo ">> Compilando (Apple Silicon + Intel)…"
swiftc -O -target arm64-apple-macos11 -o "$SALIDA/pa-arm64" mac/ProbadorAudios.swift
swiftc -O -target x86_64-apple-macos11 -o "$SALIDA/pa-x86_64" mac/ProbadorAudios.swift
lipo -create -output "$APP/Contents/MacOS/ProbadorAudios" "$SALIDA/pa-arm64" "$SALIDA/pa-x86_64"
rm -f "$SALIDA/pa-arm64" "$SALIDA/pa-x86_64"

sed -e "s/__VERSION__/$VERSION/" -e "s/__BUILD__/$BUILD/" mac/Info.plist > "$APP/Contents/Info.plist"
printf 'APPL????' > "$APP/Contents/PkgInfo"
cp recursos/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
cp mac/iniciar.sh "$APP/Contents/Resources/iniciar.sh"
chmod +x "$APP/Contents/Resources/iniciar.sh"
rsync -a --exclude "__pycache__" app/ "$APP/Contents/Resources/app/"
xattr -cr "$APP"

if [ -n "${MAC_IDENTIDAD:-}" ]; then
  echo ">> Firmando con: $MAC_IDENTIDAD"
  codesign --force --options runtime --timestamp --sign "$MAC_IDENTIDAD" "$APP"
else
  echo ">> Sin certificado: firma local (ad-hoc), solo para pruebas"
  codesign --force --sign - "$APP"
fi
codesign --verify --strict --verbose=2 "$APP"
echo ">> Listo: $APP"
