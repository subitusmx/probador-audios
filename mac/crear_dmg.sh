#!/bin/bash
# Crea el instalador .dmg (la app + acceso a Aplicaciones para arrastrarla).
set -euo pipefail
cd "$(dirname "$0")/.."
DMG="dist/ProbadorAudios-Mac.dmg"
TEMP="dist/dmg"
rm -rf "$TEMP" "$DMG"
mkdir -p "$TEMP"
cp -R "dist/Probador de Audios.app" "$TEMP/"
ln -s /Applications "$TEMP/Aplicaciones"
hdiutil create -volname "Probador de Audios" -srcfolder "$TEMP" -ov -format UDZO "$DMG"
rm -rf "$TEMP"
if [ -n "${MAC_IDENTIDAD:-}" ]; then
  codesign --force --timestamp --sign "$MAC_IDENTIDAD" "$DMG"
fi
echo ">> Listo: $DMG"
