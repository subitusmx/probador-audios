# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = [
#   "flask>=3.0",
#   "faster-whisper>=1.1.0",
#   "num2words>=0.5.13",
# ]
# ///
"""
Probador de Audios — servidor local.

Transcribe cada audio con Whisper (en tu propia Mac, sin enviar nada a internet)
y lo compara con el texto original del guion.
"""
import json
import logging
import os
import queue
import socket
import sys
import threading
import time
import traceback
import urllib.request
import uuid
import webbrowser
from pathlib import Path

import shutil


# ---------------------------------------------------------------- Dónde se guarda todo
def carpeta_datos_app():
    """Carpeta donde viven el modelo de voz y los componentes (fuera de la carpeta de la app)."""
    if os.environ.get("PROBADOR_DATOS"):
        return Path(os.environ["PROBADOR_DATOS"])
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ProbadorAudios"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ProbadorAudios"
    return Path.home() / ".local" / "share" / "ProbadorAudios"


DATOS_APP = carpeta_datos_app()
CARPETA_MODELOS = DATOS_APP / "modelos"
if os.name == "nt" and not str(CARPETA_MODELOS).isascii():
    # El motor de voz no abre rutas con acentos/ñ en Windows (p. ej. C:\Users\Martín)
    CARPETA_MODELOS = Path(os.environ.get("SystemDrive", "C:") + "\\") / "ProbadorAudios" / "modelos"
CARPETA_MODELOS.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"] = str(CARPETA_MODELOS)
os.environ.pop("HF_HUB_CACHE", None)


def migrar_modelos_antiguos():
    """Las primeras versiones guardaban el modelo en ~/.cache/huggingface.
    Si está ahí, lo movemos a la carpeta nueva para no descargarlo otra vez."""
    viejo = Path.home() / ".cache" / "huggingface" / "hub"
    nuevo = CARPETA_MODELOS / "hub"
    for nombre in ("models--Systran--faster-whisper-large-v3",):
        origen, destino = viejo / nombre, nuevo / nombre
        if origen.is_dir() and not destino.exists():
            try:
                nuevo.mkdir(parents=True, exist_ok=True)
                shutil.move(str(origen), str(destino))
                print(f">> Modelo de voz movido a: {destino}", flush=True)
            except Exception as e:
                print(f">> No se pudo mover el modelo anterior ({e}); se descargará de nuevo.", flush=True)


migrar_modelos_antiguos()

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
# Descarga por HTTP normal: se puede medir el avance y se reanuda si se corta
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "30")

from flask import Flask, jsonify, request, send_file, send_from_directory, abort

from comparador import comparar

BASE = Path(__file__).resolve().parent
# Audios cargados y proyecto: junto al modelo, fuera de la carpeta de la app
# (la app instalada no debe escribir dentro de sí misma).
DATOS = DATOS_APP / "proyecto"
AUDIOS = DATOS / "audios"
PROYECTO = DATOS / "proyecto.json"
AUDIOS.mkdir(parents=True, exist_ok=True)

PUERTO_PREFERIDO = 8765
EXTENSIONES = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".aiff", ".aif", ".mp4", ".webm", ".opus"}

# Siempre se usa el modelo de máxima precisión
MODELOS = {"large-v3": "Máxima precisión"}
MODELO_DEFECTO = "large-v3"
# Solo para pruebas automáticas: permite usar un modelo más pequeño
if os.environ.get("PROBADOR_MODELO"):
    MODELO_DEFECTO = os.environ["PROBADOR_MODELO"]
    MODELOS = {MODELO_DEFECTO: "Prueba"}

app = Flask(__name__, static_folder=str(BASE / "static"))
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# ---------------------------------------------------------------- Whisper
_modelos = {}
_modelo_lock = threading.Lock()


