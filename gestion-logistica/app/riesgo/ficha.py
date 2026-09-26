# -*- coding: utf-8 -*-
"""Ficha de cada documento del expediente: QUÉ es, sin tener que abrirlo.

Para cada documento que el segmentador reconoce se arma:

- el TÍTULO COMPLETO tal como está impreso: «INFORME N° 132-2026-MPC/GPS/SGPVL»,
  «MEMORANDO N° 2809-2026-MPC-OGAF-OLG», «ORDEN DE SERVICIO N° 0001234»…
- los CAMPOS del oficio: A / PARA, DE, ASUNTO, REFERENCIA y FECHA, con el
  nombre y el cargo de cada persona;
- las FIRMAS: nombre, cargo y oficina de quien firma (el sello de firma o el
  pie de firma), y
- los SELLOS: de recepción, de proveído, de «recibido», de folio y de visto
  bueno, con su oficina, fecha, hora y número.

Cómo se consigue leerlo bien (calibrado con un expediente real de
orden de servicio de 44 hojas escaneadas):

1. El OCR que trae el escáner lee «MPC/GPS/SGPVL» como «MPCIGPS/SGPVL» y los
   números a mano se los salta. Si hay Tesseract en el equipo, la cabecera y
   el pie de cada documento se vuelven a leer a 300 ppp (lectura enfocada).
2. Las siglas se corrigen con las que el propio expediente enseña: el membrete
   «GERENCIA DE PROGRAMAS SOCIALES» da «GPS», «SUBGERENCIA DEL PROGRAMA DE
   VASO DE LECHE» da «SGPVL». Una «I» o un «1» entre dos siglas conocidas es
   una «/» mal leída; un «0» dentro de una sigla es una «O».
3. Un número escrito a mano («MEMORANDO N° 28?9…») se confirma con la
   REFERENCIA de otro documento que lo cita escrito a máquina («REF: MEMORANDO
   N° 2809-2026-MPC/OGAF/OLG», pág. 33).
4. Los sellos se tiñen con tinta azul o violeta: se separan por COLOR del
   texto negro, cada sello se recorta y se lee solo.
5. Los nombres de las firmas salen rotos porque la firma los cruza; se
   reconocen comparándolos con las personas que el expediente ya nombra
   (A, DE, «Entregar a», el proveedor) y con el directorio de funcionarios.

Todo lo que no se pudo leer con seguridad se marca como tal: mejor un «sin
leer» a la vista que un dato inventado.
"""
from __future__ import annotations

import io
import re
import unicodedata
from difflib import SequenceMatcher

from .ocr_base import OCRLine, OCRWord

# ───────────────────────────────────────────────────────────── utilidades

def _sin_tildes(t):
    t = unicodedata.normalize("NFKD", t or "")
    return "".join(c for c in t if not unicodedata.combining(c))


