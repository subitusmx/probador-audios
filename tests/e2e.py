"""
Prueba de punta a punta contra la app ya encendida (solo usa la biblioteca estándar).

  python tests/e2e.py --url http://127.0.0.1:8765 --audio voz.wav --texto "..." --idioma es

Comprueba que:
  1) el audio correcto con su texto sale "correcto" (o con diferencias mínimas), y
  2) si al texto se le agregan palabras que no se dijeron, la app las marca como faltantes.
"""
import argparse
import json
import mimetypes
import sys
import time
import urllib.request
import uuid
from pathlib import Path


def pedir(url, datos=None, tipo=None, timeout=60):
    req = urllib.request.Request(url, data=datos)
    if tipo:
        req.add_header("Content-Type", tipo)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def esperar_servidor(base, minutos):
    limite = time.time() + minutos * 60
    while time.time() < limite:
        try:
            if pedir(base + "/api/ping", timeout=3).get("ok"):
                return
        except Exception:
            pass
        time.sleep(3)
    sys.exit("La app no arrancó a tiempo")


def subir(base, ruta):
    limite = "----" + uuid.uuid4().hex
    tipo = mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
    cuerpo = (
        f"--{limite}\r\nContent-Disposition: form-data; name=\"archivo\"; filename=\"{ruta.name}\"\r\n"
        f"Content-Type: {tipo}\r\n\r\n"
    ).encode() + ruta.read_bytes() + f"\r\n--{limite}--\r\n".encode()
    r = pedir(base + "/api/subir", cuerpo, f"multipart/form-data; boundary={limite}")
    return r["archivos"][0]["id"]


def verificar(base, audio_id, texto, idioma, minutos):
    cuerpo = json.dumps({"audio": audio_id, "texto": texto, "idioma": idioma}).encode()
    tid = pedir(base + "/api/verificar", cuerpo, "application/json")["trabajo"]
    limite = time.time() + minutos * 60
    ultimo = ""
    while time.time() < limite:
        r = pedir(f"{base}/api/trabajo/{tid}")
        if r["mensaje"] != ultimo:
            ultimo = r["mensaje"]
            print("   …", ultimo, flush=True)
        if r["estado"] == "listo":
            return r["resultado"]
        if r["estado"] in ("error", "perdido"):
            sys.exit(f"Error al verificar: {r['mensaje']}")
        time.sleep(3)
    sys.exit("La verificación tardó demasiado")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--audio", required=True)
    ap.add_argument("--texto", required=True)
    ap.add_argument("--idioma", default="es")
    ap.add_argument("--minutos", type=float, default=25)
    a = ap.parse_args()

    esperar_servidor(a.url, a.minutos)
    print(">> Servidor listo", flush=True)
    audio_id = subir(a.url, Path(a.audio))

    print(">> Prueba 1: texto correcto", flush=True)
    r = verificar(a.url, audio_id, a.texto, a.idioma, a.minutos)
    print(f"   veredicto={r['veredicto']} porcentaje={r['porcentaje']} escuchado={r['transcripcion']!r}")
    if r["porcentaje"] < 80:
        sys.exit("FALLÓ: la concordancia con el texto correcto debería ser alta")

    extra = " y además esto nunca se dijo en el audio" if a.idioma == "es" else " and this part was never spoken at all"
    print(">> Prueba 2: texto con palabras que no se dijeron", flush=True)
    r2 = verificar(a.url, audio_id, a.texto + extra, a.idioma, a.minutos)
    print(f"   veredicto={r2['veredicto']} porcentaje={r2['porcentaje']} omitidas={r2['omitidas']}")
    if r2["omitidas"] < 4 or r2["veredicto"] in ("correcto", "correcto_menor"):
        sys.exit("FALLÓ: debería detectar las palabras faltantes")

    print(">> TODO BIEN", flush=True)


if __name__ == "__main__":
    main()