def revisar_motor():
    """Comprueba que el motor de voz se puede cargar (en Windows puede faltar Visual C++)."""
    try:
        import ctranslate2  # noqa: F401
        import faster_whisper  # noqa: F401
        return None
    except Exception as e:
        traceback.print_exc()
        if os.name == "nt":
            return ("Falta un componente de Microsoft (Visual C++). Cierra la app y vuelve a abrir "
                    "Iniciar.bat para instalarlo, o descárgalo de https://aka.ms/vs/17/release/vc_redist.x64.exe")
        return f"No se pudo cargar el motor de voz: {e}"


ERROR_MOTOR = revisar_motor()
if ERROR_MOTOR:
    print("\n>> " + ERROR_MOTOR + "\n", flush=True)

TAMANO_MB = {"small": 484, "medium": 1530, "large-v3-turbo": 1620, "large-v3": 3090}
descargas = {}  # nombre -> {estado, bytes, total, error, ultimo_cambio}
_descarga_lock = threading.Lock()


def ruta_local(nombre):
    """Ruta del modelo si ya está completo en la Mac; si no, None."""
    try:
        from faster_whisper.utils import download_model
        return download_model(nombre, local_files_only=True)
    except Exception:
        return None


def modelo_descargado(nombre):
    return ruta_local(nombre) is not None


def _carpeta_modelo(nombre):
    from faster_whisper.utils import _MODELS
    from huggingface_hub import constants
    return Path(constants.HF_HUB_CACHE) / ("models--" + _MODELS[nombre].replace("/", "--"))


def _tamano(carpeta):
    total = 0
    try:
        for raiz, _, archivos in os.walk(carpeta):
            for a in archivos:
                p = os.path.join(raiz, a)
                if not os.path.islink(p):
                    try:
                        total += os.path.getsize(p)
                    except OSError:
                        pass
    except Exception:
        pass
    return total


def _descargar(nombre):
    d = descargas[nombre]
    carpeta = _carpeta_modelo(nombre)
    terminado = threading.Event()

    def medir():
        previo = -1
        while not terminado.is_set():
            b = _tamano(carpeta)
            if b != previo:
                d["bytes"], d["ultimo_cambio"], previo = b, time.time(), b
            terminado.wait(1)

    threading.Thread(target=medir, daemon=True).start()
    print(f"\n>> Descargando el modelo de voz '{nombre}' (~{TAMANO_MB.get(nombre, 500)} MB). Solo pasa la primera vez…", flush=True)
    intentos = 0
    while True:
        try:
            from faster_whisper.utils import download_model
            download_model(nombre)
            d["estado"] = "listo"
            print(f">> Modelo '{nombre}' descargado.", flush=True)
            break
        except Exception as e:
            intentos += 1
            if intentos >= 3:
                d["estado"] = "error"
                d["error"] = str(e)
                print(f">> No se pudo descargar el modelo: {e}", flush=True)
                break
            print(f">> La descarga se interrumpió ({e}). Reintentando…", flush=True)
            time.sleep(3)
    terminado.set()


def iniciar_descarga(nombre):
    """Empieza a descargar el modelo en segundo plano (si hace falta). No bloquea."""
    if ERROR_MOTOR:
        return {"estado": "error", "bytes": 0, "total": 0, "error": ERROR_MOTOR, "ultimo_cambio": time.time()}
    with _descarga_lock:
        d = descargas.get(nombre)
        if d and d["estado"] in ("descargando", "listo"):
            return d
        if modelo_descargado(nombre):
            descargas[nombre] = {"estado": "listo", "bytes": 0, "total": 0, "error": None, "ultimo_cambio": time.time()}
            return descargas[nombre]
        descargas[nombre] = {
            "estado": "descargando", "bytes": 0, "total": TAMANO_MB.get(nombre, 500) * 1024 * 1024,
            "error": None, "ultimo_cambio": time.time(),
        }
        threading.Thread(target=_descargar, args=(nombre,), daemon=True).start()
        return descargas[nombre]