def _norm(t):
    """MAYÚSCULAS, sin tildes, solo letras/números/espacios."""
    t = _sin_tildes(t).upper()
    t = re.sub(r"[^A-Z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _compacto(t):
    return re.sub(r"[^A-Z0-9]", "", _norm(t))


def _parecido(a, b):
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _yc(l):
    return (l.bbox[1] + l.bbox[3]) / 2


def _limpia(t):
    t = re.sub(r"\s+", " ", (t or "")).strip(" .,;:|'\"`´‘’“”_-—[]()")
    return t


def _titulo_propio(t):
    """«SUBGERENTE DE LA OFICINA DE LOGISTICA» -> «Subgerente de la Oficina de Logistica»."""
    menores = {"de", "del", "la", "las", "los", "el", "y", "e", "en", "a", "para", "por", "con"}
    pal = t.lower().split()
    return " ".join(p if (i and p in menores) else p[:1].upper() + p[1:] for i, p in enumerate(pal))


# ─────────────────────────────────────────────────────────────── siglas

# Siglas de la Municipalidad Provincial del Callao que aparecen en las
# nomenclaturas. Se completan con las que enseña cada expediente.
OFICINAS_BASE = [
    "OFICINA DE LOGISTICA", "GERENCIA DE ADMINISTRACION", "OFICINA GENERAL DE ADMINISTRACION Y FINANZAS",
    "SUBGERENCIA DEL PROGRAMA DE VASO DE LECHE", "GERENCIA DE PROGRAMAS SOCIALES", "OFICINA DE PRESUPUESTO",
    "OFICINA GENERAL DE PLANEAMIENTO MODERNIZACION PRESUPUESTO E INVERSIONES", "OFICINA DE CONTABILIDAD",
    "OFICINA DE TESORERIA", "GERENCIA MUNICIPAL", "OFICINA GENERAL DE ASESORIA JURIDICA",
    "SUBGERENCIA DE CONTRATOS MENORES", "GERENCIA DE DESARROLLO HUMANO", "ORGANO DE CONTROL INSTITUCIONAL",
    "SECRETARIA GENERAL", "ALCALDIA",
]

SIGLAS_BASE = {
    "MPC", "GM", "OGAF", "OLG", "OGPMPI", "OPR", "OP", "GPS", "SGPVL", "SGCM", "GDH",
    "SGCT", "OC", "OT", "OGAJ", "OCI", "GAT", "GDU", "GSC", "GGA", "SG", "ALC",
    "OGTI", "OCP", "OGRH", "SGRH", "GTSV", "GDE", "GSCGA", "PVL", "ULE", "OEC",
}
_NO_CUENTAN = {"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y", "E", "EN", "A", "PARA", "POR"}
_OFICINA_RE = re.compile(r"\b((?:SUB\s*)?GERENCIA|OFICINA(?:\s+GENERAL)?|SUBGERENCIA|UNIDAD|"
                         r"DIRECCION|DEPARTAMENTO|AREA)\b(.{6,90})")


def _sigla_de(nombre):
    """«SUBGERENCIA DEL PROGRAMA DE VASO DE LECHE» -> «SGPVL»."""
    n = _norm(nombre)
    n = re.sub(r"^SUB\s*GERENCIA", "SUB GERENCIA", n)
    letras = []
    for p in n.split():
        if p in _NO_CUENTAN:
            continue
        if p == "SUB":
            letras.append("S")
            continue
        letras.append(p[0])
    return "".join(letras)


def siglas_del_expediente(doc):
    """Siglas que el expediente enseña en sus membretes y en las
    nomenclaturas bien escritas (con «/» o «-» entre siglas)."""
    siglas = set(SIGLAS_BASE)
    oficinas = set(OFICINAS_BASE)
    vistas = {}
    paginas_ofi = {}
    for pg in doc.pages:
        for l in pg.lines:
            t = _norm(l.text)
            if len(t) > 90:
                continue
            m = _OFICINA_RE.search(t)
            if m and len(t.split()) <= 12:
                nombre = (m.group(1) + m.group(2)).strip()
                # solo membretes limpios: palabras de verdad, sin basura del OCR
                if all(len(p) > 1 or p in ("Y", "E", "A") for p in nombre.split()) and not re.search(r"\d", nombre) \
                        and _yc(l) < 0.2 and l.bbox[0] < 0.55:
                    paginas_ofi.setdefault(nombre, set()).add(pg.number)
                s = _sigla_de(nombre)
                if 3 <= len(s) <= 7:
                    siglas.add(s)
        for m in re.finditer(r"\b20\d\d\s*-\s*((?:[A-Z]{2,7}\s*[-/]\s*){1,5}[A-Z]{2,7})", _sin_tildes(pg.text).upper()):
            partes = [p for p in re.split(r"\s*[-/]\s*", m.group(1)) if p]
            if partes and partes[0] == "MPC":
                for p in partes:
                    if 2 <= len(p) <= 7:
                        vistas[p] = vistas.get(p, 0) + 1
    # un membrete se repite en varias hojas; una mala lectura, no
    oficinas.update(o for o, pags in paginas_ofi.items() if len(pags) >= 2)
    # una sigla vista una sola vez puede ser una mala lectura («SGPV»)
    siglas.update(p for p, n in vistas.items() if n >= 2)
    return siglas, oficinas


def conf_linea(l):
    return l.conf if l.conf else 0.7


def _corrige_sigla(tok, siglas):
    """Una sigla leída con errores -> la sigla conocida más parecida."""
    tok = tok.replace("0", "O").replace("5", "S").replace("8", "B")
    if tok in siglas or len(tok) < 3:
        return tok, tok in siglas
    mejor, r = None, 0.0
    for s in siglas:
        if abs(len(s) - len(tok)) > 1:
            continue
        if len(s) == len(tok) >= 4 and sum(a != b for a, b in zip(s, tok)) == 1:
            return s, True
        x = _parecido(tok, s)
        if x > r:
            mejor, r = s, x
    if mejor and r >= 0.8:
        return mejor, True
    return tok, False


def _parte_siglas(tok, siglas):
    """«MPCIGPS» -> ["MPC", "GPS"]: una I / l / 1 entre dos siglas conocidas
    es una «/» mal leída. Si no se puede partir, se deja entero."""
    if tok in siglas:
        return [tok]
    for i in range(2, len(tok) - 2):
        if tok[i] in "IL1|":
            a, b = tok[:i], tok[i + 1:]
            if a in siglas and (b in siglas or _parte_siglas(b, siglas) != [b]):
                return [a] + _parte_siglas(b, siglas)
    for i in range(2, len(tok) - 1):
        a, b = tok[:i], tok[i:]
        if a in siglas and b in siglas:
            return [a, b]
    return [tok]


# ─────────────────────────────────────────────────── títulos numerados

_CLASES = [
    (r"INFORME\s+T[EÉ]CNICO", "INFORME TÉCNICO"),
    (r"INFORME", "INFORME"),
    (r"MEMOR[AÁ]NDUM\s+M[UÚ]LTIPLE", "MEMORÁNDUM MÚLTIPLE"),
    (r"MEMORANDO\s+M[UÚ]LTIPLE", "MEMORANDO MÚLTIPLE"),
    (r"MEMOR[AÁ]NDUM", "MEMORÁNDUM"),
    (r"MEMORANDO", "MEMORANDO"),
    (r"OFICIO\s+M[UÚ]LTIPLE", "OFICIO MÚLTIPLE"),
    (r"OFICIO", "OFICIO"),
    (r"CARTA\s+NOTARIAL", "CARTA NOTARIAL"),
    (r"CARTA", "CARTA"),
    (r"PROVE[IÍ]DO", "PROVEÍDO"),
    (r"ORDEN\s+DE\s+SERVICIO", "ORDEN DE SERVICIO"),
    (r"ORDEN\s+DE\s+COMPRA", "ORDEN DE COMPRA"),
    (r"PEDIDO\s+DE\s+SERVICIO", "PEDIDO DE SERVICIO"),
    (r"PEDIDO\s+DE\s+COMPRA", "PEDIDO DE COMPRA"),
    (r"CONFORMIDAD\s+DE\s+SERVICIOS?", "CONFORMIDAD DE SERVICIOS"),
    (r"CONFORMIDAD\s+DE\s+BIENES", "CONFORMIDAD DE BIENES"),
    (r"CONFORMIDAD", "CONFORMIDAD"),
    (r"CERTIFICACI[OÓ]N\s+DE\s+CR[EÉ]DITO\s+PRESUPUESTARIO", "CERTIFICACIÓN DE CRÉDITO PRESUPUESTARIO"),
    (r"CERTIFICADO\s+DE\s+CR[EÉ]DITO\s+PRESUPUESTARIO", "CERTIFICADO DE CRÉDITO PRESUPUESTARIO"),
    (r"RESOLUCI[OÓ]N\s+DE\s+ALCALD[IÍ]A", "RESOLUCIÓN DE ALCALDÍA"),
    (r"RESOLUCI[OÓ]N\s+GERENCIAL", "RESOLUCIÓN GERENCIAL"),
    (r"RESOLUCI[OÓ]N\s+SUB\s*GERENCIAL", "RESOLUCIÓN SUBGERENCIAL"),
    (r"RESOLUCI[OÓ]N", "RESOLUCIÓN"),
    (r"ACTA\s+DE\s+[A-ZÁÉÍÓÚ]+", None),
    (r"SOLICITUD", "SOLICITUD"),
    (r"COTIZACI[OÓ]N", "COTIZACIÓN"),
    (r"PROFORMA", "PROFORMA"),
    (r"NOTA\s+DE\s+ENTRADA\s+(?:A|AL)\s+ALMAC[EÉ]N", "NOTA DE ENTRADA A ALMACÉN"),
    (r"PECOSA", "PECOSA"),
    (r"CONSTANCIA\s+DE\s+PRESTACI[OÓ]N", "CONSTANCIA DE PRESTACIÓN"),
]
_CLASE_RE = "(?P<clase>" + "|".join(p for p, _ in _CLASES) + ")"
# N°, Nº, N', N", N*, No, NRO., NÚMERO… (el OCR los escribe de mil maneras)
_NUMERAL = r"\s*(?:N\s*(?:[°º'\"*]|[oO](?=\s*[\d\[]))?\.?|NRO\.?|N[UÚ]MERO|N\s*ro\.?)\s*[:.]?\s*"
_NUM_RE = re.compile(
    _CLASE_RE + _NUMERAL +
    r"\[?\s*(?P<num>[0-9OoIl|SB£]{0,7}(?:[OoIl|SB0-9£]|\s(?=[-–]))?)"
    r"(?P<basura>[^\s\-–\d]{1,8}\s*(?=[-–]\s*2\s?[0O@]\s?2))?"
    r"(?:\s*[-–]\s*(?P<anio>2\s?[0O@]\s?2\s?[\dO@]))?"
    r"(?P<resto>(?:\s*[-–/]\s*[A-Z0-9]{1,9}){0,7})",
    re.I)


def _digitos(s):
    t = (s or "").upper()
    for a, b in (("O", "0"), ("I", "1"), ("L", "1"), ("|", "1"), ("S", "5"), ("B", "8"), ("£", "4")):
        t = t.replace(a, b)
    return re.sub(r"[^0-9]", "", t)


def _clase_canonica(texto):
    t = _sin_tildes(texto).upper()
    for pat, canon in _CLASES:
        if re.fullmatch(_sin_tildes(pat).upper().replace("[EE]", "E"), t) or re.fullmatch(pat, texto, re.I):
            return canon or re.sub(r"\s+", " ", texto.upper())
    return texto.upper()


def _lee_nomenclatura(m, siglas):
    """De un acierto de _NUM_RE -> dict con el título armado y cuán
    confiable es (0..1)."""
    clase = _clase_canonica(re.sub(r"\s+", " ", m.group("clase")))
    num = _digitos(m.group("num"))
    anio = (m.group("anio") or "").upper().replace("O", "0").replace("@", "0")
    ilegible = bool(m.group("basura")) and not num
    anio = re.sub(r"\s", "", anio)
    resto = (m.group("resto") or "").upper()
    # cada sigla con el separador que la precede, TAL COMO ESTÁ IMPRESO
    pares = re.findall(r"\s*([-–/])\s*([A-Z0-9]{1,9})", resto)
    siglas_ok, seps_ok, sal, conocidas = [], [], [], 0
    for sep_i, t in pares:
        sep_i = "-" if sep_i == "–" else sep_i
        if re.fullmatch(r"[0-9]{1,9}", t) and not siglas_ok:
            # «…-2026-0001234» (O/S con año delante)
            sal.append(t)
            continue
        partes = _parte_siglas(t.replace("0", "O"), siglas)
        for j, p in enumerate(partes):
            c, ok = _corrige_sigla(p, siglas)
            if len(c) == 1 or (not ok and len(c) > 7):
                continue
            conocidas += ok
            siglas_ok.append(c)
            # una «I» leída en lugar de «/» vuelve a ser «/»
            seps_ok.append(sep_i if j == 0 else "/")
    # las siglas desconocidas al final suelen ser basura de un sello pegado
    while siglas_ok and siglas_ok[-1] not in siglas and len(siglas_ok) > 1:
        siglas_ok.pop()
        seps_ok.pop()
    titulo = _arma(clase, num, anio, sal, siglas_ok, seps_ok, ilegible)
    conf = 0.35
    conf += 0.2 if num else 0
    conf += 0.2 if anio else 0
    conf += 0.25 * (conocidas / len(siglas_ok)) if siglas_ok else (0.15 if anio else 0)
    if ilegible:
        conf -= 0.15
    return {"titulo": titulo.strip(), "clase": clase, "numero": num, "anio": anio, "sal": sal,
            "siglas": siglas_ok, "seps": seps_ok, "ilegible": ilegible,
            "confianza": round(min(conf, 1.0), 2)}


def _arma(clase, num, anio, sal, siglas_ok, seps_ok, ilegible=False):
    partes = [x for x in ([num] if num else (["____"] if (anio or siglas_ok) else [])) +
              ([anio] if anio else []) + list(sal)]
    titulo = clase + " N° " + ("-".join(partes) if partes else "")
    if siglas_ok:
        titulo += "".join(sp + sg for sp, sg in zip(seps_ok, siglas_ok)) if partes else \
            "-" + siglas_ok[0] + "".join(sp + sg for sp, sg in zip(seps_ok[1:], siglas_ok[1:]))
    if not num and (anio or siglas_ok):
        titulo += "  (número ilegible)" if ilegible else "  (sin número)"
    return titulo


# qué clases de título le corresponden a cada tipo de documento del segmentador
_CLASES_DE_TIPO = {
    "orden_servicio": {"ORDEN DE SERVICIO", "ORDEN DE COMPRA"},
    "pedido_servicio": {"PEDIDO DE SERVICIO", "PEDIDO DE COMPRA"},
    "conformidad": {"CONFORMIDAD DE SERVICIOS", "CONFORMIDAD DE BIENES", "CONFORMIDAD"},
    "proveido": {"PROVEÍDO"},
    "certificacion": {"CERTIFICACIÓN DE CRÉDITO PRESUPUESTARIO", "CERTIFICADO DE CRÉDITO PRESUPUESTARIO"},
    "cotizacion": {"COTIZACIÓN", "PROFORMA"},
}
_DOCUMENTALES = {"INFORME", "INFORME TÉCNICO", "MEMORANDO", "MEMORÁNDUM", "MEMORANDO MÚLTIPLE",
                 "MEMORÁNDUM MÚLTIPLE", "OFICIO", "OFICIO MÚLTIPLE", "CARTA", "CARTA NOTARIAL",
                 "SOLICITUD", "RESOLUCIÓN", "RESOLUCIÓN GERENCIAL", "RESOLUCIÓN SUBGERENCIAL",
                 "RESOLUCIÓN DE ALCALDÍA"}


def _clase_admitida(clase, tipo):
    if tipo in _CLASES_DE_TIPO:
        return clase in _CLASES_DE_TIPO[tipo]
    if tipo in ("informe", "memorando", "informe_cuantia", "solicitud_ccp", "requerimiento"):
        return clase in _DOCUMENTALES or clase.startswith("ACTA")
    # en el resto (TDR, anexos, correos…) una «Orden de Servicio N°…» es una cita
    return clase not in {"ORDEN DE SERVICIO", "ORDEN DE COMPRA", "PEDIDO DE SERVICIO",
                         "PEDIDO DE COMPRA", "CONFORMIDAD DE SERVICIOS", "CONFORMIDAD"}


def _y_campos(lineas):
    """Altura del primer campo A / PARA / DE: el título va más arriba."""
    ys = [_yc(l) for l in lineas if _yc(l) < 0.6 and l.bbox[0] < 0.45 and
          (_ETIQUETA_RE.match((l.text or "").strip()) and
           _clave_campo(_ETIQUETA_RE.match((l.text or "").strip()).group("et")) in ("a", "de"))]
    return min(ys) if ys else None


_NUM_CAJA_RE = re.compile(r"^\s*[\[|(]?\s*([0-9OoIl]{4,10})\s*[\]|)]?\s*$")


_CLAVES_CLASE = ["INFORME", "MEMORANDO", "MEMORANDUM", "OFICIO", "PROVEIDO", "CARTA", "SOLICITUD",
                 "RESOLUCION", "CONFORMIDAD"]


def _arregla_clase(txt):
    """«ME MORANDO N°…» -> «MEMORANDO N°…»; «INFORNE N°…» -> «INFORME N°…»."""
    m = re.match(r"^\s*((?:[A-Za-zÁÉÍÓÚÑ0]{1,12}\s?){1,3}?)(?=\s*N\s*[°º'\"*oO]|\s*N\s*\d|\s*NRO)", txt)
    if not m:
        return txt
    cab = _compacto(m.group(1).replace("0", "O"))
    for c in _CLAVES_CLASE:
        if cab == c:
            return c + txt[m.end():]
        if len(cab) == len(c) and sum(a != b for a, b in zip(cab, c)) <= 1 or _parecido(cab, c) >= 0.86:
            return c + txt[m.end():]
    return txt


def _renglones(lineas):
    """Une en un renglón los trozos que el OCR partió a la misma altura
    («MEMORANDO N°» | «-2026-MPC-OGAF-OLG»)."""
    ls = sorted(lineas, key=lambda l: (round(_yc(l), 3), l.bbox[0]))
    filas = []
    for l in ls:
        if filas and abs(_yc(filas[-1][-1]) - _yc(l)) < 0.007 and l.bbox[0] > filas[-1][-1].bbox[0]:
            filas[-1].append(l)
        else:
            filas.append([l])
    out = []
    for f in filas:
        if len(f) == 1:
            out.append(f[0])
            continue
        f.sort(key=lambda l: l.bbox[0])
        out.append(OCRLine(text=" ".join(x.text for x in f), conf=min(x.conf for x in f),
                           bbox=(f[0].bbox[0], min(x.bbox[1] for x in f), f[-1].bbox[2], max(x.bbox[3] for x in f)),
                           page=f[0].page, words=[w for x in f for w in x.words]))
    return out


def buscar_titulo(lineas, siglas, zona=0.55, tipo=None):
    """El mejor título numerado en la parte de arriba de una hoja."""
    mejor = None
    tope = _y_campos(lineas)
    originales = lineas
    lineas = _renglones([l for l in lineas if _yc(l) <= zona])
    for l in lineas:
        if _yc(l) > zona or (tope is not None and _yc(l) > tope + 0.004):
            continue
        # sin el sello de folio que a veces se pega a la derecha del título
        txt = _arregla_clase(l.text or "")
        for m in _NUM_RE.finditer(txt):
            antes = txt[:m.start()].strip()
            if m.start() > 0 and re.search(r"(AL|EL|LA|DEL|SEG[UÚ]N|MEDIANTE|CON|REF[.:]?|REFERENCIA|[a-e]\))\s*[:.]?\s*$",
                                          antes, re.I):
                continue      # «…a la Orden de Servicio N°…» es una cita, no el título
            clase = _clase_canonica(re.sub(r"\s+", " ", m.group("clase")))
            if tipo and not _clase_admitida(clase, tipo):
                continue
            if not (m.group("num") or m.group("anio")) and not m.group("basura"):
                # el número de la orden / pedido va en un recuadro aparte, a la misma altura
                caja = next((o for o in originales if o is not l and abs(_yc(o) - _yc(l)) < 0.012
                             and o.bbox[0] >= l.bbox[0] and _NUM_CAJA_RE.match(o.text or "")), None)
                if not caja:
                    continue
                txt2 = txt[:m.end()] + " " + _NUM_CAJA_RE.match(caja.text).group(1)
                m = _NUM_RE.search(txt2, m.start())
                if not m or not m.group("num"):
                    continue
            r = _lee_nomenclatura(m, siglas)
            # un título va arriba y en su propio renglón
            r["confianza"] = round(r["confianza"] * (1.0 if m.start() < 25 else 0.85), 2)
            r["y"] = _yc(l)
            if not mejor or r["confianza"] > mejor["confianza"] + 0.05 or (
                    abs(r["confianza"] - mejor["confianza"]) <= 0.05 and r["y"] < mejor["y"]):
                mejor = r
    return mejor


def citas_del_expediente(doc, siglas):
    """Todas las nomenclaturas citadas en el cuerpo de los documentos
    (REFERENCIA, «mediante el Memorando N°…»): sirven para confirmar números
    que en su propio documento están escritos a mano."""
    out = []
    for pg in doc.pages:
        for l in pg.lines:
            for m in _NUM_RE.finditer(l.text or ""):
                if not m.group("num") or not m.group("anio"):
                    continue
                r = _lee_nomenclatura(m, siglas)
                if r["numero"] and r["anio"] and r["siglas"]:
                    r["pagina"] = pg.number
                    out.append(r)
    return out


def _confirma_con_citas(t, citas, pagina_propia, ya_usados=()):
    """Confirma o completa el número del título con una cita escrita a
    máquina en otro documento (misma clase, año y siglas).

    - Si el número se leyó igual en la cita: queda «confirmado».
    - Si se leyó incompleto («280» y la cita dice «2809»): se completa.
    - Si en el documento el número está ILEGIBLE (garabatos), se toma el de
      la única cita que calce y que no sea ya el número de otro documento.
    - Si el número está EN BLANCO (el memorando aún no se numeró) no se
      inventa ninguno."""
    if not t or not t.get("anio"):
        return t
    propias = set(t["siglas"])
    primera = lambda c: _sin_tildes(c).split()[0]
    candidatos = []
    for c in citas:
        if c["pagina"] == pagina_propia or c["anio"] != t["anio"]:
            continue
        if primera(c["clase"]) != primera(t["clase"]):
            continue
        # las siglas propias deben estar todas en la cita (el OCR puede
        # haberse comido la última: «…-OGAF-OL»)
        if not propias or not propias <= set(c["siglas"]) or len(propias) < min(2, len(c["siglas"])):
            continue
        n0, n1 = t["numero"].lstrip("0"), c["numero"].lstrip("0")
        if n0:
            if n0 == n1:
                candidatos.append((1.0, c))
            elif len(n1) >= len(n0) and (n1.startswith(n0) or _parecido(n0, n1) >= 0.75):
                candidatos.append((_parecido(n0, n1), c))
        elif t.get("ilegible") and n1 not in ya_usados:
            candidatos.append((0.8, c))
    if not candidatos:
        return t
    if not t["numero"] and len({c["numero"].lstrip("0") for _, c in candidatos}) > 1:
        return t                     # más de una cita posible: no se adivina
    r, c = max(candidatos, key=lambda x: x[0])
    t = dict(t)
    leido = t["titulo"]
    mismo = t["numero"] and c["numero"].lstrip("0") == t["numero"].lstrip("0")
    numero = t["numero"] if mismo else (c["numero"] if len(c["numero"]) >= len(t["numero"]) else t["numero"])
    # siglas: las de la cita si la propia lectura perdió alguna, con los
    # separadores de la propia hoja
    siglas_c, seps = list(t["siglas"]), list(t["seps"])
    if len(c["siglas"]) > len(siglas_c):
        faltan = c["siglas"][len(siglas_c):]
        siglas_c += faltan
        seps += [seps[-1] if seps else "-"] * len(faltan)
    t.update(numero=numero, siglas=siglas_c, seps=seps, ilegible=False)
    t["titulo"] = _arma(t["clase"], numero, t["anio"], t.get("sal", []), siglas_c, seps)
    if mismo and t["titulo"] == leido:
        t["confirmado"] = f"coincide con la cita de la pág. {c['pagina']}"
        t["confianza"] = max(t["confianza"], 0.97)
    else:
        t["confirmado"] = (f"completado con la cita de la pág. {c['pagina']} "
                           f"(en la hoja se leyó «{leido}»)")
        t["confianza"] = max(t["confianza"], 0.9)
    return t


# ─────────────────────────────────────── títulos sin número (TDR, correos…)

_RUIDO_TITULO = re.compile(r"MUNICIPALIDAD|CALLAO|FOLIO|GERENCIA DE ADM|OFICINA LOG|^ANO DE|^AÑO DE", re.I)


def _es_ruido(l):
    """Membrete, sello de folio o frase del año: no son el título."""
    n = _norm(l.text)
    if not n or _RUIDO_TITULO.search(n) or _RUIDO_TITULO.search(l.text or ""):
        return True
    if l.bbox[0] > 0.6 and _yc(l) < 0.16:          # esquina del sello de folio
        return True
    return False


def _titulo_libre(pg, seg):
    """Documentos que no llevan «N°»: se arma el nombre con lo que dicen."""
    lineas = [l for l in _renglones(pg.lines)]
    textos = [_limpia(l.text) for l in lineas]
    comp = [_compacto(t) for t in textos]
    if seg.tipo == "tdr":
        base = "TÉRMINOS DE REFERENCIA"
        if any("ESPECIFICACIONESTECNICAS" in c for c in comp[:25]) and not any("TERMINOSDEREFERENCIA" in c for c in comp[:25]):
            base = "ESPECIFICACIONES TÉCNICAS"
        for i, c in enumerate(comp):
            if "DENOMINACI" in c and "CONTRATAC" in c or "OBJETODELACONTRATACI" in c:
                resto = textos[i].split(":", 1)[1] if ":" in textos[i] else ""
                trozos = [resto] if len(_norm(resto)) > 8 else []
                for t in textos[i + 1:i + 4]:
                    if re.match(r"^\s*\d+\s*[.)]", t) or len(_norm(t)) < 4:
                        break
                    trozos.append(t)
                den = _limpia(" ".join(trozos))
                if den:
                    return f"{base} — {den.upper()}"
        return base
    # anexos: «ANEXO01», «ANEX04», «ANEXO N° 2»
    for t in textos[:12]:
        m = re.match(r"^\s*ANEX[O0]?\s*N?[°º]?\s*([0-9OIl]{1,2}[0-9OIl]?)\s*[.:-]?\s*(.*)$", t, re.I)
        if m:
            n = _digitos(m.group(1))[-2:].zfill(2)
            resto = _limpia(m.group(2))
            return f"ANEXO {n}" + (f" — {resto.upper()}" if len(resto) > 4 else "")
    if seg.tipo == "validez_cpe":
        for t in textos[:15]:
            if re.search(r"es un comprobante", t, re.I) or re.search(r"(no\s+)?es\s+v[aá]lid", t, re.I):
                return "CONSULTA DE VALIDEZ DEL COMPROBANTE DE PAGO ELECTRÓNICO — " + _limpia(t)
        return "CONSULTA DE VALIDEZ DEL COMPROBANTE DE PAGO ELECTRÓNICO"
    if seg.tipo == "solicitud_cotizacion" or any(c.startswith("GMAIL") for c in comp[:4]):
        asunto = remitente = fecha = ""
        for l, t in zip(lineas[:14], textos[:14]):
            if _es_ruido(l) or re.search(r"@|GMAIL|<", t, re.I):
                continue
            if not asunto and len(re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", t)) >= 2 and len(t) <= 90:
                asunto = t
        for t in textos[:16]:
            m = re.match(r"(.+?)\s*<[^>]+>\s*(.*)$", t)
            if m and re.search(r"\d{4}", m.group(2)):
                remitente, fecha = _limpia(m.group(1)), _limpia(m.group(2))
                break
        if asunto:
            s = f"CORREO: «{asunto}»"
            if remitente:
                s += f" — de {remitente}"
            if fecha:
                s += f", {fecha}"
            return s
    # informe del proveedor, cartas sin número: las primeras líneas en
    # mayúsculas bajo el membrete
    titulo = []
    for l, t in zip(lineas[:22], textos[:22]):
        if _es_ruido(l):
            if titulo:
                break
            continue
        letras = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ]", "", t)
        if len(letras) >= 6 and sum(ch.isupper() for ch in letras) / len(letras) > 0.85 and len(t) <= 70 \
                and len(re.findall(r"[A-Za-zÁÉÍÓÚÑ]{3,}", t)) >= 2:
            titulo.append(t.upper())
            if len(titulo) == 2:
                break
        elif titulo:
            break
    if titulo:
        s = _arregla_clase(" ".join(titulo) + " N ").rstrip(" N") if False else " ".join(titulo)
        s = re.sub(r"^INF\s*ORME\b", "INFORME", s)
        s = re.sub(r"^MEMO\s*RANDO\b", "MEMORANDO", s)
        for t in textos[:25]:
            m = re.search(r"ORDEN\s+DE\s+SERVICIO\s*N\D{0,4}([0-9][0-9\-\s]{4,16}[0-9])", t, re.I)
            if m and "ORDEN DE SERVICIO" not in s:
                numero_os = re.sub(r"\s+", "", m.group(1))
                s += f" (O/S N° {numero_os})"
                break
        return s
    return ""


def _factura(pg):
    txt = "\n".join(l.text for l in pg.lines)
    t = _sin_tildes(txt).upper()
    clase = "FACTURA ELECTRÓNICA" if "FACTURA" in t else ("RECIBO POR HONORARIOS ELECTRÓNICO" if "HONORARIO" in t else "BOLETA DE VENTA")
    serie = re.search(r"\b([EFB][0O0-9]{2,3}\s*[-–]\s*\d{1,8})\b", t)
    ruc = re.search(r"RUC\s*[:.]?\s*(\d{11})", t)
    s = clase
    if serie:
        s += " " + re.sub(r"[\s–]", "", serie.group(1)).replace("O", "0")
    if ruc:
        s += f" — RUC {ruc.group(1)}"
    return s


# ────────────────────────────────────────── campos A / DE / ASUNTO / …

_CAMPOS = [("para", r"PARA"), ("a", r"A"), ("de", r"DE"), ("asunto", r"ASUNTO"),
           ("referencia", r"REFERENCIA|REF\.?"), ("fecha", r"FECHA")]
_ETIQUETA_RE = re.compile(r"^[\s|!¡'\"`.,;_?¿]*(?P<et>" + "|".join(p for _, p in _CAMPOS) + r"|[?¿]?EFERENCIA|R\S?FERENCIA|ASUNT[O0]|FECH[A4])\s*(?:[:;.'´]|\s{2,}|\s(?=:)|(?<=[A-Z]{5})\s[E:;,'´](?=\s)|$)\s*(?P<resto>.*)$", re.I)
_TRATOS = r"(?:ABOG\.?|ABG\.?|SR\.?|SRA\.?|SRTA\.?|LIC\.?|LIC\.?\s*ADM\.?|ING\.?|CPC\.?|C\.P\.C\.?|DR\.?|DRA\.?|ECON\.?|ARQ\.?|MG\.?|MAG\.?|PROF\.?|BACH\.?|TEC\.?)"
_TRATO_RE = re.compile(r"^\s*(" + _TRATOS + r")[,.]?\s+", re.I)
_ORDEN = ["a", "de", "asunto", "referencia", "fecha"]


def _clave_campo(et):
    et = _norm(_sin_tildes(et))
    if len(et) >= 5:
        for clave, largo in (("referencia", "REFERENCIA"), ("asunto", "ASUNTO"), ("fecha", "FECHA")):
            if _parecido(et, largo) >= 0.8:
                return clave
    for clave, pat in _CAMPOS:
        if re.fullmatch(pat.replace("\\.", ""), et):
            return "a" if clave == "para" else clave
    return None


def _persona(lineas_valor):
    if not lineas_valor:
        return None
    nombre = _limpia(lineas_valor[0])
    trato = ""
    m = _TRATO_RE.match(nombre)
    if m:
        trato = m.group(1).upper().rstrip(".") + "."
        nombre = nombre[m.end():]
    cargo = _limpia(lineas_valor[1]) if len(lineas_valor) > 1 else ""
    if re.match(r"^\W*(ASUNTO|REFERENCIA|FECHA|PARA)\b", _sin_tildes(cargo), re.I):
        cargo = ""
    mc = re.search(r"\b(Sub\s*Gerente|Gerente|Jef[ae]|Subgerencia|Gerencia|Oficina|Coordinador|Director|"
                   r"Especialista|Asistente|Encargad|Responsable|Alcalde|Contador|Tesorer|Secretari)", cargo, re.I)
    if mc:
        cargo = cargo[mc.start():]
    nombre = re.sub(r"[.,;:]+(?=\s|$)", "", nombre)
    if not _parece_nombre(nombre):
        return None
    if cargo and (re.search(r"\d{3}|N[°º*]", cargo) or len(cargo) > 90):
        cargo = ""
    return {"trato": trato.replace(",", "."), "nombre": _limpia(nombre).upper(), "cargo": cargo}


_NO_NOMBRE = re.compile(r"OFICINA|GERENCIA|MUNICIPALIDAD|INFORME|MEMORANDO|PROGRAMA|CALLAO|FOLIO|HORA|"
                        r"BIENES|MENORES|CONTRATOS|SERVICIOS|COORDINADOR|EXPEDIENTE|PROVEIDO|DIRECTIVA|"
                        r"FIRMA|FECHA|RECIBID|PROVEEDOR|RESPONSAB|SERVICIO|JR\b|AV\b|CALLE|PASAJE|N[°º]|"
                        r"ORDEN|CONFORMIDAD|DENOMINACI|OBLIGACI|ADQUISICI|REG\b", re.I)


def _parece_nombre(t):
    """¿Es el nombre de una persona? 2 a 6 palabras de letras, sin palabras
    de oficina, sello ni dirección."""
    t = _TRATO_RE.sub("", t or "")
    pal = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+", t)
    if not 2 <= len(pal) <= 6 or re.search(r"\d", t):
        return False
    if _NO_NOMBRE.search(_sin_tildes(t)):
        return False
    return sum(len(p) >= 3 for p in pal) >= 2


_MESES = {"ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7,
          "AGOSTO": 8, "SETIEMBRE": 9, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12}
_MES_CORTO = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AGO": 8,
              "SET": 9, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}


