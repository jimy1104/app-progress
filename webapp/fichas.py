# -*- coding: utf-8 -*-
"""FICHA de cada documento del expediente: qué es, sin tener que abrirlo.

Para cada documento que identificó el segmentador se arma:

  titulo      el nombre completo y limpio: «INFORME N° 132-2026-MPC/GPS/SGPVL»,
              «FACTURA ELECTRÓNICA E001-18», «TÉRMINOS DE REFERENCIA: SERVICIO DE …»
  numero      el código del documento, reparado con las siglas que se repiten en
              el expediente (el OCR lee «MPCIGPS» donde dice «MPC/GPS»)
  fecha, asunto, referencia, de, para (con nombre y cargo)
  firmantes   quién firma, con su cargo. Los nombres se reconocen contra el REGISTRO
              DE PERSONAS del expediente (armado con lo que se lee limpio: los campos
              A/DE/PARA, el proveedor, «Elaborado por»), así un sello de post-firma
              mal leído («T RRES VILCA») igual se identifica.
  sellos      folio, recepción (fecha y hora), proveído, visto bueno, post-firma,
              institucional; y las firmas manuscritas (trazos de tinta de color).
  resumen     una línea para mostrar al pasar el mouse.

Todo sale de la lectura (OCRDocument) y, si hay PDF, de la tinta de color de la hoja.
Nada se inventa: lo que no se pudo leer queda vacío.
"""
from __future__ import annotations
import re, unicodedata
from difflib import SequenceMatcher
from collections import Counter

MESES = {"ENE": 1, "ENERO": 1, "FEB": 2, "FEBRERO": 2, "MAR": 3, "MARZO": 3, "ABR": 4, "ABRIL": 4,
         "MAY": 5, "MAYO": 5, "JUN": 6, "JUNIO": 6, "JUL": 7, "JULIO": 7, "AGO": 8, "AGOSTO": 8,
         "SET": 9, "SEP": 9, "SETIEMBRE": 9, "SEPTIEMBRE": 9, "OCT": 10, "OCTUBRE": 10,
         "NOV": 11, "NOVIEMBRE": 11, "DIC": 12, "DICIEMBRE": 12}

TRATAMIENTOS = r"(?:ABOG|ABG|SR|SRA|SRTA|SRES|LIC|ING|CPC|C\s?P\s?C|DR|DRA|MG|MGTR|ECON|ARQ|PROF|TEC|BACH|CP)"
CARGOS = re.compile(r"\b(SUB\s?GERENTE|GERENTE|JEFE|JEFA|DIRECTOR|DIRECTORA|ALCALDE|ALCALDESA|ASISTENTE|"
                    r"ESPECIALISTA|COORDINADOR|COORDINADORA|RESPONSABLE|ANALISTA|SECRETARI[OA]|COMPRADOR|"
                    r"ADMINISTRADOR|TESORER[OA]|CONTADOR|ASESOR|ASESORA|ENCARGAD[OA])\b")
INSTITUCION = {"MUNICIPALIDAD", "PROVINCIAL", "CALLAO", "GERENCIA", "SUBGERENCIA", "OFICINA", "PROGRAMA",
               "VASO", "LECHE", "LOGISTICA", "GENERAL", "ADMINISTRACION", "FINANZAS", "DEL", "DE", "LA",
               "SOCIALES", "PROGRAMAS", "PRESUPUESTO", "SERVICIO", "SERVICIOS", "ORDEN", "AREA", "USUARIA",
               "FIRMA", "SOLICITANTE", "AUTORIZADA", "VOBO", "PROVEIDO", "COMPROBANTE", "RESPONSABLE", "ADQUISICIONES", "ABASTECIMIENTO",
               "CONFORMIDAD", "FECHA", "HORA", "FOLIO", "RECEPCION", "DOCUMENTO", "CONTENIDO", "VISTO",
               "BUENO", "ENTREGABLE", "SEGUNDO", "PRIMER", "TERMINOS", "REFERENCIA", "JEFE", "GERENTE",
               "SUB", "SUBGERENTE", "ELABORADO", "POR", "PLANEAMIENTO", "INVERSIONES", "MODERNIZACION",
               "CONTABILIDAD", "TESORERIA", "UNIDAD", "LOCAL", "EMPADRONAMIENTO", "PERU", "REPUBLICA",
               "SENORES", "PRESENTE", "ATENTAMENTE", "ASUNTO", "PARA", "RESPONSABILIDAD", "PROVEEDOR",
               "CONTRATISTA", "ENTIDAD", "PENALIDADES", "OBLIGACIONES", "CONDICIONES", "REQUISITOS",
               "NORMAS", "REGLAMENTOS", "DIRECTIVAS", "DISPOSICIONES", "VIGENTES", "PLAZO", "OBJETO"}
ARTICULOS = {"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y", "EN", "A"}

ETIQUETAS_CAMPO = {"A": "para", "PARA": "para", "SENOR": "para", "SENORES": "para", "DE": "de",
                   "ASUNTO": "asunto", "REF": "referencia", "REFERENCIA": "referencia", "FECHA": "fecha"}
ORDEN_CAMPOS = ["para", "de", "asunto", "referencia", "fecha"]