def texto_descarga(d):
    mb = d["bytes"] / 1048576
    total = d["total"] / 1048576
    pct = min(99, int(100 * mb / total)) if total else 0
    txt = f"Descargando el modelo de voz (solo la primera vez): {mb:,.0f} MB de ~{total:,.0f} MB ({pct}%)"
    if time.time() - d["ultimo_cambio"] > 60:
        txt += ". La descarga parece detenida: revisa tu conexión a internet."
    return txt


def estado_modelo(nombre):
    if ERROR_MOTOR:
        return {"estado": "error", "texto": ERROR_MOTOR}
    d = descargas.get(nombre)
    if d and d["estado"] == "descargando":
        return {"estado": "descargando", "texto": texto_descarga(d)}
    if d and d["estado"] == "error":
        return {"estado": "error", "texto": "No se pudo descargar el modelo de voz. Revisa tu conexión a internet y vuelve a intentarlo."}
    if (d and d["estado"] == "listo") or modelo_descargado(nombre):
        return {"estado": "listo", "texto": ""}
    return {"estado": "falta", "texto": f"La primera verificación descargará este modelo (~{TAMANO_MB.get(nombre, 500):,} MB). Solo pasa una vez."}


def obtener_modelo(nombre, avisar):
    if ERROR_MOTOR:
        raise RuntimeError(ERROR_MOTOR)
    with _modelo_lock:
        if nombre in _modelos:
            return _modelos[nombre]
        # 1) Asegurar que el modelo está descargado, mostrando el avance
        d = iniciar_descarga(nombre)
        while d["estado"] == "descargando":
            avisar(texto_descarga(d))
            time.sleep(1)
        if d["estado"] == "error":
            descargas.pop(nombre, None)  # permitir reintentar en la siguiente verificación
            raise RuntimeError(
                "no se pudo descargar el modelo de voz. Revisa tu conexión a internet "
                "(la descarga solo se necesita la primera vez) y vuelve a verificar."
            )
        # 2) Cargarlo en memoria
        avisar("Cargando el modelo de voz (unos segundos)…")
        from faster_whisper import WhisperModel
        _modelos.clear()  # liberar otros modelos para no llenar la memoria
        ruta = ruta_local(nombre) or nombre
        m = WhisperModel(ruta, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
        _modelos[nombre] = m
        print(f">> Modelo '{nombre}' listo.", flush=True)
        return m


def decodificar(ruta, frecuencia=16000):
    """Lee cualquier audio (mp3, wav, m4a…) y lo convierte a mono 16 kHz para Whisper.
    Se hace aquí (y no dentro de faster-whisper) para funcionar con cualquier versión de PyAV."""
    import av
    import numpy as np
    partes = []
    with av.open(str(ruta), mode="r") as contenedor:
        flujo = next(s for s in contenedor.streams if s.type == "audio")
        remuestreo = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=frecuencia)

        def guardar(frames):
            if frames is None:
                return
            if not isinstance(frames, list):
                frames = [frames]
            for fr in frames:
                partes.append(fr.to_ndarray().reshape(-1))

        for paquete in contenedor.demux(flujo):
            try:
                for frame in paquete.decode():
                    guardar(remuestreo.resample(frame))
            except av.error.InvalidDataError:
                continue  # un fragmento dañado no debe detener todo el audio
        guardar(remuestreo.resample(None))  # vaciar lo pendiente
    if not partes:
        raise RuntimeError("el archivo no tiene audio o está dañado")
    return np.concatenate(partes).astype(np.float32) / 32768.0