def fechas_en(texto, anio_defecto=""):
    """Todas las fechas que se pueden leer en un texto (ISO), en orden."""
    t = _sin_tildes(texto or "").upper().replace("£", "E").replace("€", "E").replace("$", "S")
    t = re.sub(r"\b[DO](\d)\b", r"0\1", t)
    t = re.sub(r"\b(\d)\s?[.,]\s?(\d)(?=\s*(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SET|SEP|OCT|NOV|DIC))", r"\1\2", t)
    out = []
    for m in re.finditer(r"(\d{1,2})\s*(?:DE\s+)?([A-Z]{4,10})\s+(?:DEL?\s+)?(20\d\d)", t):
        mes = next((v for k, v in _MESES.items() if _parecido(m.group(2), k) >= 0.8), None)
        if mes and 1 <= int(m.group(1)) <= 31:
            out.append(f"{m.group(3)}-{mes:02d}-{int(m.group(1)):02d}")
    for m in re.finditer(r"\b(\d{1,2})\s*[-./ ,]?\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SET|SEP|OCT|NOV|DIC)[A-Z]*\.?,?\s*[-./ ]?\s*(20\d\d|\d{2})\b", t):
        anio = m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3)
        if 1 <= int(m.group(1)) <= 31:
            out.append(f"{anio}-{_MES_CORTO[m.group(2)]:02d}-{int(m.group(1)):02d}")
    if not out and anio_defecto:
        # «03 SEP» sin año (el sello lo dejó ilegible): el año del documento
        for m in re.finditer(r"\b(\d{1,2})\s*[-./ ,]?\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SET|SEP|OCT|NOV|DIC)\b", t):
            if 1 <= int(m.group(1)) <= 31:
                out.append(f"{anio_defecto}-{_MES_CORTO[m.group(2)]:02d}-{int(m.group(1)):02d}")
    for m in re.finditer(r"\b(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(20\d\d|\d{2})\b", t):
        if 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(1)) <= 31:
            anio = m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3)
            out.append(f"{anio}-{int(m.group(2)):02d}-{int(m.group(1)):02d}")
    return out


