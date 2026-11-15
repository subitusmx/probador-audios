"""
Comparador de texto vs. transcripción.

Recibe el texto original (guion) y las palabras que Whisper escuchó en el audio
(con sus tiempos) y devuelve, palabra por palabra, qué coincide, qué falta,
qué cambió y qué se agregó, junto con un porcentaje de concordancia.
"""
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher

try:
    from num2words import num2words
except Exception:  # si no está instalada, simplemente no convertimos números
    num2words = None

IDIOMAS_NUM2WORDS = {"es": "es", "en": "en", "pt": "pt", "fr": "fr", "it": "it", "de": "de"}

SIMBOLOS = {
    "es": {"%": " por ciento ", "&": " y ", "+": " mas "},
    "en": {"%": " percent ", "&": " and ", "+": " plus "},
    "pt": {"%": " por cento ", "&": " e ", "+": " mais "},
    "fr": {"%": " pour cent ", "&": " et ", "+": " plus "},
}

_RE_MILES = re.compile(r"\d{1,3}(?:[.,]\d{3})+(?![.,]?\d)")
_RE_DECIMAL = re.compile(r"(\d+)[.,](\d+)")
_RE_NUM = re.compile(r"\d+")


def _sin_acentos(texto):
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def _numero_a_palabras(n, idioma):
    if num2words is None:
        return n
    try:
        return " " + num2words(int(n), lang=IDIOMAS_NUM2WORDS.get(idioma, "es")) + " "
    except Exception:
        return n