def transcribir(ruta, idioma, nombre_modelo, avisar):
    modelo = obtener_modelo(nombre_modelo, avisar)
    avisar("Escuchando el audio…")
    audio = decodificar(ruta)
    segmentos, info = modelo.transcribe(
        audio,
        language=None if idioma == "auto" else idioma,
        word_timestamps=True,
        beam_size=5,
        vad_filter=False,               # no recortar nada: queremos oír todo
        condition_on_previous_text=False,  # evita repeticiones inventadas
        # Importante: NO se le da el guion como pista, para que no "adivine"
        # lo que debería decir y oculte errores reales.
    )
    palabras = []
    for s in segmentos:
        for w in (s.words or []):
            palabras.append({"word": w.word, "start": w.start, "end": w.end})
        if info.duration:
            avisar(f"Escuchando el audio… {min(99, int(100 * s.end / info.duration))}%")
    return palabras, info


# ---------------------------------------------------------------- Cola de trabajos
trabajos = {}
cola = queue.Queue()


def trabajador():
    while True:
        tid = cola.get()
        t = trabajos.get(tid)
        if not t:
            continue
        t["estado"] = "procesando"

        def avisar(msg, t=t):
            t["mensaje"] = msg

        try:
            inicio = time.time()
            palabras, info = transcribir(t["ruta"], t["idioma"], t["modelo"], avisar)
            idioma_cmp = info.language if t["idioma"] == "auto" else t["idioma"]
            r = comparar(t["texto"], palabras, idioma_cmp)
            r["duracion_audio"] = round(info.duration or 0, 1)
            r["idioma_detectado"] = info.language
            r["segundos_proceso"] = round(time.time() - inicio, 1)
            r["modelo"] = t["modelo"]
            t["resultado"] = r
            t["estado"] = "listo"
            t["mensaje"] = ""
        except Exception as e:
            traceback.print_exc()
            t["estado"] = "error"
            texto = str(e)
            if os.name == "nt" and "dll" in texto.lower():
                texto = ("falta un componente de Microsoft (Visual C++). Cierra la app y vuelve a abrir "
                         "Iniciar.bat para instalarlo, o descárgalo de https://aka.ms/vs/17/release/vc_redist.x64.exe")
            t["mensaje"] = f"No se pudo procesar: {texto}"
        finally:
            cola.task_done()


threading.Thread(target=trabajador, daemon=True).start()


# ---------------------------------------------------------------- Rutas
@app.get("/")
def inicio():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/ping")
def ping():
    return jsonify(ok=True, app="probador-audios")


@app.get("/api/config")
def config():
    return jsonify(
        modelos=[{"id": k, "nombre": v} for k, v in MODELOS.items()],
        modelo_defecto=MODELO_DEFECTO,
    )


@app.get("/api/modelo/<nombre>")
def api_estado_modelo(nombre):
    if nombre not in MODELOS:
        abort(404)
    return jsonify(estado_modelo(nombre))


@app.post("/api/descargar/<nombre>")
def api_descargar(nombre):
    if nombre not in MODELOS:
        abort(404)
    iniciar_descarga(nombre)
    return jsonify(estado_modelo(nombre))


@app.post("/api/subir")
def subir():
    archivos = request.files.getlist("archivo")
    salida = []
    for f in archivos:
        ext = Path(f.filename or "").suffix.lower()
        if ext not in EXTENSIONES:
            salida.append({"nombre": f.filename, "error": "Formato no soportado"})
            continue
        aid = uuid.uuid4().hex[:12]
        f.save(AUDIOS / f"{aid}{ext}")
        salida.append({"id": f"{aid}{ext}", "nombre": f.filename})
    return jsonify(archivos=salida)


@app.get("/api/audio/<aid>")
def audio(aid):
    ruta = AUDIOS / Path(aid).name
    if not ruta.exists():
        abort(404)
    return send_file(ruta, conditional=True)