# ------------------------------------------------------------ utilidades ----
def _n(t):
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).upper()
    t = re.sub(r"[–—_]", lambda m: "-" if m.group(0) != "_" else " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _tokens(t):
    return [x for x in re.split(r"[^A-Z0-9]+", _n(t)) if x]


def _yc(ln):
    return (ln.bbox[1] + ln.bbox[3]) / 2


def _parecidas(a, b, umbral=0.8):
    return a == b or (len(a) >= 3 and len(b) >= 3 and SequenceMatcher(None, a, b).ratio() >= umbral)


def filas(lineas, tol=0.55):
    """Agrupa renglones que están a la misma altura (Azure a veces separa la etiqueta
    «ASUNTO :» de su valor) y los ordena de izquierda a derecha."""
    out = []
    for ln in sorted(lineas, key=lambda l: (_yc(l), l.bbox[0])):
        alto = max(1e-4, ln.bbox[3] - ln.bbox[1])
        if out and abs(_yc(ln) - _yc(out[-1][-1])) <= tol * alto:
            out[-1].append(ln)
        else:
            out.append([ln])
    return [sorted(f, key=lambda l: l.bbox[0]) for f in out]


def _texto_fila(f):
    return " ".join(l.text.strip() for l in f if l.text.strip())


def fecha_de(texto):
    """dd/mm/aaaa desde «23 de abril del 2026», «23 ABR 2026», «02 rie setiembre del 2026»
    (el «de» mal leído), «02/09/2026», «23.04.26»."""
    from difflib import get_close_matches
    t = _n(texto)
    m = re.search(r"\b(\d{1,2})\s*(?:[A-Z]{1,3}\s+)?([A-Z]{3,10})\.?,?\s*(?:[A-Z]{1,3}\s+)?((?:19|20)\d\d)\b", t)
    if m:
        mes = MESES.get(m.group(2))
        if mes is None:
            c = get_close_matches(m.group(2), list(MESES), n=1, cutoff=0.8)
            mes = MESES[c[0]] if c else None
        if mes and 1 <= int(m.group(1)) <= 31:
            return f"{int(m.group(1)):02d}/{mes:02d}/{m.group(3)}"
    m = re.search(r"\b(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{2,4})\b", t)
    if m and 1 <= int(m.group(1)) <= 31 and 1 <= int(m.group(2)) <= 12:
        a = int(m.group(3))
        a = a + 2000 if a < 100 else a
        if 2000 <= a <= 2040:
            return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{a}"
    return ""


def hora_de(texto):
    t = _n(texto)
    m = re.search(r"HORA\W{0,4}([01]?\d|2[0-3])\s*[:.]?\s*([0-5]\d)\s*(A\.?\s?M|P\.?\s?M|HRS?|H)?\b", t) or \
        re.search(r"\b([01]?\d|2[0-3])\s*[:.]\s*([0-5]\d)\s*(A\.?\s?M|P\.?\s?M|HRS?|H)?\b", t)
    return f"{int(m.group(1)):02d}:{m.group(2)}" + (" " + m.group(3).replace(" ", "").replace(".", "").lower()
                                                    if m and m.group(3) and m.group(3)[0] in "AP" else "") if m else ""


# ------------------------------------------------------- siglas y números ----
_CODIGO = re.compile(r"[0-9A-Z][0-9A-Z/\-\.]*")


# Siglas de dependencias de la Municipalidad Provincial del Callao que aparecen en
# los códigos de los documentos. Se suman (con peso 2) a las que se repiten en el
# expediente para reparar una sigla que el OCR leyó mal y que sale una sola vez.
SIGLAS_CONOCIDAS = ("MPC", "GM", "GPS", "SGPVL", "OGAF", "OLG", "OGPMPI", "OPR", "OC", "OT", "OGAJ", "OCI",
                    "SG", "GA", "OGA", "OGTI", "OGRH")


def siglas_del_expediente(doc):
    """Siglas que se repiten en los códigos del expediente (MPC, GPS, SGPVL, OGAF…).
    Sirven para reparar lo que el OCR pega o confunde."""
    c = Counter({s: 2 for s in SIGLAS_CONOCIDAS})
    for pg in doc.pages:
        for m in re.finditer(r"\d{2,4}\s*[-/]\s*((?:[A-Z]{2,8}\s*[-/]\s*){0,5}[A-Z]{2,8})", _n(pg.text)):
            for s in re.split(r"[-/\s]+", m.group(1)):
                if 2 <= len(s) <= 8 and s.isalpha():
                    c[s] += 1
    return c


def _edicion(a, b):
    """Distancia de edición (Levenshtein), corta."""
    if abs(len(a) - len(b)) > 1:
        return 9
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _sigla_conocida(parte, siglas):
    """La sigla del expediente que corresponde a lo leído: la misma, o la vecina (una
    letra de diferencia) que más se repite. Una sigla vista una sola vez solo se acepta
    tal cual si no tiene una vecina más frecuente."""
    p = parte.replace("0", "O").replace("1", "I") if sum(c.isalpha() for c in parte) >= 3 else parte
    vecinas = [(k, s) for s, k in siglas.items() if len(s) >= 3 and _edicion(s, p) <= 1]
    if not vecinas and len(p) >= 6:
        # sigla larga con dos errores («C0GPAPI» -> OGPMPI): solo si hay UNA candidata
        lejanas = [(k, s) for s, k in siglas.items() if len(s) >= 5 and k >= 2 and _edicion(s, p) <= 2]
        if len(lejanas) == 1:
            return lejanas[0][1]
    if not vecinas:
        return None
    k, mejor = max(vecinas)
    if mejor == p or k >= 2:
        return mejor
    return None


def _reparar_siglas(parte, siglas):
    if not siglas or not parte or parte.isdigit():
        return parte
    k = _sigla_conocida(parte, siglas)
    if k:
        return k
    # «MPCIGPS» = «MPC» + «I» (la barra leída como I) + «GPS»; «MPCISGPYL» = MPC / SGPVL
    for i in range(2, len(parte) - 2):
        if parte[i] in "I1L|":
            a, b = _sigla_conocida(parte[:i], siglas), _sigla_conocida(parte[i + 1:], siglas)
            if a and b:
                return a + "/" + b
    return parte


def numero_de(texto, siglas=None, solo_digitos=False):
    """El código que sigue a «N°» en un título. «N' 132-2026-MPCIGPS/SGPVL ocacion |» ->
    «132-2026-MPC/GPS/SGPVL»."""
    t = _n(texto)
    t = re.sub(r"\s*([-/])\s*", r"\1", t)                 # «01493- 2025 - MPC» -> «01493-2025-MPC»
    m = re.search(r"\bN\s?(?:RO|O|UM|UMERO)?[^\w\-]{0,4}\s*(?:\([A-Z]\)\s*|[A-Z]\s+)?(?=[\d\-])", t)
    if not m:
        return ""
    resto = t[m.end():]
    cod = _CODIGO.match(resto) or re.match(r"-[0-9A-Z/\-\.]+", resto)
    if not cod:
        return ""
    s = cod.group(0).strip("./")
    siguiente = resto[cod.end():cod.end() + 1]
    if siguiente and siguiente in "%?¿&#@$" or re.match(r"^-?\d$", s.split("-")[0] if not s.startswith("-") else s[1:].split("-")[0]):
        return "ILEGIBLE" + ("-" + "-".join(p for p in re.split(r"-", resto[cod.end():]) if re.fullmatch(r"[A-Z]{2,8}", p)) if True else "")
    if s.startswith("-"):
        s = "S/N" + s.rstrip("-")               # número en blanco: «MEMORANDO N° -2026-MPC…»
    s = s.rstrip("-")
    if solo_digitos:
        d = re.match(r"\d+", s)
        return d.group(0) if d else ""
    partes = re.split(r"([-/])", s)
    partes = [_reparar_siglas(p, siglas) if p not in "-/" else p for p in partes]
    s = "".join(partes)
    return s if re.search(r"\d", s) and re.match(r"^(S/N|\d)", s) else ""


# ---------------------------------------------------------------- personas ----
def _limpiar_nombre(t):
    t = _n(t)
    t = re.sub(r"^\W*:?\s*", "", t)
    t = re.sub(r"^" + TRATAMIENTOS + r"\.?\s+", "", t)
    t = re.sub(r"[^A-Z\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def nombre_en(texto):
    """El primer tramo de 2+ palabras en MAYÚSCULAS (los nombres en cabeceras y sellos
    van así), sin tratamiento. «Sr. ROSA ELENA TORRES VILCA y NOS pe» ->
    «ROSA ELENA TORRES VILCA»."""
    toks = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ\.]+", texto or "")
    tramo = []
    for tk in toks:
        limpio = tk.strip(".")
        if re.fullmatch(TRATAMIENTOS, _n(limpio)) and not tramo:
            continue
        if len(limpio) >= 2 and limpio.isupper():
            tramo.append(limpio)
        elif tramo:
            if len(tramo) >= 2:
                break
            tramo = []
    return _limpiar_nombre(" ".join(tramo)) if len(tramo) >= 2 else ""


def es_nombre(t):
    """¿Parece nombre de persona? 2 a 6 palabras, sin cifras ni palabras institucionales."""
    ws = [w for w in _limpiar_nombre(t).split() if w not in ARTICULOS]
    if not (2 <= len(ws) <= 6) or re.search(r"[\d,;:]", t or ""):
        return False
    if sum(1 for w in ws if len(w) >= 3) < 2 or sum(len(w) for w in ws) < 8:
        return False
    return sum(1 for w in ws if w in INSTITUCION) == 0


class Registro:
    """Personas del expediente: nombre canónico -> {cargo, visto}."""

    def __init__(self):
        self.personas = {}

    def clave(self, nombre):
        return frozenset(w for w in _limpiar_nombre(nombre).split() if len(w) >= 3)

    def agregar(self, nombre, cargo="", fuente=""):
        limpio = _limpiar_nombre(nombre)
        if not es_nombre(limpio):
            return None
        k = self.clave(limpio)
        for kk, p in self.personas.items():
            if len(k & kk) >= min(3, len(k), len(kk)) or self._fuzzy(k, kk) >= 0.9:
                if cargo and not p["cargo"]:
                    p["cargo"] = cargo
                # se prefiere el orden «NOMBRES APELLIDOS» de los campos A/DE/PARA
                if fuente == "cabecera" and p["fuente"] != "cabecera":
                    p["nombre"], p["fuente"] = limpio, fuente
                p["visto"] += 1
                return p
        p = {"nombre": limpio, "cargo": cargo, "fuente": fuente, "visto": 1}
        self.personas[k] = p
        return p

    @staticmethod
    def _fuzzy(a, b):
        if not a or not b:
            return 0.0
        hits = sum(1 for x in a if any(_parecidas(x, y, 0.82) for y in b))
        return hits / max(len(a), len(b))

    def buscar_difuso(self, texto, umbral=0.82):
        """Para renglones destrozados por una firma encima («ROSA EL NA T RRES
        V LCA»): se comparan las LETRAS seguidas del renglón con las del nombre,
        en una ventana del largo del nombre."""
        letras = re.sub(r"[^A-Z]", "", _n(texto))
        out = []
        for p in self.personas.values():
            nom = re.sub(r"[^A-Z]", "", p["nombre"])
            if len(nom) < 12 or len(letras) < 0.6 * len(nom):
                continue
            mejor = 0.0
            paso = max(1, len(nom) // 8)
            for i in range(0, max(1, len(letras) - len(nom) + 1), paso):
                r = SequenceMatcher(None, nom, letras[i:i + len(nom) + 4], autojunk=False).ratio()
                mejor = max(mejor, r)
            if mejor >= umbral:
                out.append((mejor, p))
        out.sort(key=lambda t: -t[0])
        return [p for _, p in out]

    def buscar(self, texto, minimo=2):
        """Personas del registro cuyo nombre aparece (tolerando errores de OCR) en el texto."""
        toks = [w for w in _tokens(texto) if len(w) >= 3]
        out = []
        for k, p in self.personas.items():
            hits = sum(1 for x in k if any(_parecidas(x, y, 0.8) for y in toks))
            if hits >= min(minimo, len(k)) and hits >= 0.5 * len(k):
                out.append((hits / len(k), p))
        out.sort(key=lambda t: -t[0])
        return [p for _, p in out]


# ------------------------------------------------------------------ campos ----
def _etiqueta_fila(f):
    """(campo, valor) si la fila empieza con una etiqueta (A, PARA, DE, ASUNTO…).
    El «:» casi nunca se lee bien («DE !», «A E», «FECHA ,»): se reconoce la PALABRA de
    la etiqueta y la separación entre la columna de etiquetas y la de valores."""
    ws = sorted((w for l in f for w in (l.words or [])), key=lambda w: w.bbox[0])
    if not ws:
        return None
    if ws[0].bbox[0] > 0.4:              # etiquetas en la columna izquierda (no en sellos)
        return None
    primera = _n(ws[0].text).strip(".:;")
    campo = ETIQUETAS_CAMPO.get(primera)
    if not campo:
        m = re.match(r"^([A-Z]{1,10})[:;]", _n(ws[0].text))
        campo = ETIQUETAS_CAMPO.get(m.group(1)) if m else None
    if not campo:
        return None
    resto = ws[1:]
    separador = bool(re.search(r"[:;]", ws[0].text))
    if resto and len(resto[0].text.strip()) == 1 and not resto[0].text.strip().isalnum() or \
            (resto and resto[0].text.strip() in ("H", "E", "I", "l", "i", "!", "|", ",", "-", ";", ":")):
        separador, resto = True, resto[1:]
    if not resto:
        return None
    hueco = resto[0].bbox[0] - ws[0].bbox[2]
    # «A» y «DE» son palabras comunes: solo cuentan como etiqueta con separador o columna
    if campo in ("para", "de") and primera in ("A", "DE") and not (separador or hueco > 0.05):
        return None
    valor = " ".join(w.text for w in resto).strip(" :;")
    return campo, valor


_TEXTO_DE_SELLO = re.compile(r"RECEPCION DE ESTE|LA RECEPCION|NO SIGNIFICA|SIGNIFICA LA ACEPTACION|"
                             r"ACEPTACION DE SU|^\W*RECIBID[OA]\b|FOLIO\s*N|^\W*HORA\b|^\W*PROVEIDO")


def _x_valor(f):
    """Dónde empieza el VALOR en una fila «ETIQUETA : valor» (la columna de valores)."""
    ws = sorted((w for l in f for w in (l.words or [])), key=lambda w: w.bbox[0])
    for i, w in enumerate(ws):
        if ":" in w.text:
            if w.text.strip().endswith(":"):
                return ws[i + 1].bbox[0] if i + 1 < len(ws) else None
            return w.bbox[0]
    return ws[1].bbox[0] if len(ws) > 1 else None


def campos_cabecera(pg):
    """A/PARA, DE, ASUNTO, REFERENCIA, FECHA de un memorando, informe u oficio."""
    zona = [l for l in pg.lines if _yc(l) <= 0.62 and not l.manuscrita and not _TEXTO_DE_SELLO.search(_n(l.text))]
    out, actual, col = {}, None, None
    for f in filas(zona):
        txt = _texto_fila(f)
        t = _n(txt)
        et = _etiqueta_fila(f)
        if et and et[0] not in out:
            out[et[0]] = [et[1]]
            actual, col = et[0], _x_valor(f)
            continue
        if actual and col is not None and not re.match(r"^\W{0,2}[A-Z0-9]{0,3}(\s+[A-Z0-9]{1,2})?\s*:", t):
            # continuación: solo lo que está en la columna de valores (a la izquierda
            # suelen quedar sellos de recepción puestos sobre las etiquetas)
            f = [l for l in f if l.bbox[0] >= col - 0.06]
            if not f:
                continue
            txt = _texto_fila(f)
            t = _n(txt)
        if re.match(r"^\W{0,2}[A-Z0-9]{0,3}(\s+[A-Z0-9]{1,2})?\s*:", t) and actual is not None:
            # etiqueta tapada por un sello («id : Sr. CESAR…»): la que sigue en el orden habitual
            pend = [c for c in ORDEN_CAMPOS if c not in out and ORDEN_CAMPOS.index(c) > ORDEN_CAMPOS.index(actual)]
            valor = txt.split(":", 1)[1].strip(" :;")
            if "fecha" not in out and ("FECHA" in t or (fecha_de(valor) and len(valor) <= 45)):
                pend = ["fecha"]
            if pend:
                out[pend[0]] = [valor]
                actual, col = pend[0], _x_valor(f)
                continue
        if actual and len(out.get(actual, [])) < 3 and len(t) > 3:
            # continuación del valor (el cargo bajo el nombre, la 2ª línea del asunto)
            if actual in ("para", "de") and len(out[actual]) >= 2:
                actual = None
                continue
            out[actual].append(txt.strip())
        elif out and len(t) > 60:
            break                                         # empezó el cuerpo del documento
    res = {}
    for k in ("para", "de"):
        if k in out:
            vals = out[k]
            nombre = nombre_en(vals[0]) or (_limpiar_nombre(vals[0]) if es_nombre(vals[0]) else vals[0].strip())
            cargo = next((v for v in vals[1:] if not nombre_en(v)), "")
            res[k] = {"nombre": nombre, "texto": vals[0].strip(), "cargo": cargo.strip()}
    if "asunto" in out:
        res["asunto"] = " ".join(out["asunto"]).strip(" -")[:300]
    if "referencia" in out:
        res["referencia"] = " ".join(out["referencia"]).strip()[:300]
    if "fecha" in out:
        res["fecha"] = fecha_de(" ".join(out["fecha"])) or " ".join(out["fecha"]).strip()[:40]
    return res


# ------------------------------------------------------------------ títulos ---
PREFIJOS = {
    "orden_servicio": ("ORDEN DE SERVICIO", "ORDEN DE COMPRA"),
    "pedido_servicio": ("PEDIDO DE SERVICIO", "PEDIDO DE COMPRA"),
    "informe": ("INFORME",), "memorando": ("MEMORANDO", "OFICIO", "MEMORANDUM"),
    "conformidad": ("CONFORMIDAD DE SERVICIOS", "ACTA DE CONFORMIDAD"),
    "certificacion": ("CERTIFICACIÓN DE CRÉDITO PRESUPUESTARIO",),
    "carta": ("CARTA",), "contrato": ("CONTRATO",), "cotizacion": ("COTIZACIÓN",),
}


def _prefijo(tipo, texto):
    ops = PREFIJOS.get(tipo)
    if not ops:
        return ""
    t = _n(texto).replace(" ", "")
    for o in ops:
        if _n(o).replace(" ", "")[:10] in t:
            return o
    return ops[0]


def titulo_de(seg, doc, siglas):
    """Nombre completo y limpio del documento."""
    pg = doc.pages[seg.pagina_ini - 1]
    crudo = (seg.titulo or "").strip()
    # si las cifras del título se releyeron después de segmentar, vale el renglón actual
    forma = re.sub(r"\d", "9", crudo)
    crudo = next((l.text.strip() for l in pg.lines if l.text.strip() != crudo
                  and re.sub(r"\d", "9", l.text.strip()) == forma), crudo)
    tipo = seg.tipo
    lineas = sorted(pg.lines, key=lambda l: (_yc(l), l.bbox[0]))

    def siguiente(tras, n=2):
        idx = next((i for i, l in enumerate(lineas) if l.text.strip()[:120] == tras[:120]), None)
        return [l.text for l in lineas[idx + 1: idx + 1 + n]] if idx is not None else []

    if tipo in ("orden_servicio", "pedido_servicio"):
        num = numero_de(crudo, solo_digitos=True) or next(
            (re.sub(r"\D", "", s) for s in siguiente(crudo) if re.fullmatch(r"\W*\d{4,8}\W*", s.strip())), "")
        return f"{_prefijo(tipo, crudo)} N° {num}".strip() if num else _prefijo(tipo, crudo), num
    if tipo in PREFIJOS:
        num = numero_de(crudo, siglas)
        if not num:
            for s in siguiente(crudo, 1):
                num = numero_de("N " + s, siglas) if re.match(r"^\W*[\d-]", s) else ""
        if num:
            return f"{_prefijo(tipo, crudo)} N° {num}", num
        largo = re.sub(r"\s+", " ", crudo).strip(" |")
        if len(_n(largo).split()) > len(_prefijo(tipo, crudo).split()) + 1 and "N" not in _n(largo).split():
            # «INFORME DEL SERVICIO DE ALQUILER DE UNIDAD VEHICULAR»: el título leído, completo
            if re.search(r"\b(DE|DEL|Y|LA|EL)\s*$", _n(largo)):
                largo += " " + " ".join(siguiente(crudo, 1))
            return re.sub(r"\s+", " ", largo)[:140], ""
        return _prefijo(tipo, crudo), ""
    if tipo == "tdr":
        for i, l in enumerate(lineas):
            if "DENOMINACION" in _n(l.text) and i + 1 < len(lineas):
                den = " ".join(x.text.strip() for x in lineas[i + 1:i + 3]
                               if not re.match(r"^\W*\d+\W", x.text.strip()))
                return f"TÉRMINOS DE REFERENCIA: {den[:160]}", ""
        return "TÉRMINOS DE REFERENCIA", ""
    if tipo == "comprobante_pago":
        serie = _serie_cpe(" ".join(l.text for l in pg.lines))
        base = "RECIBO POR HONORARIOS" if "HONORARIOS" in _n(pg.text) else \
            "BOLETA DE VENTA ELECTRÓNICA" if "BOLETA" in _n(pg.text) else "FACTURA ELECTRÓNICA"
        return (f"{base} {serie}" if serie else base), serie
    if tipo == "validez_cpe":
        frase = next((l.text.strip() for l in lineas if "COMPROBANTE DE PAGO" in _n(l.text)
                      and ("VALIDO" in _n(l.text) or "ES UN" in _n(l.text))), "")
        serie = _serie_cpe(pg.text)
        return (f"CONSULTA DE VALIDEZ DEL COMPROBANTE {serie}".strip() + (" · válido" if "VALIDO" in _n(pg.text) else "")), serie
    if tipo == "correo":
        asunto = next((l.text.strip() for l in lineas
                       if 0.08 < _yc(l) < 0.3 and 4 <= len(l.text.strip()) <= 90 and "@" not in l.text
                       and not re.search(r"GMAIL|PARA:|MUNICIPALIDAD|FOLIO|GERENCIA", _n(l.text))), "")
        de = next((l.text.strip() for l in lineas if "@" in l.text and not _n(l.text).startswith("PARA")), "")
        de = re.sub(r"<.*", "", de).strip()
        return f"CORREO: {asunto}" + (f" (de {de})" if de else ""), ""
    if tipo == "informe" or crudo:
        if crudo and re.search(r"\b(DE|DEL|Y|LA)\s*$", _n(crudo)):
            crudo += " " + " ".join(siguiente(crudo, 1))
        return re.sub(r"\s+", " ", crudo)[:140], numero_de(crudo, siglas)
    if (pg.meta or {}).get("foto", 0) >= 0.13:
        return "Panel fotográfico", ""
    return "", ""


def _serie_cpe(texto):
    t = _n(texto)
    m = re.search(r"\b([EFB][A-Z0-9O]{3})\s*[-–]\s*(\d{1,8})\b", t)
    if not m:
        return ""
    serie = m.group(1)[0] + m.group(1)[1:].replace("O", "0")
    return f"{serie}-{int(m.group(2))}"


# ---------------------------------------------------------------- léxico ----
class Lexico:
    """Diccionario del PROPIO expediente: las palabras que se leyeron con confianza
    alta en el texto impreso (normalizada -> forma escrita más frecuente, con tildes).
    Con él se corrige lo que el OCR lee a medias en sellos y firmas
    («Adminisiración» -> «Administración») y se descarta lo que no es texto («AA ab»)."""

    EXTRA = {"FOLIO", "FECHA", "HORA", "FIRMA", "RECIBIDO", "RECIBIDA", "PROVEIDO", "REG", "EXP",
             "EXPEDIENTE", "MESA", "PARTES", "TRAMITE", "DOCUMENTARIO", "GERENTE", "SUBGERENTE", "JEFE",
             "MUNICIPALIDAD", "PROVINCIAL", "CALLAO", "GERENCIA", "SUBGERENCIA", "OFICINA", "LOGISTICA",
             "ADMINISTRACION", "RECEPCION", "DOCUMENTO", "SIGNIFICA", "ACEPTACION", "CONTENIDO", "VISTO",
             "BUENO"} | set(MESES)

    def __init__(self, doc=None):
        formas = {}
        for pg in (doc.pages if doc else []):
            for l in pg.lines:
                for w in (l.words or []):
                    t = w.text.strip(".,;:()«»\"'|“”!¡?¿*")
                    if len(t) >= 3 and t.isalpha() and (w.conf or 0) >= 0.9:
                        formas.setdefault(_n(t), Counter())[t] += 1
        self.forma = {k: c.most_common(1)[0][0] for k, c in formas.items()}
        self.cuenta = {k: sum(c.values()) for k, c in formas.items()}
        for k in self.EXTRA:
            self.forma.setdefault(k, k.title() if len(k) > 3 else k)
        self._por_largo = {}
        for k in self.forma:
            self._por_largo.setdefault(len(k), []).append(k)
        self._cache = {}

    def __contains__(self, palabra):
        return _n(palabra) in self.forma

    def corregir(self, palabra):
        """(forma corregida, ¿reconocida?)"""
        from difflib import get_close_matches
        k = _n(palabra)
        if k in self.forma:
            return self.forma[k], True
        if len(k) < 5 or not k.isalpha():
            return palabra, False
        if k not in self._cache:
            cands = [w for n in range(len(k) - 2, len(k) + 3) for w in self._por_largo.get(n, ())]
            c = get_close_matches(k, cands, n=1, cutoff=0.8)
            r = SequenceMatcher(None, k, c[0]).ratio() if c else 0
            ok = bool(c) and (c[0][0] == k[0] or r >= 0.9) and (abs(len(c[0]) - len(k)) <= 1 or r >= 0.9)
            self._cache[k] = (self.forma[c[0]], True) if ok else (palabra, False)
        forma, ok = self._cache[k]
        return (_como(palabra, forma) if ok else forma), ok


def _como(original, forma):
    """La forma corregida con las mayúsculas de lo leído: GERENCIA / Gerencia / gerencia."""
    letras = [c for c in original if c.isalpha()]
    if letras and all(c.isupper() for c in letras):
        return forma.upper()
    if letras and letras[0].isupper():
        return forma[:1].upper() + forma[1:].lower()
    return forma.lower()


_CORTAS = {"IA": "la", "DEI": "del", "EI": "el", "ei": "el", "Ia": "la", "Io": "lo", "IO": "lo", "IOS": "los",
           "Ios": "los", "Ias": "las", "IAS": "las", "dei": "del", "ia": "la", "ias": "las", "ios": "los"}


def pulir(texto, lex):
    """Corrige, con el léxico del expediente, lo que el OCR confunde en un texto corto
    (cargo, asunto): «Subgerencia de ia Oficina» -> «de la», «dei Pro:rama» -> «del
    Programa», «MOR!» -> «MORI». Solo cambia palabras que así pasan a existir."""
    if not texto or lex is None:
        return texto

    def arreglar(m):
        w = m.group(0)
        if w in _CORTAS:
            return _CORTAS[w]
        if w.isdigit() or w in lex:
            return w
        limpio = re.sub(r"[:;|!¡]", "", w) if not w.endswith("!") else w[:-1] + "I"
        cands = [limpio, w.replace("!", "I").replace("|", "I")] + \
                [re.sub(r"[:;|!¡]+", c, w) for c in "glitfjr"]
        for cand in cands:
            if cand != w and len(cand) >= 3 and cand in lex:
                return _como(cand, lex.forma[_n(cand)])
        if len(w) >= 6 and w.isalpha():
            c, ok = lex.corregir(w)
            if ok and SequenceMatcher(None, _n(c), _n(w)).ratio() >= 0.85:
                return c
        return w

    texto = re.sub(r"\bN\s?[*º°'\"”]\s?(?=\d)", "N° ", texto)
    return re.sub(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ:;|!¡]*[A-Za-zÁÉÍÓÚÜÑáéíóúüñ!]|[A-Za-z]+", arreglar, texto)


_FECHA_SELLO = re.compile(r"\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*\d{2,4}|\b\d{1,2}\s+(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|"
                          r"SET|SEP|OCT|NOV|DIC)[A-Z]*\.?\s+(19|20)?\d\d\b")


def texto_legible(lineas, lex):
    """Los renglones de un sello que SON texto: palabras del expediente (corregidas),
    fechas, horas y números; sin repetidos ni migas del OCR."""
    out, vistos = [], []
    for l in lineas:
        t = (l.text if hasattr(l, "text") else str(l)).strip()
        tn = _n(t)
        if _FECHA_SELLO.search(tn) or re.search(r"HORA\W{0,3}\d", tn):
            partes = [t]
        else:
            partes, buenas, total, largas = [], 0, 0, 0
            toks = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+|\d[\d/.\-]*", t)
            unidos = []
            for tk in toks:
                junto = _n(unidos[-1] + tk) if unidos else ""
                if unidos and tk.isalpha() and unidos[-1].isalpha() and junto in lex.forma and len(junto) >= 7 \
                        and lex.cuenta.get(junto, 2) > max(lex.cuenta.get(_n(tk), 0), lex.cuenta.get(_n(unidos[-1]), 0)):
                    unidos[-1] += tk
                else:
                    unidos.append(tk)
            for tk in unidos:
                if tk[0].isdigit():
                    partes.append(tk)
                    continue
                if len(tk) < 3:
                    if _n(tk) in ARTICULOS or _n(tk) in ("N", "NO", "AL"):
                        partes.append("N°" if _n(tk) == "N" else tk)
                    continue
                total += 1
                c, ok = lex.corregir(tk)
                if ok:
                    buenas += 1
                    largas += len(tk) >= 5
                    partes.append(c)
            if not total or buenas / total < 0.6 or not largas:
                continue
        s = re.sub(r"\s+", " ", " ".join(partes)).strip(" -/")
        k = re.sub(r"[^A-Z0-9]", "", _n(s))
        if len(k) < 3 or any(k in v for v in vistos):
            continue
        vistos = [v for v in vistos if v not in k] + [k]
        out = [o for o in out if re.sub(r"[^A-Z0-9]", "", _n(o)) not in k] + [s]
    return out


_OFICINA = re.compile(r"^(SUB ?GERENCIA|GERENCIA|OFICINA|MESA DE PARTES|UNIDAD|AREA|ALCALDIA|SECRETARIA)"
                     r"((\s+(DE|DEL|LA|Y|GENERAL))*\s+[A-Z]{4,}|\s*$)")


def _oficina(renglones):
    """La dependencia del sello: el renglón de oficina más específico (el último)."""
    ofs = []
    for r in renglones:
        # desde la ÚLTIMA dependencia nombrada en el renglón («gerencia Oficina de Logística»)
        cortes = [m.start() for m in re.finditer(r"\b(SUB ?GERENCIA|GERENCIA|OFICINA|UNIDAD)\b", _n(r))]
        for i in reversed(cortes):
            cola = r[i:] if len(r) == len(_n(r)) else r[i:]
            if _OFICINA.search(_n(cola)) and len(cola) <= 70 and len([w for w in _n(cola).split() if len(w) >= 4]) >= 2:
                ofs.append(cola)
                break
    if not ofs:
        return ""
    ws = ofs[-1].split()
    while ws and (len(ws[-1]) <= 2 or _n(ws[-1]) in ARTICULOS):
        ws.pop()
    return _bonito(" ".join(ws))


_TILDES = {"AREA": "Área", "LOGISTICA": "Logística", "ADMINISTRACION": "Administración", "RECEPCION": "Recepción",
           "TESORERIA": "Tesorería", "ALMACEN": "Almacén", "GESTION": "Gestión", "INFORMATICA": "Informática",
           "TECNOLOGIAS": "Tecnologías", "INFORMACION": "Información", "PLANIFICACION": "Planificación",
           "MODERNIZACION": "Modernización", "CONTRATACION": "Contratación", "CONTRATACIONES": "Contrataciones",
           "ECONOMICO": "Económico", "JURIDICA": "Jurídica", "PUBLICA": "Pública", "PUBLICAS": "Públicas",
           "ALCALDIA": "Alcaldía", "SECRETARIA": "Secretaría", "AUDITORIA": "Auditoría", "PATRIMONIO": "Patrimonio",
           "GERENCIA": "Gerencia", "FISCALIZACION": "Fiscalización", "PARTICIPACION": "Participación"}


_ABREVIATURAS = {"SERV": "Serv.", "AUX": "Aux.", "ADM": "Adm.", "ADMIN": "Adm.", "GRAL": "Gral.", "COORD": "Coord.",
                 "ESP": "Esp.", "ASIST": "Asist."}


def _bonito(t):
    """«OFICINA DE LOGÍSTICA» -> «Oficina de Logística» (conserva siglas y tildes)."""
    ws = []
    for i, w in enumerate(t.split()):
        if _n(w) in _TILDES and _n(w) == re.sub(r"[^A-Z]", "", _n(w)):
            ws.append(_TILDES[_n(w)])
            continue
        if _n(w).strip(".,") in _ABREVIATURAS:
            ws.append(_ABREVIATURAS[_n(w).strip(".,")])
            continue
        if i and _n(w) in ARTICULOS | {"Y"}:
            ws.append(w.lower())
        elif len(w) <= 5 and w.isupper() and not _n(w) in Lexico.EXTRA and re.fullmatch(r"[A-Z]+", _n(w)) \
                and _n(w) not in INSTITUCION:
            ws.append(w)                                     # sigla: OGAF, SGPVL
        else:
            ws.append(w[:1].upper() + w[1:].lower())
    return " ".join(ws)


_CONTINUA_CARGO = INSTITUCION | ARTICULOS | {"ADQUISICIONES", "ABASTECIMIENTO", "AUXILIARES", "SERV", "USUARIA",
                                            "CONTRATOS", "MENORES", "BIENES", "COMPRAS", "CONTROL", "PREVIO",
                                            "PATRIMONIO", "ALMACEN", "Y"}


_PALABRAS_CARGO = ("SUBGERENTE", "GERENTE", "DIRECTOR", "DIRECTORA", "RESPONSABLE", "ALCALDE", "ASISTENTE",
                   "ESPECIALISTA", "COORDINADOR", "COORDINADORA", "ANALISTA", "SECRETARIA", "ADMINISTRADOR",
                   "TESORERO", "CONTADOR", "ENCARGADO", "ENCARGADA")


def _cargo_difuso(t):
    """«sun GENENTEFecha» -> «SUB GERENTE»: la palabra de cargo mal leída (o pegada a
    la siguiente) se reconoce por parecido con las palabras de cargo."""
    toks = re.findall(r"[A-Z]+", t)
    for i, tk in enumerate(toks):
        for cw in _PALABRAS_CARGO:
            if len(tk) >= len(cw) - 1 and SequenceMatcher(None, tk[:len(cw)], cw).ratio() >= 0.84:
                sub = i > 0 and SequenceMatcher(None, toks[i - 1], "SUB").ratio() >= 0.66
                return ("SUB " if sub and cw == "GERENTE" else "") + cw
    return ""


def cargo_en(texto):
    """El cargo completo que empieza en la palabra de cargo: «RESPONSABLE DE
    ADQUISICIONES Y SERV. AUXILIARES», «SUB GERENTE», «JEFE DE ÁREA USUARIA»."""
    t = _n(texto)
    m = CARGOS.search(t)
    if not m:
        d = _cargo_difuso(t)
        return _bonito(d) if d else ""
    ws = [m.group(1).replace("SUBGERENTE", "SUB GERENTE")]
    for w in re.findall(r"[A-Z]+", t[m.end():])[:8]:
        if w not in _CONTINUA_CARGO or CARGOS.fullmatch(w) or w in ("RESPONSABLE", "JEFE", "GERENTE"):
            break
        ws.append(w)
    while ws and ws[-1] in ARTICULOS | {"Y", "E"}:
        ws.pop()
    return _bonito(" ".join(ws))


# ------------------------------------------------------------------- sellos ---
def _proveido(t):
    w = re.findall(r"[A-Z]{5,}", t[:25])
    return bool(w) and not w[0].startswith("PROVEED") and SequenceMatcher(None, w[0], "PROVEIDO").ratio() >= 0.75


def _tipo_sello(t, corto, gris=False):
    """Clase de sello por su texto (normalizado). 'corto': el renglón ancla es breve.
    'gris': no hay tinta de color que lo delimite; se exige una frase de sello (no
    basta la palabra «recepción», que también está en los formularios impresos)."""
    if re.match(r"^\W{0,3}[A-Z]{5,}", t) and _proveido(t):
        return "proveído"
    if re.search(r"RECEPCION DE ESTE|NO SIGNIFICA LA ACEPTACION|NO VALIDA SU CONTENIDO|SIGNIFICA LA ACEPTACION", t):
        return "recepción"
    if corto and re.search(r"\b(RECIBID[OA]|RECIBI)\b", t) and (not gris or len(t.split()) <= 4):
        return "recepción"
    if corto and not gris and re.search(r"\bRECEPCION\b", t):
        return "recepción"
    if corto and re.search(r"\bFOLIO\b", t) and (not gris or len(t.split()) <= 5):
        return "folio"
    if corto and re.search(r"\bV\s?[°O*.]?\s?B\s?[°O*.]?\b", t) and len(t) <= 30:
        return "visto bueno"
    return None


def _datos_sello(s, texto, lineas_caja, renglones):
    t = _n(texto)
    if s["tipo"] in ("recepción", "proveído"):
        s["fecha"], s["hora"] = fecha_de(texto), hora_de(texto)
    if s["tipo"] == "proveído":
        s["numero"] = numero_de(texto)
        dest = next((r for r in renglones if re.match(r"^(AL?|A LA|PARA)\b", _n(r)) and len(r) > 6), "")
        if dest:
            s["destino"] = dest
    if s["tipo"] == "folio":
        # el número del folio va en el recuadro de al lado (casi siempre a mano)
        nums = [re.sub(r"\D", "", l.text) for l in lineas_caja
                if re.fullmatch(r"\W*\d{1,3}\W*", l.text.strip())]
        s["numero"] = nums[0] if nums else ""
    if s["tipo"] == "recepción" or (s["tipo"] == "institucional" and re.search(r"\bFECHA\b", t) and re.search(r"\bHORA\b", t)):
        s["tipo"] = "recepción"
        s["fecha"], s["hora"] = s.get("fecha") or fecha_de(texto), s.get("hora") or hora_de(texto)
    of = _oficina(renglones)
    if of:
        s["oficina"] = of
    s["descripcion"] = describir_sello(s)
    return s


def describir_sello(s):
    """Una línea legible del sello: «Recibido – Oficina de Logística, 23/04/2026 16:19»."""
    tp = s["tipo"]
    cuando = " ".join(x for x in (s.get("fecha"), s.get("hora")) if x)
    if tp == "folio":
        d = "Folio" + (f" N° {s['numero']}" if s.get("numero") else " (número no legible)")
    elif tp == "recepción":
        d = "Recibido"
    elif tp == "proveído":
        d = "Proveído" + (f" N° {s['numero']}" if s.get("numero") else "")
    elif tp == "visto bueno":
        d = "V°B°"
    elif tp == "post-firma":
        d = "Sello de firma: " + s.get("nombre", "") + (f" – {s['cargo']}" if s.get("cargo") else "")
    elif tp == "firma manuscrita":
        return f"Firma manuscrita (tinta {s.get('color') or 'de color'})"
    else:
        d = "Sello"
    if s.get("oficina") and tp != "post-firma":
        d += f" – {s['oficina']}"
    if cuando:
        d += f", {cuando}"
    if s.get("destino"):
        d += f" · {s['destino']}"
    return d


def _lineas_en(lineas, b, m=0.01):
    """Los renglones DENTRO de la caja `b`, recortados a las palabras que caen en ella
    (un renglón que cruza el sello trae texto impreso de afuera)."""
    from ocr.base import OCRLine

    def adentro(bb):
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        return b[0] - m <= cx <= b[2] + m and b[1] - m <= cy <= b[3] + m

    out = []
    for l in lineas:
        if not l.words:
            if adentro(l.bbox):
                out.append(l)
            continue
        ws = [w for w in l.words if adentro(w.bbox)]
        if not ws or len(ws) < 0.5 * len(l.words):
            continue                      # renglón del cuerpo que el sello apenas pisa
        if len(ws) == len(l.words):
            out.append(l)
            continue
        out.append(OCRLine(text=" ".join(w.text for w in ws), conf=sum(w.conf for w in ws) / len(ws),
                           bbox=(min(w.bbox[0] for w in ws), min(w.bbox[1] for w in ws),
                                 max(w.bbox[2] for w in ws), max(w.bbox[3] for w in ws)),
                           page=l.page, words=ws, manuscrita=l.manuscrita))
    return out


def sellos_de_pagina(pg, regiones=(), registro=None, lex=None):
    """Sellos de una hoja: por la TINTA de color cuando la hay (la región ES el sello) y
    por su TEXTO cuando el sello quedó gris en el escaneo.
    [{tipo, descripcion, texto, fecha, hora, numero, oficina, nombre, cargo, pagina, bbox}]"""
    lex = lex or Lexico()
    lineas = sorted(pg.lines + _lectura_sellos(pg), key=lambda l: (_yc(l), l.bbox[0]))
    breves = [l for l in lineas if (l.bbox[2] - l.bbox[0]) <= 0.45]        # los sellos no traen renglones largos
    out, usados = [], set()

    def dentro(b, l, m=0.01):
        cx, cy = (l.bbox[0] + l.bbox[2]) / 2, _yc(l)
        return b[0] - m <= cx <= b[2] + m and b[1] - m <= cy <= b[3] + m

    def persona_en(caja):
        texto = " ".join(l.text for l in caja)
        pers = registro.buscar(texto) if registro else []
        if not pers and registro:
            for l in caja:
                pers = registro.buscar_difuso(l.text)
                if pers:
                    break
        return pers

    foto = (pg.meta or {}).get("foto", 0) >= 0.13
    regiones = [] if foto else list(regiones or ())          # en una hoja de fotos el color es de las fotos
    # 1) sellos de color: la región delimita el sello exacto
    for r in regiones:
        if r.get("forma") != "sello":
            continue
        caja = _lineas_en(lineas, r["bbox"])
        if not caja:
            continue
        texto = " / ".join(l.text.strip() for l in caja)
        renglones = texto_legible(caja, lex)
        tn = _n(texto)
        tipo = next((tp for tp in (_tipo_sello(_n(l.text), True) for l in caja) if tp), None)
        personas = persona_en(caja)
        if not tipo and "FOLIO" in tn.replace(" ", ""):
            tipo = "folio"
        if not tipo and personas:
            tipo = "post-firma"
        if not tipo:
            reales = {_n(w) for r_ in renglones for w in r_.split()}
            if len(reales) < 2 or not (reales & {"MUNICIPALIDAD", "GERENCIA", "SUBGERENCIA", "OFICINA", "PROGRAMA"}):
                continue                           # tinta de color sin texto de sello legible
            tipo = "institucional"
        for l in caja:
            usados.add(id(l))
        s = {"tipo": tipo, "texto": " / ".join(renglones)[:300], "pagina": pg.number, "bbox": r["bbox"],
             "color": r.get("color", "")}
        if tipo == "post-firma":
            s["nombre"] = personas[0]["nombre"]
            s["cargo"] = next((cargo_en(l.text) for l in caja if cargo_en(l.text)), "") or personas[0].get("cargo", "")
        s = _datos_sello(s, texto, caja, renglones)
        if tipo == "institucional" and not s.get("oficina"):
            continue                              # «MUNICIPALIDAD PROVINCIAL» y nada más
        out.append(s)
    # 2) sellos grises: renglón ancla + los breves que caen en su columna, justo debajo
    for ln in breves:
        if id(ln) in usados:
            continue
        tipo = _tipo_sello(_n(ln.text), len(ln.text.strip()) <= 60, gris=True)
        if not tipo:
            continue
        arriba, abajo = {"proveído": (0.02, 0.2), "recepción": (0.07, 0.07)}.get(tipo, (0.02, 0.05))
        x0, x1 = ln.bbox[0] - 0.04, ln.bbox[2] + 0.08
        caja = [l for l in breves if id(l) not in usados and x0 <= (l.bbox[0] + l.bbox[2]) / 2 <= x1
                and ln.bbox[1] - arriba <= _yc(l) <= ln.bbox[3] + abajo]
        for l in caja:
            usados.add(id(l))
        texto = " / ".join(l.text.strip() for l in caja)
        renglones = texto_legible(caja, lex)
        out.append(_datos_sello({"tipo": tipo, "texto": " / ".join(renglones)[:300], "pagina": pg.number,
                                 "bbox": [min(l.bbox[0] for l in caja), min(l.bbox[1] for l in caja),
                                          max(l.bbox[2] for l in caja), max(l.bbox[3] for l in caja)]},
                                texto, caja, renglones))
    # post-firma: nombre + cargo juntos (sello del funcionario o pie de firma)
    for f in filas([l for l in lineas if _yc(l) >= 0.45]):
        t = _n(_texto_fila(f))
        if CARGOS.search(t):
            arriba = [l for l in lineas if 0 < _yc(f[0]) - _yc(l) <= 0.045]
            candidatos = list(f) + arriba
            for cl in candidatos:
                c = cl.text
                personas = (registro.buscar(c) or registro.buscar_difuso(c)) if registro else []
                sin_registro = nombre_en(c)
                if personas or (sin_registro and es_nombre(sin_registro) and
                                sum(1 for w in sin_registro.split() if len(w) >= 3) >= 3):
                    # el cargo es el de SU columna (en la fila hay otras casillas)
                    cargo = next((x for x in (cargo_en(tx) for tx in [c] + _columna(cl, lineas, 0, 0.05)) if x), "")
                    s = {"tipo": "post-firma", "texto": " / ".join(texto_legible([c] + _columna(cl, lineas, 0, 0.05), lex))[:200],
                         "pagina": pg.number, "nombre": personas[0]["nombre"] if personas else nombre_en(c),
                         "cargo": cargo,
                         "bbox": [min(l.bbox[0] for l in f), min(l.bbox[1] for l in f),
                                  max(l.bbox[2] for l in f), max(l.bbox[3] for l in f)]}
                    s["descripcion"] = describir_sello(s)
                    if not any(o.get("nombre") == s["nombre"] and o["tipo"] == "post-firma" for o in out):
                        out.append(s)
                    break
    # firmas manuscritas: trazos de tinta azul o violeta, en la parte baja de la hoja
    for r in regiones:
        ancho, alto_r = r["bbox"][2] - r["bbox"][0], r["bbox"][3] - r["bbox"][1]
        if r.get("forma") == "trazo" and r["bbox"][1] > 0.3 and r.get("color") in ("azul", "violeta") \
                and ancho >= 0.06 and alto_r >= 0.025:
            s = {"tipo": "firma manuscrita", "texto": f"trazo de tinta {r.get('color', '')}",
                 "pagina": pg.number, "bbox": r["bbox"], "color": r.get("color", "")}
            s["descripcion"] = describir_sello(s)
            out.append(s)
    return out


def _lectura_sellos(pg):
    """Renglones leídos en la imagen de SOLO tinta de color (si el lector la hizo)."""
    from ocr.base import OCRLine
    out = []
    for d in (pg.meta or {}).get("lectura_sellos", []) or []:
        try:
            out.append(OCRLine(text=d["text"], conf=d.get("conf", 0.5), bbox=tuple(d["bbox"]), page=pg.number))
        except Exception:
            continue
    return out


# ---------------------------------------------------------------- firmantes ---
# renglones impresos que marcan dónde va una firma (formularios y pies de firma)
_CASILLA_FIRMA = re.compile(r"FIRMA DEL SOLIC[A-Z]*|FIRMA AUTORIZADA|JEFE DE(L)? AREA USUARIA|"
                            r"RESPONSABLE DE ADQUISICIONES|RESPONSABLE DE ABASTECIMIENTO|FIRMA Y SELLO|"
                            r"(?<![A-Z])(EL)?ABORADO POR|REVISADO POR|APROBADO POR|FIRMA DEL (PROVEEDOR|CONTRATISTA|JEFE)")
TIPOS_CON_REMITENTE = ("informe", "memorando", "carta", "oficio")
_ROLES = {"ELABORADOPOR": "elaboró", "ABORADOPOR": "elaboró", "CONFORMIDAD": "da conformidad", "FIRMADELSOLI": "solicitante", "FIRMAAUTORIZ": "autoriza",
          "CONFORMIDADD": "da conformidad", "JEFEDEAREAUS": "jefe del área usuaria",
          "JEFEDELAREAU": "jefe del área usuaria", "REVISADOPOR": "revisó", "APROBADOPOR": "aprobó",
          "VB": "visto bueno", "VOB": "visto bueno"}


def _rol(etiqueta):
    k = re.sub(r"\W", "", _n(etiqueta))
    return _ROLES.get(k[:12]) or _ROLES.get(k) or _bonito(etiqueta.title()).lower()


def _columna(ln, lineas, desde, hasta):
    """Texto de las PALABRAS que están en la columna del renglón `ln`, entre `desde` y
    `hasta` (fracción de hoja, relativo a su centro), agrupado por renglón. Trabaja con
    palabras y no con renglones porque en las tablas el OCR junta columnas vecinas."""
    x0, x1, y = ln.bbox[0] - 0.03, ln.bbox[2] + 0.03, _yc(ln)
    pal = []
    for l in lineas:
        if l is ln or not (desde <= _yc(l) - y <= hasta) or _yc(l) == y:
            continue
        ws = l.words or [l]
        for w in ws:
            cx = (w.bbox[0] + w.bbox[2]) / 2
            if x0 <= cx <= x1:
                pal.append(w)
    grupos = filas(pal) if pal else []
    grupos.sort(key=lambda f: abs(_yc(f[0]) - y))
    return [" ".join(w.text for w in f) for f in grupos]


def firmantes_de(seg, doc, registro, sellos, esperado=None, lex=None):
    """Quién firma el documento, con su cargo:
      1. nombres del registro en el pie (después de «Atentamente», o en la parte baja),
         leídos limpios o destrozados por la firma encima (comparación por letras);
      2. sellos de post-firma;
      3. el remitente («DE») de un memorando/informe firma su documento: si el sello
         no se pudo leer, se pone igual y se marca «por: remitente»;
      4. casillas de firma de un formulario («Firma autorizada», «Jefe de área
         usuaria») firmadas pero con el nombre ilegible: se devuelve la casilla con su
         cargo y nombre vacío, para que se vea que hay una firma sin identificar."""
    out = []
    paginas = [p for p in range(seg.pagina_ini, seg.pagina_fin + 1)
               if not (doc.pages[p - 1].meta or {}).get("en_blanco")]
    if not paginas:
        return out
    zonas = []
    for p in paginas:
        pg = doc.pages[p - 1]
        corte = 0.55
        for ln in pg.lines:
            if re.search(r"ATENTAMENTE|SIN OTRO PARTICULAR|FIRMA DEL|RESPONSABLE DE ADQUISICIONES|"
                         r"ELABORADO POR|JEFE DE AREA", _n(ln.text)):
                corte = min(corte, _yc(ln) - 0.02)
        zonas.append((p, [l for l in pg.lines if _yc(l) >= corte] + _lectura_sellos(pg)))
    vistos = set()

    def agregar(per, p, y, cargo="", por=None, rol="", xc=None):
        if per["nombre"] in vistos:
            return
        vistos.add(per["nombre"])
        firma = any(s["tipo"] == "firma manuscrita" and s["pagina"] == p and
                    abs((s["bbox"][1] + s["bbox"][3]) / 2 - y) < 0.12 for s in sellos)
        x = {"nombre": per["nombre"], "cargo": cargo or per.get("cargo", ""), "pagina": p,
             "firma_manuscrita": True if firma else None, "_y": y, "_x": xc}
        if por:
            x["por"] = por
        if rol:
            x["rol"] = rol
        out.append(x)

    def cargo_bajo(ln, zona):
        """El cargo impreso bajo el nombre (en su misma columna): «SUB GERENTE»."""
        suyo = cargo_en(ln.text)
        if suyo:
            return suyo
        for texto in _columna(ln, zona, 0, 0.05):
            c = cargo_en(texto)
            if c:
                return c
        for texto in _columna(ln, zona, 0, 0.05):
            if _OFICINA.search(_n(texto)):
                return _bonito(texto.strip())
        return ""

    def rol_en(ln, pg):
        """El papel de la persona en ESTE documento, por la casilla del formulario donde
        está su nombre: «ELABORADO POR», «CONFORMIDAD DEL SERVICIO», «FIRMA AUTORIZADA»."""
        for texto in _columna(ln, pg.lines, -0.07, 0.07):
            m = _CASILLA_FIRMA.search(_n(texto)) or re.search(r"\bCONFORMIDAD\b|\bV\W?B\W?\b", _n(texto))
            if m:
                return _rol(m.group(0))
        return ""

    for p, zona in zonas:
        for f in filas(zona):
            txt = _texto_fila(f)
            encontrados = registro.buscar(txt) or registro.buscar_difuso(txt)
            for per in encontrados:
                # el renglón exacto del nombre (en la fila puede haber otras columnas)
                ln = max(f, key=lambda l: (len(registro.clave(per["nombre"]) & set(_tokens(l.text))),
                                           SequenceMatcher(None, re.sub(r"[^A-Z]", "", per["nombre"]),
                                                           re.sub(r"[^A-Z]", "", _n(l.text))).ratio()))
                agregar(per, p, _yc(ln), cargo_bajo(ln, zona), rol=rol_en(ln, doc.pages[p - 1]),
                        xc=(ln.bbox[0] + ln.bbox[2]) / 2)
    for s in sellos:
        if s["tipo"] == "post-firma" and s.get("nombre") and s["nombre"] not in vistos:
            per = registro.buscar(s["nombre"])
            per = per[0] if per else {"nombre": s["nombre"], "cargo": ""}
            agregar(per, s["pagina"], (s["bbox"][1] + s["bbox"][3]) / 2 if s.get("bbox") else 0.8,
                    s.get("cargo", ""))
    # el remitente firma su memorando/informe
    if esperado and seg.tipo in TIPOS_CON_REMITENTE and es_nombre(esperado.get("nombre", "")) and \
            not any(registro.clave(esperado["nombre"]) == registro.clave(x["nombre"]) for x in out):
        p, zona = zonas[-1]
        for pp, z in zonas:                        # la hoja donde está «Atentamente»
            if any(re.search(r"ATENTAMENTE|SIN OTRO PARTICULAR", _n(l.text)) for l in z):
                p, zona = pp, z
        if not out:
            per = registro.buscar(esperado["nombre"])
            cargo = esperado.get("cargo") or (per[0].get("cargo", "") if per else "")
            agregar({"nombre": esperado["nombre"], "cargo": cargo}, p, 0.7, por="remitente")
    # casillas de firma de formularios sin nombre legible
    for p in (paginas if seg.tipo not in TIPOS_CON_REMITENTE else ()):
        pg = doc.pages[p - 1]
        for ln in pg.lines:
            m = _CASILLA_FIRMA.search(_n(ln.text))
            if not m or _yc(ln) < 0.3:
                continue
            y = _yc(ln)
            xc = (ln.bbox[0] + ln.bbox[2]) / 2
            if any(x["pagina"] == p and -0.15 <= y - x["_y"] <= 0.06 for x in out) or \
                    any(x.get("_x") is not None and x["nombre"] and abs(y - x["_y"]) <= 0.1 and abs(xc - x["_x"]) <= 0.2
                        for x in out):
                continue                  # ya se sabe quién firma ahí (en esta hoja o en su copia)
            # ¿hay firma? tinta de color o un renglón escrito justo encima de la casilla
            tinta = any(s["pagina"] == p and s["tipo"] in ("firma manuscrita", "post-firma", "institucional")
                        and -0.15 <= y - (s["bbox"][1] + s["bbox"][3]) / 2 <= 0.08 for s in sellos if s.get("bbox"))
            escrito = any(0 < y - _yc(l) <= 0.08 and abs(l.bbox[0] - ln.bbox[0]) < 0.25 and len(l.text.strip()) >= 3
                          for l in pg.lines if l is not ln)
            if tinta or escrito:
                es_cargo = bool(CARGOS.match(_n(m.group(0))))
                x = {"nombre": "", "cargo": cargo_en(m.group(0)) if es_cargo else "", "pagina": p,
                     "firma_manuscrita": None, "legible": False, "_y": y}
                if not es_cargo:
                    x["rol"] = _rol(m.group(0))
                if not any(o["pagina"] == p and not o["nombre"] and o["cargo"] == x["cargo"] and
                           o.get("rol") == x.get("rol") for o in out):
                    out.append(x)
    for x in out:
        x.pop("_y", None)
        x.pop("_x", None)
    return out


# -------------------------------------------------------------------- todo ----
def registro_de_personas(doc, segmentos, contexto=None):
    reg = Registro()
    for s in segmentos:
        pg = doc.pages[s.pagina_ini - 1]
        c = campos_cabecera(pg) if s.tipo not in ("orden_servicio", "pedido_servicio", "tdr") else {}
        for k in ("para", "de"):
            if k in c and es_nombre(c[k]["nombre"]):
                reg.agregar(c[k]["nombre"], c[k].get("cargo", ""), "cabecera")
    # proveedor, «elaborado por», «Señor(es):», «Encargado»: donde los nombres salen limpios
    for pg in doc.pages:
        ls = sorted(pg.lines, key=lambda l: (_yc(l), l.bbox[0]))
        for i, ln in enumerate(ls):
            t = _n(ln.text)
            m = re.search(r"(SENOR\s?\(?ES\)?|ENCARGAD[OA]\(?A?\)?|PROVEEDOR)\s*:", t)
            if m:
                nombre = nombre_en(ln.text.split(":", 1)[-1])
                if nombre and es_nombre(nombre):
                    reg.agregar(nombre, "Proveedor" if "PROVEEDOR" in m.group(1) or "SENOR" in m.group(1) else "",
                                "orden")
            if "ELABORADO POR" in t:
                nombre = " ".join(l.text for l in ls[i + 1:i + 4] if re.fullmatch(r"[A-ZÁÉÍÓÚÑ ,]+", l.text.strip()))
                if es_nombre(nombre):
                    reg.agregar(nombre, "Responsable de adquisiciones", "orden")
    if contexto and contexto.get("proveedor"):
        reg.agregar(contexto["proveedor"], "Proveedor", "orden")
    # firmas de pie bien leídas: nombre seguido de un renglón con cargo/oficina
    for pg in doc.pages:
        ls = sorted([l for l in pg.lines if _yc(l) > 0.5], key=lambda l: (_yc(l), l.bbox[0]))
        for i, ln in enumerate(ls[:-1]):
            if es_nombre(ln.text) and ln.conf >= 0.8 and ln.text.strip().isupper():
                sig = ls[i + 1].text
                if CARGOS.search(_n(sig)) or "OFICINA" in _n(sig):
                    reg.agregar(ln.text, sig.strip(), "firma")
    return reg


def fichas(doc, segmentos, regiones_por_pagina=None, contexto=None):
    """Una ficha por segmento (mismo orden)."""
    regiones_por_pagina = regiones_por_pagina or {}
    siglas = siglas_del_expediente(doc)
    lex = Lexico(doc)
    reg = registro_de_personas(doc, segmentos, contexto)
    for p in reg.personas.values():
        p["cargo"] = pulir(p.get("cargo", ""), lex)
    series = {}
    out = []
    for s in segmentos:
        pg = doc.pages[s.pagina_ini - 1]
        titulo, numero = titulo_de(s, doc, siglas)
        campos = campos_cabecera(pg) if s.tipo in ("informe", "memorando", "carta", "otro", "conformidad") else {}
        if not campos.get("fecha"):
            campos["fecha"] = _fecha_documento(pg)
        sellos = []
        for p in range(s.pagina_ini, s.pagina_fin + 1):
            pp = doc.pages[p - 1]
            if not (pp.meta or {}).get("en_blanco"):
                sellos += sellos_de_pagina(pp, regiones_por_pagina.get(p, ()), reg, lex)
        firmantes = firmantes_de(s, doc, reg, sellos, campos.get("de") if isinstance(campos.get("de"), dict) else None,
                                 lex)
        if s.tipo in ("comprobante_pago", "validez_cpe") and numero:
            series[s.tipo] = numero
        for k in ("de", "para"):
            if isinstance(campos.get(k), dict):
                campos[k]["cargo"] = pulir(campos[k].get("cargo", ""), lex)
                campos[k]["nombre"] = pulir(campos[k]["nombre"], lex)
                if not campos[k]["cargo"]:
                    per = reg.buscar(campos[k]["nombre"])
                    if per and per[0].get("cargo"):
                        campos[k]["cargo"] = pulir(per[0]["cargo"], lex)
        for k in ("asunto", "referencia"):
            if campos.get(k):
                campos[k] = pulir(campos[k], lex)
        for x in firmantes:
            x["cargo"] = pulir(x.get("cargo", ""), lex)
        out.append({"titulo": titulo or s.etiqueta, "numero": numero, **campos,
                    "firmantes": firmantes, "sellos": sellos})
    _completar_por_referencias(doc, segmentos, out, siglas)
    # la consulta de validez y la factura se confirman entre sí (misma serie)
    for s, f in zip(segmentos, out):
        if s.tipo == "comprobante_pago" and not f["numero"] and series.get("validez_cpe"):
            f["numero"] = series["validez_cpe"]
            f["titulo"] = f"{f['titulo']} {f['numero']}"
        f["resumen"] = resumen(f, s)
    return out, reg


_TIPO_REF = {"MEMORANDO": "memorando", "INFORME": "informe", "OFICIO": "memorando", "CARTA": "carta",
             "CONFORMIDAD DE SERVICIO": "conformidad", "CONFORMIDAD DE SERVICIOS": "conformidad",
             "ORDEN DE SERVICIO": "orden_servicio"}


def _completar_por_referencias(doc, segmentos, fichas_, siglas):
    """Un documento cuyo número no se pudo leer (p. ej. manuscrito) se completa con la
    cita que otro documento hace de él: «REF: MEMORANDO N° 2809-2026-MPC/OGAF/OLG».
    Solo si el tipo coincide, comparte siglas con lo que sí se leyó y el número no
    pertenece ya a otro documento del expediente."""
    citas = []
    for i, s in enumerate(segmentos):
        for p in range(s.pagina_ini, s.pagina_fin + 1):
            for m in re.finditer(r"(MEMORANDO|INFORME|OFICIO|CARTA|CONFORMIDAD DE SERVICIOS?)\s*N\W{0,3}\s*"
                                 r"(\d[0-9A-Z/\-\. ]{4,40})", _n(doc.pages[p - 1].text)):
                num = numero_de("N " + m.group(2), siglas)
                if num and not num.startswith(("S/N", "ILEGIBLE")):
                    citas.append((_TIPO_REF.get(m.group(1), ""), num, i, p))
    ya = {f["numero"] for f in fichas_ if f.get("numero")}
    for s, f in zip(segmentos, fichas_):
        if not f.get("numero", "").startswith("ILEGIBLE"):
            continue                      # solo números que existen pero no se pudieron leer
        leido = set(re.split(r"[-/]", f.get("numero", "") or "")) - {"", "ILEGIBLE"}
        for tipo, num, i, p in citas:
            if tipo != s.tipo or num in ya or segmentos[i] is s:
                continue
            siglas_cita = set(re.split(r"[-/]", num))
            if leido and len(leido & siglas_cita) < min(2, len(leido)):
                continue
            f["numero"] = num
            f["titulo"] = f"{_prefijo(s.tipo, f['titulo'])} N° {num}"
            f["numero_fuente"] = f"citado en la hoja {p}"
            ya.add(num)
            break
        else:
            if f.get("numero", "").startswith("ILEGIBLE"):
                f["titulo"] = f"{_prefijo(s.tipo, f['titulo'])} N° (no legible){f['numero'][8:]}"


def _fecha_documento(pg):
    """Fecha del documento: la etiquetada como tal antes que cualquier otra (no la de
    inicio del servicio ni la de un sello)."""
    ls = sorted(pg.lines, key=lambda l: (_yc(l), l.bbox[0]))
    for patron in (r"FECHA DE (INFORME|EMISION|CONFORMIDAD)|^FECHA\b", r"(CALLAO|LIMA),", r"\d{1,2} DE [A-Z]+ DEL? 20\d\d"):
        for l in ls:
            if re.search(patron, _n(l.text)) and "INICIO" not in _n(l.text):
                f = fecha_de(l.text)
                if f:
                    return f
    return ""


def describir_firmante(x):
    d = x["nombre"] or "(nombre no legible)"
    if x.get("cargo"):
        d += f" – {x['cargo']}"
    if x.get("rol"):
        d += f" [{x['rol']}]"
    return d


def resumen(f, seg):
    partes = [f["titulo"] or seg.etiqueta]
    if f.get("fecha"):
        partes.append(f["fecha"])
    if f.get("de"):
        partes.append("De: " + f["de"]["nombre"] + (f" ({f['de']['cargo']})" if f["de"].get("cargo") else ""))
    if f.get("para"):
        partes.append("Para: " + f["para"]["nombre"] + (f" ({f['para']['cargo']})" if f["para"].get("cargo") else ""))
    if f.get("asunto"):
        partes.append("Asunto: " + f["asunto"][:140])
    if f.get("firmantes"):
        partes.append("Firma: " + "; ".join(describir_firmante(x) for x in f["firmantes"][:4]))
    rec = [s for s in f.get("sellos", []) if s["tipo"] in ("recepción", "proveído", "folio", "visto bueno")]
    if rec:
        partes.append("Sellos: " + "; ".join(f"{s.get('descripcion') or s['tipo']} (hoja {s['pagina']})"
                                            for s in rec[:4]))
    return " · ".join(partes)