def normalizar_palabra(palabra, idioma="es"):
    """Convierte una palabra (o pieza de texto) a tokens comparables:
    minúsculas, sin acentos ni puntuación, números escritos con letra."""
    t = palabra.lower()
    for simbolo, reemplazo in SIMBOLOS.get(idioma, SIMBOLOS["es"]).items():
        t = t.replace(simbolo, reemplazo)
    # 1.000.000 / 1,000 -> 1000000
    t = _RE_MILES.sub(lambda m: re.sub(r"[.,]", "", m.group(0)), t)
    # 3,5 -> 3 coma 5
    coma = {"es": " coma ", "en": " point ", "pt": " virgula ", "fr": " virgule "}.get(idioma, " coma ")
    t = _RE_DECIMAL.sub(lambda m: m.group(1) + coma + m.group(2), t)
    t = _RE_NUM.sub(lambda m: _numero_a_palabras(m.group(0), idioma), t)
    t = _sin_acentos(t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    tokens = t.split()
    if idioma == "es":
        # Los números cambian de género según el sustantivo ("mil quinientas unidades");
        # tratamos ambas formas como equivalentes.
        tokens = [_GENERO_ES.get(x, re.sub(r"ientas$", "ientos", x)) for x in tokens]
    return tokens


_GENERO_ES = {"una": "un", "uno": "un", "veintiuna": "veintiun", "veintiuno": "veintiun"}


def fonetico(t, idioma="es"):
    """Aproximación de cómo suena una palabra, para detectar homófonos."""
    if idioma == "es":
        t = t.replace("ch", "#")
        t = t.replace("h", "")
        t = re.sub(r"g([ei])", r"j\1", t)
        t = re.sub(r"gu([ei])", r"g\1", t)
        t = re.sub(r"qu([ei])", r"k\1", t)
        t = re.sub(r"c([ei])", r"s\1", t)
        t = t.replace("c", "k").replace("q", "k").replace("z", "s")
        t = t.replace("v", "b").replace("w", "b").replace("ll", "y")
        t = re.sub(r"y$", "i", t)
        t = t.replace("x", "ks")
        t = re.sub(r"(.)\1+", r"\1", t)  # letras dobles
        return t
    if idioma == "pt":
        return re.sub(r"(.)\1+", r"\1", t.replace("h", "").replace("z", "s").replace("ç", "s"))
    # Otros idiomas: solo colapsar letras dobles
    return re.sub(r"(.)\1+", r"\1", t)


def preparar_referencia(texto, idioma="es"):
    """Divide el guion en palabras visibles y tokens normalizados."""
    palabras = texto.split()
    tokens, token_palabra = [], []
    for i, p in enumerate(palabras):
        for tok in normalizar_palabra(p, idioma):
            tokens.append(tok)
            token_palabra.append(i)
    return palabras, tokens, token_palabra


def preparar_hipotesis(palabras_whisper, idioma="es"):
    """palabras_whisper: lista de dicts {word, start, end}."""
    palabras, tiempos, tokens, token_palabra = [], [], [], []
    for p in palabras_whisper:
        texto = p["word"].strip()
        if not texto:
            continue
        idx = len(palabras)
        palabras.append(texto)
        tiempos.append(float(p.get("start") or 0.0))
        for tok in normalizar_palabra(texto, idioma):
            tokens.append(tok)
            token_palabra.append(idx)
    return palabras, tiempos, tokens, token_palabra


GRAVEDAD = {"ok": 0, "similar": 1, "cambiada": 2, "omitida": 2}


def comparar(texto, palabras_whisper, idioma="es"):
    ref_palabras, ref_tok, ref_tok_pal = preparar_referencia(texto, idioma)
    hyp_palabras, hyp_tiempos, hyp_tok, hyp_tok_pal = preparar_hipotesis(palabras_whisper, idioma)

    n = len(ref_palabras)
    estado = ["ok"] * n
    escuchado = [[] for _ in range(n)]
    tiempo = [None] * n
    agregadas_despues = defaultdict(list)  # índice de palabra del guion (-1 = al inicio) -> índices hyp
    hyp_usadas = set()

    def tiempo_hyp_tok(j):
        return hyp_tiempos[hyp_tok_pal[j]] if 0 <= j < len(hyp_tok) else None

    def marcar(w, nuevo):
        if GRAVEDAD[nuevo] > GRAVEDAD[estado[w]] or (estado[w] == "omitida" and nuevo == "cambiada"):
            estado[w] = nuevo

    sm = SequenceMatcher(None, ref_tok, hyp_tok, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                w = ref_tok_pal[i1 + k]
                if tiempo[w] is None:
                    tiempo[w] = tiempo_hyp_tok(j1 + k)
            continue

        if op == "delete":
            for i in range(i1, i2):
                marcar(ref_tok_pal[i], "omitida")
            continue

        if op == "insert":
            ancla = ref_tok_pal[i1 - 1] if i1 > 0 else -1
            for j in range(j1, j2):
                hw = hyp_tok_pal[j]
                if hw not in agregadas_despues[ancla]:
                    agregadas_despues[ancla].append(hw)
            continue

        # replace
        a, b = ref_tok[i1:i2], hyp_tok[j1:j2]
        if "".join(a) == "".join(b):  # p.ej. "e-mail" vs "email", "sin embargo" vs "sinembargo"
            for i in range(i1, i2):
                w = ref_tok_pal[i]
                if tiempo[w] is None:
                    tiempo[w] = tiempo_hyp_tok(j1)
            continue
        # "similar" = suenan igual (homófonos: casa/caza, vaca/baca, hola/ola);
        # el audio no permite distinguirlas, así que no se cuentan como error real.
        mismo_sonido = fonetico("".join(a), idioma) == fonetico("".join(b), idioma)
        tipo = "similar" if mismo_sonido else "cambiada"
        primera = ref_tok_pal[i1]
        for i in range(i1, i2):
            w = ref_tok_pal[i]
            marcar(w, tipo)
            if tiempo[w] is None:
                tiempo[w] = tiempo_hyp_tok(j1)
        for j in range(j1, j2):
            hw = hyp_tok_pal[j]
            if hw not in escuchado[primera]:
                escuchado[primera].append(hw)

    # Rellenar tiempos faltantes con el último conocido (para poder reproducir cerca)
    ultimo = 0.0
    for w in range(n):
        if tiempo[w] is None:
            tiempo[w] = ultimo
        else:
            ultimo = tiempo[w]

    def texto_hyp(indices):
        libres = [h for h in indices if h not in hyp_usadas]
        hyp_usadas.update(libres)
        return " ".join(hyp_palabras[h] for h in libres)

    segmentos = []

    def agregar_insertadas(ancla):
        if agregadas_despues.get(ancla):
            idx = agregadas_despues[ancla]
            txt = texto_hyp(idx)
            if txt:
                segmentos.append({"tipo": "agregada", "texto": txt, "t": hyp_tiempos[idx[0]]})

    agregar_insertadas(-1)
    for w in range(n):
        seg = {"tipo": estado[w], "texto": ref_palabras[w], "t": round(tiempo[w], 2)}
        if estado[w] in ("cambiada", "similar") and escuchado[w]:
            seg["escuchado"] = texto_hyp(escuchado[w])
        segmentos.append(seg)
        agregar_insertadas(w)

    omitidas = sum(1 for e in estado if e == "omitida")
    cambiadas = sum(1 for e in estado if e == "cambiada")
    similares = sum(1 for e in estado if e == "similar")
    agregadas = sum(len(v) for v in agregadas_despues.values())

    if n == 0:
        porcentaje = 0.0
    else:
        errores = omitidas + cambiadas + agregadas + 0.3 * similares
        porcentaje = max(0.0, 100.0 * (1 - errores / n))

    if n == 0:
        veredicto = "error"
    elif len(hyp_palabras) == 0:
        veredicto = "error"
    elif omitidas == 0 and cambiadas == 0 and agregadas == 0 and similares == 0:
        veredicto = "correcto"
    elif omitidas == 0 and cambiadas == 0 and agregadas == 0:
        veredicto = "correcto_menor"  # solo diferencias de escritura muy parecidas
    elif porcentaje >= 90:
        veredicto = "revisar"
    else:
        veredicto = "error"

    return {
        "porcentaje": round(porcentaje, 1),
        "veredicto": veredicto,
        "total_palabras": n,
        "omitidas": omitidas,
        "cambiadas": cambiadas,
        "similares": similares,
        "agregadas": agregadas,
        "segmentos": segmentos,
        "transcripcion": " ".join(hyp_palabras),
    }