@app.post("/api/verificar")
def verificar():
    d = request.get_json(force=True)
    ruta = AUDIOS / Path(d.get("audio", "")).name
    if not ruta.exists():
        return jsonify(error="El audio ya no existe; vuelve a cargarlo."), 400
    texto = (d.get("texto") or "").strip()
    if not texto:
        return jsonify(error="Falta el texto original."), 400
    modelo = d.get("modelo") if d.get("modelo") in MODELOS else MODELO_DEFECTO
    tid = uuid.uuid4().hex
    trabajos[tid] = {
        "estado": "en_cola", "mensaje": "En espera…", "ruta": ruta, "texto": texto,
        "idioma": d.get("idioma") or "es", "modelo": modelo, "resultado": None,
    }
    cola.put(tid)
    return jsonify(trabajo=tid)


@app.get("/api/trabajo/<tid>")
def trabajo(tid):
    t = trabajos.get(tid)
    if not t:
        return jsonify(estado="perdido", mensaje="El trabajo se perdió (¿reiniciaste la app?). Vuelve a verificar.")
    return jsonify(estado=t["estado"], mensaje=t["mensaje"], resultado=t["resultado"])


@app.get("/api/proyecto")
def leer_proyecto():
    if PROYECTO.exists():
        try:
            return jsonify(json.loads(PROYECTO.read_text("utf-8")))
        except Exception:
            pass
    return jsonify({})


@app.post("/api/proyecto")
def guardar_proyecto():
    d = request.get_json(force=True)
    tmp = PROYECTO.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), "utf-8")
    tmp.replace(PROYECTO)
    return jsonify(ok=True)


@app.post("/api/nuevo")
def nuevo_proyecto():
    d = request.get_json(silent=True) or {}
    conservar = set(d.get("conservar") or [])
    for f in AUDIOS.iterdir():
        if f.name not in conservar:
            try:
                f.unlink()
            except Exception:
                pass
    return jsonify(ok=True)


# ---------------------------------------------------------------- Arranque
def puerto_libre(p):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", p)) != 0


def ya_abierta(p):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{p}/api/ping", timeout=1) as r:
            return b"probador-audios" in r.read()
    except Exception:
        return False


def main():
    if os.environ.get("PROBADOR_SIN_NAVEGADOR") == "1":
        sys.argv.append("--sin-navegador")
    puerto = PUERTO_PREFERIDO
    if not puerto_libre(puerto):
        if ya_abierta(puerto):
            print("La app ya estaba abierta. Abriendo el navegador…")
            print(f"PROBADOR_URL=http://127.0.0.1:{puerto}", flush=True)
            if "--sin-navegador" not in sys.argv:
                webbrowser.open(f"http://127.0.0.1:{puerto}")
            return
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            puerto = s.getsockname()[1]

    # Empezar a descargar el modelo de voz desde ya (si falta), para no esperar después
    modelo_inicial = MODELO_DEFECTO
    try:
        guardado = json.loads(PROYECTO.read_text("utf-8")).get("modelo")
        if guardado in MODELOS:
            modelo_inicial = guardado
    except Exception:
        pass
    iniciar_descarga(modelo_inicial)

    url = f"http://127.0.0.1:{puerto}"
    print("\n" + "=" * 60)
    print("  PROBADOR DE AUDIOS está funcionando")
    print(f"  Abre en tu navegador: {url}")
    print("  Para cerrarlo: cierra esta ventana (o presiona Ctrl+C).")
    print(f"  Modelo de voz guardado en: {CARPETA_MODELOS}")
    print("=" * 60 + "\n", flush=True)
    print(f"PROBADOR_URL={url}", flush=True)  # lo lee la app de Mac para abrir el navegador
    if os.environ.get("PROBADOR_VIGILAR_STDIN") == "1":
        # Cuando la app de Mac se cierra, su tubería se cierra y este servidor termina.
        def vigilar():
            try:
                while sys.stdin.read(1024):
                    pass
            except Exception:
                pass
            os._exit(0)
        threading.Thread(target=vigilar, daemon=True).start()
    if "--sin-navegador" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    import flask.cli
    flask.cli.show_server_banner = lambda *a, **k: None
    app.run(host="127.0.0.1", port=puerto, threaded=True, debug=False)


if __name__ == "__main__":
    main()