def fecha_de(texto):
    """«Callao, 23 de abril del 2026» / «23 ABR 2026» / «23.04.26» -> (ISO, legible)."""
    t = _sin_tildes(texto or "").upper()
    m = re.search(r"(\d{1,2})\s*(?:DE\s+)?([A-Z]{4,10})\s+(?:DEL?\s+)?(20\d\d)", t)
    if m:
        mes = next((v for k, v in _MESES.items() if _parecido(m.group(2), k) >= 0.8), None)
        if mes:
            return f"{m.group(3)}-{mes:02d}-{int(m.group(1)):02d}"
    m = re.search(r"\b(\d{1,2})\s*[-./ ]?\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SET|SEP|OCT|NOV|DIC)[A-Z]*\.?\s*[-./ ]?\s*(20\d\d|\d{2})\b", t)
    if m:
        anio = m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3)
        return f"{anio}-{_MES_CORTO[m.group(2)]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"\b(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(20\d\d|\d{2})\b", t)
    if m and 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(1)) <= 31:
        anio = m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3)
        return f"{anio}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return ""


def leer_campos(lineas, arriba=0.7):
    """Los campos del oficio con su valor (la persona y su cargo en A y DE).

    Funciona con las dos formas en que llegan los renglones: etiqueta y valor
    en el mismo renglón («A : ABOG. SERGIO…») o en columnas separadas (la
    etiqueta a la izquierda y el valor a la misma altura). Si un sello tapó
    una etiqueta, el renglón que empieza con «:» toma la que sigue en el
    orden de siempre (A → DE → ASUNTO → REFERENCIA → FECHA)."""
    ls = sorted([l for l in lineas if _yc(l) <= arriba and (l.text or "").strip()],
                key=lambda l: (round(_yc(l), 3), l.bbox[0]))
    etiquetas = []      # (clave, y, x_valor, texto_en_línea)
    usados = set()
    for i, l in enumerate(ls):
        t = (l.text or "").strip()
        m = _ETIQUETA_RE.match(t)
        clave = _clave_campo(m.group("et")) if m else None
        if clave and l.bbox[0] < 0.45:
            etiquetas.append((clave, _yc(l), l.bbox[0], m.group("resto").strip(), i))
            usados.add(i)
            continue
        if re.fullmatch(r"[\s:;.|]*", t):
            usados.add(i)          # los «:» sueltos de una columna aparte
            continue
        # «: Sr. CESAR…» o «A A 0 : Sr. CESAR…»: el sello tapó la etiqueta
        mm = re.match(r"^([^:]{0,12}):\s*(.{4,})$", t)
        if mm and l.bbox[0] < 0.35 and len(re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{5,}", mm.group(1))) == 0:
            etiquetas.append((None, _yc(l), l.bbox[0], mm.group(2).strip(), i))
            usados.add(i)
    # al menos una etiqueta a la vista y otro campo (con etiqueta o tapado)
    if not [e for e in etiquetas if e[0]] or len(etiquetas) < 2:
        return {}
    # etiquetas tapadas: toman la siguiente del orden
    vistas = []
    arregladas = []
    for clave, y, x, resto, i in etiquetas:
        if clave is None:
            # la etiqueta se deduce por el orden de siempre… y por lo que dice
            prev = vistas[-1] if vistas else None
            idx = _ORDEN.index(prev) + 1 if prev in _ORDEN else 0
            clave = _ORDEN[idx] if idx < len(_ORDEN) else None
            if fecha_de(resto) and "fecha" not in vistas:
                clave = "fecha"
            elif clave in ("a", "de") and not _parece_nombre(_TRATO_RE.sub("", resto)[:60]):
                clave = "asunto" if "asunto" not in vistas else None
            elif clave == "referencia" and not re.search(r"N\s*[°º*]|\d{3}", resto):
                clave = None
            if clave is None:
                continue
        if clave in vistas:
            continue
        vistas.append(clave)
        arregladas.append((clave, y, x, resto, i))
    campos = {}
    for k, (clave, y, x, resto, i) in enumerate(arregladas):
        y_sig = arregladas[k + 1][1] if k + 1 < len(arregladas) else y + 0.08
        valor = [resto.lstrip(":; ").strip()] if resto.lstrip(":; ").strip() else []
        for j, l in enumerate(ls):
            if j in usados or j == i:
                continue
            yc = _yc(l)
            if y - 0.008 <= yc < y_sig - 0.006 and l.bbox[0] > x + 0.01:
                txt = (l.text or "").strip().lstrip(":; ").strip()
                if txt and not _ETIQUETA_RE.match(txt):
                    valor.append(txt)
                    usados.add(j)
        valor = [v for v in valor if re.search(r"[A-Za-z0-9]{2}", v)]
        if not valor:
            continue
        if clave in ("a", "de"):
            p = _persona(valor)
            if p:
                campos[clave] = p
        elif clave == "fecha":
            # hasta el año: lo que sigue suele ser un sello pegado
            m_f = re.match(r"^(.*?\b20\d\d)\b", valor[0])
            campos["fecha"] = _limpia(m_f.group(1) if m_f else valor[0])
            iso = fecha_de(valor[0])
            if iso:
                campos["fecha_iso"] = iso
        elif clave == "referencia":
            campos["referencia"] = [_limpia(v) for v in valor[:4]]
        else:
            campos[clave] = _limpia(" ".join(valor[:3]))
    return campos


# ─────────────────────────────────────────────────────────── firmas

_CARGO_RE = re.compile(
    r"\b(SUB\s*GERENTE|GERENTE(?:\s+MUNICIPAL|\s+GENERAL)?|JEF[AE](?:\s+DE\s+[A-ZÁÉÍÓÚÑ ]{3,40})?|"
    r"COORDINADOR[A]?|DIRECTOR[A]?|ALCALDE(?:SA)?|ESPECIALISTA|ASISTENTE|ENCARGAD[OA]|"
    r"RESPONSABLE(?:\s+DE\s+[A-ZÁÉÍÓÚÑ ]{3,40})?|SECRETARI[OA]|COMPRADOR[A]?|ASESOR[A]?|"
    r"ADMINISTRADOR[A]?|CONTADOR[A]?|TESORER[OA]|ANALISTA|T[EÉ]CNICO|AUXILIAR|PROCURADOR[A]?)\b",
    re.I)
_ENTIDAD_RE = re.compile(r"MUNICIPALIDAD|PROVINCIAL|DEL CALLAO", re.I)


def _palabras_nombre(t):
    return [p for p in _norm(_TRATO_RE.sub("", t or "")).split() if len(p) >= 2 and p not in _NO_CUENTAN]


def _encuentra_persona(texto_zona, personas):
    """¿Qué persona conocida firma en esta zona? El nombre sale roto porque
    la firma lo cruza («CESAR ALTK XDER TA RAZ GA HERNANDEZ»): se buscan sus
    palabras una por una; los dos APELLIDOS pesan más que los nombres."""
    zona_pal = _norm(texto_zona).split()
    zona_comp = _compacto(texto_zona)
    mejor, puntaje = None, 0.0
    for p in personas:
        pal = _palabras_nombre(p["nombre"])
        if len(pal) < 2:
            continue

        usadas = set()

        def esta(w):
            libres = [(k, z) for k, z in enumerate(zona_pal) if k not in usadas]
            for k, z in libres:
                if z == w:
                    usadas.add(k)
                    return 1.0
            if len(w) <= 5:
                return 0.0           # «DÍAZ» no es «DÍAS»: una palabra corta debe calzar entera
            mejor_k, mejor = None, 0.0
            for k, z in libres:
                if abs(len(z) - len(w)) <= 2 and len(z) >= 4:
                    x = _parecido(w, z)
                    if x > mejor:
                        mejor_k, mejor = k, x
            if mejor >= 0.8:
                usadas.add(mejor_k)
                return mejor
            # la palabra partida en dos por la firma: «TARAZO» + «NA»
            if len(w) >= 6 and w in zona_comp:
                return 0.95
            return 0.0

        notas = [esta(w) for w in pal]
        halladas = sum(1 for x in notas if x >= 0.8)
        r = halladas / len(pal)
        # nombres peruanos: los dos últimos son los apellidos
        apellidos = [x >= 0.8 for x in notas[-2:]] if len(pal) >= 3 else [x >= 0.8 for x in notas]
        if all(apellidos):
            r = max(r, 0.85)
        elif any(apellidos) and halladas >= 2:
            r = max(r, 0.7)
        if r > puntaje:
            mejor, puntaje = p, r
    if mejor and puntaje >= 0.7:
        return mejor, round(puntaje, 2)
    return None, 0.0


_PALABRAS_SELLO = re.compile(r"HORA|FIRMA|FOLIO|FECHA|RECIBID|REG\b|RECEPCI|PROVEID|PASE", re.I)


def leer_firmas(paginas, personas, oficinas):
    """Firmas del documento: el sello de firma (entidad / oficina / nombre /
    cargo) o el pie de firma escrito (nombre, cargo, DNI)."""
    firmas = []
    for pg, lineas in paginas:
        # solo renglones cortos de la mitad de abajo: un bloque de firma no
        # es un párrafo del cuerpo
        abajo = sorted([l for l in lineas if _yc(l) >= 0.45 and 2 <= len((l.text or "").strip()) <= 60],
                       key=lambda l: (round(_yc(l), 3), l.bbox[0]))
        if not abajo:
            continue
        grupos = []
        for l in abajo:
            for g in grupos:
                if any(abs(_yc(l) - _yc(o)) < 0.035 and (l.bbox[0] < o.bbox[2] + 0.06 and o.bbox[0] < l.bbox[2] + 0.06)
                       for o in g):
                    g.append(l)
                    break
            else:
                grupos.append([l])
        for g in grupos:
            g.sort(key=lambda l: (_yc(l), l.bbox[0]))
            texto = " ".join(l.text for l in g)
            persona, conf = _encuentra_persona(texto, personas)
            nombre, dni = "", None
            if persona:
                nombre = _TRATO_RE.sub("", persona["nombre"]).strip()
            else:
                # pie de firma escrito: el nombre y, justo debajo, el DNI
                for k, l in enumerate(g):
                    t = (l.text or "").strip()
                    if _parece_nombre(t) and not _PALABRAS_SELLO.search(t):
                        debajo = [o for o in g[k + 1:] if 0 < _yc(o) - _yc(l) < 0.035]
                        d = next((re.search(r"\b(\d{8})\b", o.text) for o in debajo if re.search(r"\b\d{8}\b", o.text)), None)
                        if d:
                            nombre, dni = _limpia(t).upper(), d.group(1)
                            break
            if not nombre:
                continue
            if not dni:
                d = re.search(r"\bD\.?N\.?I\.?\s*[:N°º]*\s*(\d{8})\b|\b(\d{8})\b", texto)
                if d:
                    dni = d.group(1) or d.group(2)
            cargo = ""
            for l in g:
                t = _sin_tildes(l.text).upper()
                cm = _CARGO_RE.search(t)
                if cm and len(t) <= 45 and not re.search(r"RESPONSABLE\s+DE\s+(BRINDAR|LA\s+DOC)", t):
                    cargo = _titulo_propio(re.sub(r"\s+", " ", cm.group(0)).replace("SUB GERENTE", "SUBGERENTE"))
                    break
            pc = (persona or {}).get("cargo", "")
            if pc and (not cargo or _norm(pc.replace("Sub ", "Sub")).split()[:1] == _norm(cargo.replace("Sub ", "Sub")).split()[:1]):
                cargo = pc if len(pc) > len(cargo) else cargo
            ofis = oficinas_en(texto, oficinas)
            f = {"pagina": pg, "nombre": nombre, "cargo": cargo, "oficina": ofis[0] if ofis else "",
                 "como": "sello de firma" if (ofis or _ENTIDAD_RE.search(texto)) else "pie de firma",
                 "confianza": conf if persona else 0.8}
            if dni:
                f["dni"] = dni
            if persona and conf < 1.0:
                f["nota"] = "nombre reconocido aunque la firma lo cruza"
            if not any(_norm(x["nombre"]) == _norm(f["nombre"]) and x["pagina"] == pg for x in firmas):
                firmas.append(f)
    return firmas


def _oficina_conocida(texto, oficinas):
    """El nombre bien escrito de la oficina que el OCR leyó a medias
    («Gerencia de Adminis lración» -> «Gerencia de Administración»)."""
    halladas = oficinas_en(texto, oficinas)
    if halladas:
        return halladas[0]
    return ""


_TILDE_OFICINA = {"LOGISTICA": "Logística", "ADMINISTRACION": "Administración", "MODERNIZACION": "Modernización",
                  "TESORERIA": "Tesorería", "ASESORIA": "Asesoría", "JURIDICA": "Jurídica",
                  "SECRETARIA": "Secretaría", "ALCALDIA": "Alcaldía", "ORGANO": "Órgano"}


def _bonita(oficina):
    return " ".join(_TILDE_OFICINA.get(w, w.capitalize() if w not in _NO_CUENTAN else w.lower())
                    for w in oficina.split()).replace("Planeamiento Modernización", "Planeamiento, Modernización")


def oficinas_en(texto, oficinas, umbral=0.8):
    """Oficinas conocidas que aparecen en un texto con errores de OCR, en
    el orden en que aparecen."""
    comp = _compacto(texto)
    out = []
    for o in sorted(oficinas, key=len, reverse=True):
        oc = _compacto(o)
        if len(oc) < 8 or len(comp) < len(oc) - 3:
            continue
        umbral_o = umbral - 0.06 if len(oc) >= 25 else umbral
        mejor, pos = 0.0, -1
        i = comp.find(oc)
        if i >= 0:
            mejor, pos = 1.0, i
        else:
            sm = SequenceMatcher(autojunk=False)
            sm.set_seq2(oc)
            for k in range(0, max(1, len(comp) - len(oc) + 4)):
                sm.set_seq1(comp[k:k + len(oc) + 2])
                if sm.real_quick_ratio() < umbral_o or sm.quick_ratio() < umbral_o:
                    continue
                x = sm.ratio()
                if x > mejor:
                    mejor, pos = x, k
        if mejor >= umbral_o and not any(abs(pos - p) < 6 for p, _ in out):
            out.append((pos, _bonita(o)))
    return [o for _, o in sorted(out)]


# ─────────────────────────────────────────────────────────── sellos

_SELLO_CLAVES = re.compile(r"REC[EA]PCI|RECIBID|FOLIO|PROVEID|PASE\s*A|HORA|\bREG\b|V\s*[°º]?\s*B\s*[°º]|DOCUM\w*\s+NO\b|"
                           r"NO\s+SIGNIFICA|ACEPTACI", re.I)


def _tipo_sello(t):
    u = _sin_tildes(t).upper()
    if re.search(r"RECIB|RE\s?CI\s?B|RECEP", u):
        return "recepción"
    if re.search(r"PROVEID|PROVE\W?IO|PROVE:|PASE\s*A|ATENDER\s*LO|TRAMITE\s*CORRESP", u):
        return "proveído"
    if re.search(r"RECEPCI|NO\s+SIGNIFICA|ACEPTACI|RECIBID", u):
        return "recepción"
    if re.search(r"V\s*[°º0O]?\s*B\s*[°º0O]", u):
        return "visto bueno"
    if "FOLIO" in u:
        return "folio"
    return "sello"


def parsear_sello(texto, oficinas, fecha_doc="", bbox=None):
    """Datos de un sello a partir de una o más lecturas de su texto
    (separadas por « // »)."""
    u = _sin_tildes(texto).upper()
    lecturas = [x for x in texto.split(" // ") if x.strip()]
    mejor = max(lecturas, key=lambda x: len(re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}", x))) if lecturas else texto
    s = {"tipo": _tipo_sello(texto), "texto": _limpia(re.sub(r"\s*/\s*", " / ", mejor))[:220]}
    if s["tipo"] in ("folio", "sello") and fechas_en(texto, (fecha_doc or "")[:4]) and (
            re.search(r"HORA|FIRMA|REG", u) or not (bbox and bbox[1] < 0.13 and bbox[0] > 0.6)):
        s["tipo"] = "recepción"
    if "MUNICIPALIDAD" in u or "CALLAO" in u:
        s["entidad"] = "Municipalidad Provincial del Callao"
    ofis = oficinas_en(texto, oficinas)
    if ofis:
        s["oficina"] = ofis[0]
        if len(ofis) > 1:
            s["oficinas"] = ofis
    # la fecha de un sello de recepción no puede ser anterior a la del documento
    fechas = fechas_en(texto, (fecha_doc or "")[:4])
    if fechas:
        if fecha_doc:
            # un sello va el mismo día o después del documento, y no años después:
            # un año imposible («2028» por «2026») se toma del documento
            from datetime import date
            def dia(f):
                try:
                    return date.fromisoformat(f)
                except ValueError:
                    return None
            d0 = dia(fecha_doc)
            validas = []
            for f in fechas:
                d = dia(f)
                if d and d0 and 0 <= (d - d0).days <= 400:
                    validas.append(f)
                elif d and d0 and d.year != d0.year:
                    f2 = f"{d0.year}{f[4:]}"
                    d2 = dia(f2)
                    if d2 and 0 <= (d2 - d0).days <= 400:
                        validas.append(f2)
            if validas:
                s["fecha"] = sorted(validas)[0]
        else:
            s["fecha"] = max(set(fechas), key=fechas.count)
    h = re.search(r"HORA\s*[:.]?\s*(\d{1,2})\s*[:.,]\s*(\d{2})", u)
    if h and int(h.group(1)) < 24 and int(h.group(2)) < 60:
        s["hora"] = f"{int(h.group(1)):02d}:{h.group(2)}"
    n = re.search(r"(?:PROVEIDO|REG(?:ISTRO)?|EXP(?:EDIENTE)?)\s*N?\D{0,4}(\d{3,7})", u)
    if n:
        s["numero"] = n.group(1)
    return s


def leer_sellos_de_lineas(lineas, oficinas, fecha_doc=""):
    """Sellos reconocidos en los renglones (sirve con cualquier lector):
    grupos de renglones cercanos que llevan palabras de sello."""
    ls = [l for l in lineas if (l.text or "").strip()]
    grupos = []
    for l in ls:
        for g in grupos:
            if any(abs(_yc(l) - _yc(o)) < 0.05 and (l.bbox[0] < o.bbox[2] + 0.05 and o.bbox[0] < l.bbox[2] + 0.05)
                   for o in g):
                g.append(l)
                break
        else:
            grupos.append([l])
    out = []
    for g in grupos:
        texto = " / ".join(l.text for l in sorted(g, key=lambda l: (_yc(l), l.bbox[0])))
        if not _SELLO_CLAVES.search(_sin_tildes(texto)):
            continue
        ancho = max(l.bbox[2] for l in g) - min(l.bbox[0] for l in g)
        if ancho > 0.6:       # un renglón del cuerpo que dice «recepción»
            continue
        s = parsear_sello(texto, oficinas, fecha_doc)
        s["bbox"] = (round(min(l.bbox[0] for l in g), 3), round(min(l.bbox[1] for l in g), 3),
                     round(max(l.bbox[2] for l in g), 3), round(max(l.bbox[3] for l in g), 3))
        out.append(s)
    return out


# ───────────────────────────────────────── lectura enfocada (Tesseract)

def _tesseract_ok():
    try:
        from .. import os_engine
        return os_engine.is_ocr_available()
    except Exception:
        return False


def _imagen(page, dpi=300, gris=True):
    import pymupdf
    from PIL import Image
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY if gris else pymupdf.csRGB)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def _lineas_tesseract(img, numero, recorte=(0.0, 0.0, 1.0, 1.0), psm=6):
    """Renglones con posición (fracciones de la hoja entera) leídos por
    Tesseract sobre un recorte de la imagen."""
    import pytesseract
    from PIL import ImageOps
    from .. import os_engine
    W, H = img.size
    x0, y0, x1, y1 = recorte
    rec = ImageOps.autocontrast(img.crop((int(W * x0), int(H * y0), int(W * x1), int(H * y1))))
    w, h = rec.size
    d = pytesseract.image_to_data(rec, lang=os_engine.idioma_ocr(), config=f"--psm {psm}",
                                  output_type=pytesseract.Output.DICT)
    renglones = {}
    for i, txt in enumerate(d["text"]):
        if not (txt or "").strip():
            continue
        k = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        bx = (x0 + d["left"][i] / w * (x1 - x0), y0 + d["top"][i] / h * (y1 - y0),
              x0 + (d["left"][i] + d["width"][i]) / w * (x1 - x0),
              y0 + (d["top"][i] + d["height"][i]) / h * (y1 - y0))
        c = max(0.0, float(d["conf"][i])) / 100
        renglones.setdefault(k, []).append(OCRWord(text=txt, conf=c, bbox=bx, page=numero))
    out = []
    for ws in renglones.values():
        ws.sort(key=lambda w: w.bbox[0])
        bbox = (min(w.bbox[0] for w in ws), min(w.bbox[1] for w in ws),
                max(w.bbox[2] for w in ws), max(w.bbox[3] for w in ws))
        out.append(OCRLine(text=" ".join(w.text for w in ws), conf=sum(w.conf for w in ws) / len(ws),
                           bbox=bbox, page=numero, words=ws))
    return sorted(out, key=lambda l: (round(_yc(l), 3), l.bbox[0]))


def _cajas_de_tinta(img_rgb, minimo_ancho=0.06, minimo_alto=0.02):
    """Rectángulos donde hay tinta azul/violeta de sello (y la imagen en
    gris con SOLO esa tinta, para leer cada sello limpio)."""
    import numpy as np
    from PIL import Image, ImageFilter
    a = np.asarray(img_rgb.convert("RGB")).astype(np.int16)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    azul = (B - np.maximum(R, G) > 28) & (B > 90)
    H, W = azul.shape
    k = 12
    if H < k * 4 or W < k * 4:
        return [], None
    g = azul[:H // k * k, :W // k * k].reshape(H // k, k, W // k, k).mean(axis=(1, 3)) > 0.02
    g = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))) > 0
    lab = np.zeros(g.shape, np.int32)
    cajas, cur = [], 0
    for y in range(g.shape[0]):
        for x in range(g.shape[1]):
            if g[y, x] and not lab[y, x]:
                cur += 1
                pila, ys, xs = [(y, x)], [y], [x]
                lab[y, x] = cur
                while pila:
                    cy, cx = pila.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < g.shape[0] and 0 <= nx < g.shape[1] and g[ny, nx] and not lab[ny, nx]:
                            lab[ny, nx] = cur
                            pila.append((ny, nx))
                            ys.append(ny)
                            xs.append(nx)
                bx = (min(xs) * k / W, min(ys) * k / H, (max(xs) + 1) * k / W, (max(ys) + 1) * k / H)
                if bx[2] - bx[0] >= minimo_ancho and bx[3] - bx[1] >= minimo_alto:
                    cajas.append(bx)
    gris = np.asarray(img_rgb.convert("L"))
    solo = Image.fromarray(np.where(azul, gris, 255).astype(np.uint8))
    return cajas, solo


def _regiones_por_palabras(lineas):
    """Zonas de sello halladas por sus palabras («RECEPCIÓN», «PROVEÍDO»,
    «PASE A», «RECIBIDO»…) en renglones que no son del cuerpo."""
    marcas = [l for l in lineas if _SELLO_CLAVES.search(_sin_tildes(l.text or "")) and (l.bbox[2] - l.bbox[0]) < 0.45
              and not re.search(r"^\s*[a-e]\)|N\s*[°º*]\s*\d{3,}.{0,20}20\d\d", l.text or "")]
    cajas = []
    for l in marcas:
        bx = [max(0.0, l.bbox[0] - 0.06), max(0.0, l.bbox[1] - 0.06), min(1.0, l.bbox[2] + 0.06), min(1.0, l.bbox[3] + 0.06)]
        for c in cajas:
            if _solapa(c, bx) or (abs(c[1] - bx[1]) < 0.06 and abs(c[0] - bx[0]) < 0.15):
                c[0], c[1], c[2], c[3] = min(c[0], bx[0]), min(c[1], bx[1]), max(c[2], bx[2]), max(c[3], bx[3])
                break
        else:
            cajas.append(bx)
    return [tuple(c) for c in cajas]


def _une_cajas(cajas):
    """Junta las cajas que se tocan (un mismo sello puede salir en dos
    trozos: la oficina arriba y la fecha abajo)."""
    cajas = [list(c) for c in cajas]
    cambio = True
    while cambio:
        cambio = False
        for i in range(len(cajas)):
            for j in range(i + 1, len(cajas)):
                a, b = cajas[i], cajas[j]
                if a[0] - 0.02 < b[2] and b[0] - 0.02 < a[2] and a[1] - 0.025 < b[3] and b[1] - 0.025 < a[3]:
                    cajas[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    del cajas[j]
                    cambio = True
                    break
            if cambio:
                break
    return [tuple(c) for c in cajas]


def lectura_enfocada(page, numero, cabecera=True, pie=True, sellos=True, dpi=300):
    """Vuelve a leer, más nítido, lo que identifica al documento. Devuelve
    {'cabecera': [OCRLine], 'pie': [OCRLine], 'sellos': [(bbox, texto)]}."""
    out = {"cabecera": [], "pie": [], "sellos": []}
    if not _tesseract_ok():
        return out
    try:
        img = _imagen(page, dpi=dpi, gris=False)
    except Exception:
        return out
    gris = img.convert("L")
    try:
        if cabecera:
            out["cabecera"] = _lineas_tesseract(gris, numero, (0.0, 0.0, 1.0, 0.6), psm=6)
        if pie:
            out["pie"] = _lineas_tesseract(gris, numero, (0.0, 0.45, 1.0, 1.0), psm=11)
        if sellos:
            import pytesseract
            from PIL import Image, ImageOps
            from .. import os_engine
            cajas, _solo = _cajas_de_tinta(img)
            cajas = _une_cajas(cajas + _regiones_por_palabras(out["cabecera"] + out["pie"]))
            W, H = gris.size
            for bx in cajas[:8]:
                rec = gris.crop((int(bx[0] * W), int(bx[1] * H), int(bx[2] * W), int(bx[3] * H)))
                if rec.size[0] < 40 or rec.size[1] < 20:
                    continue
                rec = ImageOps.autocontrast(rec.resize((int(rec.size[0] * 4 / 3), int(rec.size[1] * 4 / 3)), Image.LANCZOS))
                lect = []
                # el sello de folio (arriba a la derecha) basta con una lectura
                modos = (6,) if (bx[1] < 0.12 and bx[0] > 0.6) else (6, 11)
                for psm in modos:
                    t = pytesseract.image_to_string(rec, lang=os_engine.idioma_ocr(), config=f"--psm {psm}")
                    t = " / ".join(x.strip() for x in t.splitlines() if len(x.strip()) > 2)
                    if t:
                        lect.append(t)
                if lect:
                    out["sellos"].append((tuple(round(c, 3) for c in bx), " // ".join(lect)))
    except Exception:
        pass
    return out


# ────────────────────────────────────────────────────────────── armado

_TIPOS_OFICIO = {"informe", "memorando", "requerimiento", "informe_cuantia", "solicitud_ccp"}
_DATOS_FORMULARIO = [
    ("Proveedor", r"SE\w?OR\s*\(?ES\)?|PROVEEDOR|RAZ[OÓ]N\s+SOCIAL"),
    ("RUC", r"R\.?\s?U\.?\s?C\.?"),
    ("Concepto", r"CONCEPTO|OBJETO|MOTIVO|DESCRIPCI[OÓ]N"),
    ("Dirección solicitante", r"DIRECCI[OÓ]N\s+SOLICITANTE|[AÁ]REA\s+(?:USUARIA|SOLICITANTE)"),
    ("Entregar a", r"ENTREGAR\s+A\s*(?:SR\(?A?\)?)?"),
    ("N° Exp. SIAF", r"N\S?\s*EXP\.?\s*SIAF"),
    ("Monto total", r"MONTO\s+TOTAL(?:\s+S/\.?)?|IMPORTE\s+TOTAL"),
    ("Fecha", r"FECHA(?:\s+DE\s+(?:EMISI[OÓ]N|CONFORMIDAD))?"),
]


def datos_de_formulario(lineas):
    """«Etiqueta : valor» de un formulario impreso (orden, pedido,
    conformidad): lo que sirve para reconocerlo de un vistazo."""
    out = {}
    for l in _renglones([l for l in lineas if _yc(l) < 0.7]):
        t = (l.text or "").strip()
        for nombre, pat in _DATOS_FORMULARIO:
            if nombre in out:
                continue
            m = re.match(r"^\W{0,3}(?:" + pat + r")\s*[:;.]?\s*(?::\s*)?(?P<v>.{3,})$", _sin_tildes(t), re.I)
            if m:
                v = _limpia(t[m.start("v"):])
                if re.match(r"^(DE|DEL|LA|EL)\b", _sin_tildes(v), re.I) and nombre != "Concepto":
                    continue
                if nombre == "RUC":
                    d = re.search(r"\d[\d\s]{9,14}\d", v)
                    if not d:
                        continue
                    v = re.sub(r"\s", "", d.group(0))[:11]
                if len(re.findall(r"[A-Za-z0-9]{2,}", v)) >= 1:
                    out[nombre] = v[:120]
                break
    return out


def _limpia_cargo(cargo, oficinas):
    """«Subgerencia del Pro:rama de Vaso de Leche (e» -> «Subgerencia del
    Programa de Vaso de Leche (e)»: el nombre de la oficina, bien escrito."""
    if not cargo:
        return cargo
    pal = cargo.split()
    mejor = None
    for o in oficinas:
        on = _norm(o)
        n = len(on.split())
        for i in range(0, len(pal)):
            for largo in (n - 1, n, n + 1):
                if largo < 2 or i + largo > len(pal):
                    continue
                trozo = " ".join(pal[i:i + largo])
                x = _parecido(_norm(trozo), on)
                if x >= 0.86 and (not mejor or x > mejor[0]):
                    mejor = (x, i, largo, o)
    if mejor:
        x, i, largo, o = mejor
        bonita = _bonita(o).split()
        # «Subgerente del Programa…»: el cargo de la persona se conserva y
        # solo se corrige el nombre de la oficina
        primera = _norm(pal[i])
        if primera != _norm(bonita[0]) and _CARGO_RE.match(_sin_tildes(pal[i]).upper()):
            bonita = [pal[i]] + bonita[1:]
        cargo = " ".join(pal[:i] + bonita + pal[i + largo:])
    cargo = re.sub(r"\(e$", "(e)", cargo.strip())
    return cargo


def _calidad(t):
    """Qué tan limpio es un texto (parte de palabras de verdad)."""
    if isinstance(t, dict):
        t = " ".join(str(v) for v in t.values())
    elif isinstance(t, list):
        t = " ".join(t)
    try:
        from .. import os_engine
        c = os_engine.calidad_del_texto(t or "")
    except Exception:
        c = None
    if c is None:
        pal = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", t or "")
        c = len(pal) / max(1, len((t or "").split()))
    return c


def _mezcla_campos(c0, c1):
    """Escáner (c0) y lectura enfocada (c1): de cada campo, la más limpia."""
    out = {}
    for k in set(c0) | set(c1):
        a, b = c0.get(k), c1.get(k)
        if not a or not b:
            out[k] = a or b
            continue
        if k in ("a", "de"):
            ca, cb = _calidad(a.get("nombre", "")), _calidad(b.get("nombre", ""))
            elegido, otro = (b, a) if cb >= ca else (a, b)
            elegido = dict(elegido)
            if not elegido.get("cargo"):
                elegido["cargo"] = otro.get("cargo", "")
            elif otro.get("cargo") and _calidad(otro["cargo"]) > _calidad(elegido["cargo"]) + 0.1:
                elegido["cargo"] = otro["cargo"]
            if not elegido.get("trato") and otro.get("trato"):
                elegido["trato"] = otro["trato"]
            out[k] = elegido
        else:
            out[k] = b if _calidad(b) >= _calidad(a) - 0.05 else a
    if out.get("fecha") and not out.get("fecha_iso"):
        iso = fecha_de(out["fecha"])
        if iso:
            out["fecha_iso"] = iso
    return out


def _personas_conocidas(doc, fichas_previas, extra=None):
    """Personas que el expediente nombra con claridad (A, DE, «Entregar a»,
    el proveedor) y las del directorio de funcionarios."""
    personas = {}
    for f in fichas_previas:
        for k in ("a", "de"):
            p = (f.get("campos") or {}).get(k)
            if p and len(_palabras_nombre(p["nombre"])) >= 2:
                ya = personas.get(_norm(p["nombre"]))
                if not ya:
                    personas[_norm(p["nombre"])] = {"nombre": p["nombre"], "cargo": p.get("cargo", "")}
                elif p.get("cargo") and (not ya["cargo"] or _calidad(p["cargo"]) > _calidad(ya["cargo"])):
                    ya["cargo"] = p["cargo"]
    for pg in doc.pages:
        for l in pg.lines:
            m = re.search(r"(?:ENTREGAR\s+A\s+SR\(?A?\)?|SE[ÑN]OR\(?ES\)?|PROVEEDOR)\s*[:.]\s*([A-ZÁÉÍÓÚÑ ]{8,60})", l.text or "", re.I)
            if m and len(_palabras_nombre(m.group(1))) >= 3:
                n = _limpia(m.group(1)).upper()
                personas.setdefault(_norm(n), {"nombre": n, "cargo": ""})
    for p in extra or []:
        if p.get("nombre") and len(_palabras_nombre(p["nombre"])) >= 2:
            personas.setdefault(_norm(p["nombre"]), {"nombre": p["nombre"].upper(), "cargo": p.get("cargo", "")})
    # «PERE2» y «PEREZ» son la misma persona: se deja la escritura
    # que más se repite en el expediente
    texto = _norm(doc.text())
    unicas = []
    for p in sorted(personas.values(), key=lambda p: -texto.count(_norm(p["nombre"]))):
        igual = next((u for u in unicas if _parecido(_norm(u["nombre"]), _norm(p["nombre"])) >= 0.9), None)
        if igual:
            if p.get("cargo") and (not igual.get("cargo") or _calidad(p["cargo"]) > _calidad(igual["cargo"])):
                igual["cargo"] = p["cargo"]
            continue
        unicas.append(dict(p))
    return unicas


def _directorio(doc):
    """Funcionarios del directorio de municipalidades cuya entidad (RUC)
    aparece en el expediente."""
    try:
        from .. import municipalidades
    except Exception:
        return []
    rucs = set(re.findall(r"\b(20\d{9})\b", doc.text()))
    out = []
    for m in municipalidades.list_municipalidades():
        if m["ruc"] in rucs:
            for e in municipalidades.list_encargados(m["ruc"]) or []:
                out.append({"nombre": e.get("nombre", ""), "cargo": e.get("cargo", "")})
    return out


def fichas(doc, segs, mu_doc=None, enfocar=True, progreso=None):
    """Una ficha por segmento, en el mismo orden."""
    siglas, oficinas = siglas_del_expediente(doc)
    citas = citas_del_expediente(doc, siglas)
    enfoque = {}
    cache = doc.meta.setdefault("lectura_enfocada", {}) if isinstance(getattr(doc, "meta", None), dict) else {}
    usar_tess = enfocar and mu_doc is not None and _tesseract_ok() and doc.provider != "azure-document-intelligence"

    def _enf(numero, cab=True, pie=True):
        clave = str(numero)
        if clave in cache:
            e = cache[clave]
            return {"cabecera": [_linea_de_dict(x) for x in e.get("cabecera", [])],
                    "pie": [_linea_de_dict(x) for x in e.get("pie", [])],
                    "sellos": [tuple(x) for x in e.get("sellos", [])]}
        if not usar_tess:
            return {"cabecera": [], "pie": [], "sellos": []}
        e = lectura_enfocada(mu_doc[numero - 1], numero, cabecera=cab, pie=pie)
        cache[clave] = {"cabecera": [_linea_a_dict(x) for x in e["cabecera"]],
                        "pie": [_linea_a_dict(x) for x in e["pie"]],
                        "sellos": [list(x) for x in e["sellos"]]}
        return e

    salida = []
    total = len(segs)
    for k, s in enumerate(segs):
        pg0 = doc.pages[s.pagina_ini - 1]
        e0 = _enf(s.pagina_ini)
        enfoque[s.pagina_ini] = e0
        ult = s.pagina_fin
        # última hoja con contenido del documento (para las firmas)
        while ult > s.pagina_ini and len(_norm(doc.pages[ult - 1].text)) < 25:
            ult -= 1
        eu = e0 if ult == s.pagina_ini else _enf(ult)
        enfoque[ult] = eu

        ficha = {"pagina_ini": s.pagina_ini, "pagina_fin": s.pagina_fin, "tipo": s.tipo}
        # 1) título
        candidatos = [buscar_titulo(pg0.lines, siglas, tipo=s.tipo),
                      buscar_titulo(e0["cabecera"], siglas, tipo=s.tipo)]
        # la lectura enfocada (300 ppp) manda sobre el texto del escáner,
        # salvo que salga claramente peor
        base, enf = candidatos
        if base and enf and base["numero"].lstrip("0") == enf["numero"].lstrip("0") and base["anio"] == enf["anio"]:
            t = dict(base if len(base["siglas"]) > len(enf["siglas"]) else enf)
            if not t["numero"] and t.get("ilegible") and not (base.get("ilegible") and enf.get("ilegible")):
                t["ilegible"] = False
                t["titulo"] = _arma(t["clase"], "", t["anio"], t.get("sal", []), t["siglas"], t["seps"])
        elif base and enf:
            t = enf if enf["confianza"] >= base["confianza"] - 0.1 else base
        else:
            t = base or enf
        if t and s.tipo in ("comprobante_pago",):
            t = None
        if t:
            usados = {f.get("_numero") for f in salida if f.get("_numero")}
            t = _confirma_con_citas(t, citas, s.pagina_ini, usados)
            ficha["_numero"] = t["numero"].lstrip("0")
            ficha["titulo"] = t["titulo"]
            ficha["confianza_titulo"] = t["confianza"]
            if t.get("confirmado"):
                ficha["titulo_nota"] = t["confirmado"]
        elif s.tipo == "comprobante_pago":
            ficha["titulo"] = _factura(pg0)
            ficha["confianza_titulo"] = 0.8
        else:
            libre = _titulo_libre(pg0, s)
            if not libre and e0["cabecera"]:
                from .ocr_base import OCRPage
                libre = _titulo_libre(OCRPage(s.pagina_ini, 0, 0, 0, e0["cabecera"]), s)
            ficha["titulo"] = libre or s.etiqueta
            ficha["confianza_titulo"] = 0.75 if libre else 0.5
        # 2) campos A / DE / ASUNTO / REFERENCIA / FECHA (oficios, informes,
        #    memorandos); en los formularios (orden, pedido, conformidad…)
        #    sus propios datos: proveedor, RUC, concepto, «entregar a»…
        es_oficio = s.tipo in _TIPOS_OFICIO or (t and t["clase"] in _DOCUMENTALES)
        if es_oficio:
            c1 = leer_campos(e0["cabecera"]) if e0["cabecera"] else {}
            c0 = leer_campos(pg0.lines)
            campos = _mezcla_campos(c0, c1)
            if campos:
                ficha["campos"] = campos
        elif s.tipo not in ("proveido", "anexo", "solicitud_cotizacion", "comprobante_pago", "validez_cpe"):
            datos = datos_de_formulario(pg0.lines) or datos_de_formulario(e0["cabecera"])
            if datos:
                ficha["datos"] = datos
        salida.append(ficha)
        if progreso and (k % 3 == 0 or k == total - 1):
            try:
                progreso(k + 1, total, "Identificando los documentos")
            except Exception:
                pass

    # 3) firmas y sellos (necesitan conocer a las personas de TODO el expediente)
    personas = _personas_conocidas(doc, salida, _directorio(doc))
    for p in personas:
        if p.get("cargo"):
            p["cargo"] = _limpia_cargo(p["cargo"], oficinas)
    for ficha in salida:
        for k in ("a", "de"):
            c = (ficha.get("campos") or {}).get(k)
            if not c:
                continue
            igual = next((p for p in personas if _parecido(_norm(p["nombre"]), _norm(c["nombre"])) >= 0.88), None)
            if igual:
                c["nombre"] = _TRATO_RE.sub("", igual["nombre"]).strip()
            if c.get("cargo"):
                c["cargo"] = _limpia_cargo(c["cargo"], oficinas)
    for ficha, s in zip(salida, segs):
        paginas = []
        for n in sorted({s.pagina_ini, s.pagina_fin} | set(range(s.pagina_ini, s.pagina_fin + 1))):
            pg = doc.pages[n - 1]
            if len(_norm(pg.text)) < 25:
                continue
            ls = list(pg.lines)
            e = enfoque.get(n)
            if e:
                ls += e["pie"]
            paginas.append((n, ls))
        f = leer_firmas(paginas, personas, oficinas)
        unicas = []
        for x in f:
            x["cargo"] = _limpia_cargo(x.get("cargo", ""), oficinas)
            igual = next((u for u in unicas if _norm(u["nombre"]) == _norm(x["nombre"])), None)
            if igual:
                igual.setdefault("paginas", [igual["pagina"]]).append(x["pagina"])
                for k in ("cargo", "oficina", "dni"):
                    if not igual.get(k) and x.get(k):
                        igual[k] = x[k]
                continue
            unicas.append(x)
        if unicas:
            ficha["firmas"] = unicas
        sellos = []
        fecha_doc = (ficha.get("campos") or {}).get("fecha_iso", "")
        for n, ls in paginas:
            e = enfoque.get(n)
            vistos = []
            if e:
                for bx, txt in e["sellos"]:
                    # tinta azul con el nombre de quien firma: es la firma, no un sello
                    if any(sum(1 for w in _palabras_nombre(p["nombre"]) if w in _norm(txt).split()) >= 2
                           for p in personas) and not _SELLO_CLAVES.search(_sin_tildes(txt)):
                        continue
                    sl = parsear_sello(txt, oficinas, fecha_doc, bx)
                    sl["pagina"], sl["bbox"], sl["como"] = n, bx, "tinta de sello"
                    sellos.append(sl)
                    vistos.append(bx)
            for sl in leer_sellos_de_lineas(ls, oficinas, fecha_doc):
                if any(_solapa(sl["bbox"], v) for v in vistos):
                    continue
                sl["pagina"], sl["como"] = n, "texto"
                sellos.append(sl)
        sellos = _une_sellos(sellos)
        if sellos:
            ficha["sellos"] = sellos
        if s.tipo == "proveido" and ficha.get("titulo") == s.etiqueta:
            ficha["titulo"] = _titulo_proveido(sellos, siglas) or ficha["titulo"]
        ficha["resumen"] = resumen_corto(ficha)
        ficha.pop("_numero", None)
    return salida


def _titulo_proveido(sellos, siglas):
    """«PROVEÍDO N° 4431-2026-MPC/OGAF-OLG — al Coordinador de Contratos
    Menores de Bienes y Servicios», leído del sello del proveído."""
    for sl in sellos:
        if sl["tipo"] != "proveído":
            continue
        t = sl.get("texto", "")
        u = _sin_tildes(t).upper()
        titulo = "PROVEÍDO"
        m = re.search(r"PROVE\W{0,2}I?\W?[DI]?O\W{0,3}N?\W{0,3}(?P<resto>[^/|]{0,40})", u)
        if m:
            cola = m.group("resto")
            num = re.match(r"\s*(\d{3,6})\b", cola)
            anio = re.search(r"(20\d\d)", cola)
            sig = re.search(r"(MPC[A-Z0-9/\-I]{3,30})", cola.replace(" ", ""))
            partes, seps = [], []
            if sig:
                for sep_i, tok in re.findall(r"([-/]?)([A-Z0-9]+)", sig.group(1)):
                    for j, pz in enumerate(_parte_siglas(tok.replace("0", "O"), siglas)):
                        c, ok = _corrige_sigla(pz, siglas)
                        if len(c) >= 2 and (ok or len(c) >= 3):
                            partes.append(c)
                            seps.append((sep_i or "-") if j == 0 else "/")
            if partes:
                titulo = _arma("PROVEÍDO", num.group(1) if num else "", anio.group(1) if anio else "", [],
                               partes, ["-"] + seps[1:], ilegible=not num)
        if re.search(r"MENORES", u) and re.search(r"BIENES", u):
            titulo += " — al Coordinador de Contratos Menores de Bienes y Servicios"
        else:
            a = re.search(r"\bAL\.?,?\s+([A-Za-zÁÉÍÓÚÑáéíóúñ .:]{8,60})", t, re.I)
            if a:
                titulo += " — al " + _limpia(a.group(1))
        return titulo
    return ""


def _solapa(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area = max(1e-6, min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])))
    return ix * iy / area > 0.3


def _une_sellos(sellos):
    """El sello de folio se repite en cada hoja: se deja uno por documento
    (con la lista de folios) y se conservan todos los demás."""
    # sello en la esquina de arriba a la derecha con «Folio»: es el de foliación
    for s in sellos:
        bx = s.get("bbox") or (0, 1, 0, 1)
        if s["tipo"] == "sello" and bx[1] < 0.13 and bx[0] > 0.6:
            s["tipo"] = "folio"
    folios = [s for s in sellos if s["tipo"] == "folio"]
    otros = [s for s in sellos if s["tipo"] != "folio"]
    def util(s):
        datos = sum(1 for k in ("entidad", "oficina", "fecha", "hora", "numero") if s.get(k))
        if s["tipo"] == "proveído":
            return datos >= 1 or re.search(r"PASE|ATENDER|COOR", _sin_tildes(s.get("texto", "")).upper())
        if s["tipo"] in ("recepción", "visto bueno"):
            return datos >= 1
        return s.get("entidad") and (s.get("oficina") or s.get("fecha"))
    out = [s for s in otros if util(s)]
    if folios:
        f = dict(max(folios, key=lambda s: len(s.get("oficinas") or [s.get("oficina")] if s.get("oficina") else [])))
        f.pop("bbox", None)
        f["paginas"] = sorted({s["pagina"] for s in folios})
        out.append(f)
    return out


def _linea_a_dict(l):
    return {"text": l.text, "conf": l.conf, "bbox": list(l.bbox), "page": l.page}


def _linea_de_dict(d):
    return OCRLine(text=d["text"], conf=d["conf"], bbox=tuple(d["bbox"]), page=d["page"],
                   words=[OCRWord(text=w, conf=d["conf"], bbox=tuple(d["bbox"]), page=d["page"])
                          for w in d["text"].split()])


_MES_NOMBRE = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "setiembre", "octubre", "noviembre", "diciembre"]


def fecha_legible(iso):
    try:
        a, m, d = iso.split("-")
        return f"{int(d)} de {_MES_NOMBRE[int(m)]} de {a}"
    except Exception:
        return iso


def resumen_corto(ficha):
    """Lo que se ve al pasar el puntero, en pocas líneas."""
    partes = [ficha.get("titulo") or ""]
    c = ficha.get("campos") or {}
    if c.get("asunto"):
        partes.append("Asunto: " + c["asunto"])
    if c.get("de"):
        partes.append("De: " + " ".join(x for x in (c["de"].get("trato"), c["de"]["nombre"]) if x) +
                      (f" — {c['de']['cargo']}" if c["de"].get("cargo") else ""))
    if c.get("a"):
        partes.append("A: " + " ".join(x for x in (c["a"].get("trato"), c["a"]["nombre"]) if x) +
                      (f" — {c['a']['cargo']}" if c["a"].get("cargo") else ""))
    if c.get("fecha_iso"):
        partes.append("Fecha: " + fecha_legible(c["fecha_iso"]))
    elif c.get("fecha"):
        partes.append("Fecha: " + c["fecha"])
    for f in ficha.get("firmas") or []:
        ofi = f.get("oficina", "")
        if ofi and _norm(ofi) in _norm(f.get("cargo", "")).replace("SUBGERENTE", "SUBGERENCIA"):
            ofi = ""
        partes.append("Firma: " + f["nombre"] + (f" — {f['cargo']}" if f.get("cargo") else "") +
                      (f", {ofi}" if ofi else "") + (f" (DNI {f['dni']})" if f.get("dni") else ""))
    for k, v in (ficha.get("datos") or {}).items():
        partes.append(f"{k}: {v}")
    for s in ficha.get("sellos") or []:
        if s["tipo"] == "folio":
            continue
        d = [{"sello": "Sello de oficina"}.get(s["tipo"], s["tipo"].capitalize())]
        if s.get("oficina"):
            d.append(s["oficina"])
        if s.get("fecha"):
            d.append(fecha_legible(s["fecha"]))
        if s.get("hora"):
            d.append(s["hora"])
        if s.get("numero"):
            d.append("N° " + s["numero"])
        partes.append("Sello: " + " · ".join(d))
    return "\n".join(p for p in partes if p)
