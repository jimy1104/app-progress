# -*- coding: utf-8 -*-
"""Extrae de la Orden (de servicio o de compra) los datos mínimos que alimentan
el ACUMULADO de fraccionamiento: N° de orden, RUC del proveedor, monto total,
objeto (concepto) y año. Nunca se guarda el PDF, solo estos campos."""
import re, unicodedata

MUNI_RUC = "20131369558"   # RUC de la Municipalidad (no es el proveedor)

def _n(t):
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.upper()).strip()

_NUM = re.compile(r"\d{1,3}(?:[.,]\d{3})*[.,]\d{2}(?!\d)")

def parse_monto(txt):
    """'12,744.00' / '12.744,00' / '12,744,00' -> 12744.0"""
    out = []
    for m in _NUM.findall(txt or ""):
        entero, dec = m[:-3], m[-2:]
        entero = re.sub(r"[.,]", "", entero)
        try:
            out.append(float(f"{entero}.{dec}"))
        except ValueError:
            pass
    return out

def _paginas_orden(doc, segmentos):
    pags = [p for s in segmentos if s.tipo == "orden_servicio"
            for p in range(s.pagina_ini, s.pagina_fin + 1)]
    return pags or list(range(1, min(3, doc.n_pages) + 1))

def extraer_contexto(doc, segmentos, nombre_archivo=""):
    ctx = {"os": "", "ruc": "", "monto": 0.0, "monto_fuente": "", "monto_linea": None,
           "objeto": "", "anio": None}
    pags = _paginas_orden(doc, segmentos)
    lineas = [ln for p in pags for ln in doc.pages[p - 1].lines]

    # N° de orden. En el escaneo, el número suele caer en el renglón de al lado
    # («ORDEN DE SERVICIO N°» arriba y «0010559» debajo), así que si el título no
    # trae dígitos se buscan en los renglones siguientes.
    for i, ln in enumerate(lineas):
        t = _n(ln.text)
        if not re.search(r"ORDEN DE (?:SERVICIO|COMPRA)", t):
            continue
        m = re.search(r"ORDEN DE (?:SERVICIO|COMPRA)\W{0,6}N\W{0,4}0*(\d{3,8})", t)
        if m:
            ctx["os"] = m.group(1); break
        for sig in lineas[i + 1:i + 5]:
            m = re.match(r"^\W{0,4}0*(\d{3,8})\W{0,3}$", _n(sig.text))
            if m:
                ctx["os"] = m.group(1); break
        if ctx["os"]: break
    if not ctx["os"] and nombre_archivo:
        m = re.search(r"(?:^|[^A-Z])(?:O\.?\s?S\.?|O\.?\s?C\.?|ORDEN)\s*N?\W{0,3}0*(\d{3,8})", _n(nombre_archivo))
        if m: ctx["os"] = m.group(1)

    # RUC del proveedor (primer RUC de 11 dígitos 10/20 que no sea el de la Municipalidad)
    for ln in lineas:
        if "RUC" in _n(ln.text):
            dig = re.sub(r"\D", "", ln.text.split("RUC", 1)[-1] if "RUC" in ln.text else ln.text)
            for i in range(0, max(1, len(dig) - 10)):
                cand = dig[i:i + 11]
                if len(cand) == 11 and cand[:2] in ("10", "20") and cand != MUNI_RUC:
                    ctx["ruc"] = cand; break
        if ctx["ruc"]: break

    # Monto total: solo la PRIMERA orden del expediente; se prefiere el importe
    # que aparece en líneas con 'TOTAL' y, entre candidatos, el más repetido.
    primera = [s for s in segmentos if s.tipo == "orden_servicio"]
    pags1 = (list(range(primera[0].pagina_ini, primera[0].pagina_fin + 1)) if primera else pags[:2])
    lin1 = [ln for p in pags1 for ln in doc.pages[p - 1].lines]
    from collections import Counter
    todos = Counter(v for ln in lin1 for v in parse_monto(ln.text) if 0 < v <= 200 * 5500)
    cand = []
    for ln in lin1:
        t = _n(ln.text)
        if "TOTAL" in t and "SUB" not in t:
            for v in parse_monto(ln.text):
                if 0 < v <= 200 * 5500:
                    cand.append((todos[v], v, ln))
    if cand:
        cand.sort(key=lambda x: (x[0], x[1]), reverse=True)
        ctx["monto"], ctx["monto_fuente"], ctx["monto_linea"] = cand[0][1], "orden", cand[0][2]
    elif todos:
        v, _ = todos.most_common(1)[0]
        ctx["monto"], ctx["monto_fuente"] = v, "estimado"

    # Objeto / concepto
    for ln in lineas:
        t = _n(ln.text)
        m = re.match(r"^(?:CONCEPTO|CONCENTO|CONCEPT0|OBJETO)\W*[:;]?\s*(.+)$", t)
        if m and len(m.group(1)) > 8:
            ctx["objeto"] = m.group(1)[:120]; break
    if not ctx["objeto"]:
        for ln in lineas:
            t = _n(ln.text)
            if re.search(r"\b(SERVICIO DE|ADQUISICION DE|CONTRATACION DE)\b", t) and len(t) > 15:
                ctx["objeto"] = t[:120]; break

    # Año: primero en la orden; si el escaneo no lo dejó legible, el año que más
    # se repite en todo el expediente.
    for ln in lineas:
        m = re.search(r"\b(20[2-3]\d)\b", ln.text)
        if m: ctx["anio"] = int(m.group(1)); break
    if not ctx["anio"]:
        from collections import Counter
        años = Counter(int(a) for p in doc.pages for a in re.findall(r"\b(20[1-3]\d)\b", p.text))
        if años: ctx["anio"] = años.most_common(1)[0][0]
    try:
        ctx["validaciones"] = validar(doc, segmentos, ctx)
    except Exception as e:                       # la validación nunca debe tumbar el proceso
        ctx["validaciones"] = [{"dato": "validación", "estado": "error", "detalle": str(e)[:200]}]
    return ctx

def clave_objeto(objeto):
    """Clave estable para agrupar el mismo objeto contractual."""
    t = _n(objeto)
    t = re.sub(r"[^A-Z0-9 ]", " ", t)
    t = re.sub(r"\b(DE|DEL|LA|LAS|LOS|EL|EN|Y|A|AL|PARA|POR)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()[:70]


# =====================================================================
#  VALIDACIÓN CRUZADA: un dato leído por OCR se da por BUENO solo si otra
#  fuente independiente lo confirma. Así un «3» leído como «9» no pasa.
# =====================================================================
_PESOS_RUC = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def ruc_valido(ruc: str) -> bool:
    """Dígito verificador del RUC (SUNAT, módulo 11)."""
    if not re.fullmatch(r"(10|15|16|17|20)\d{9}", ruc or ""):
        return False
    s = sum(int(d) * p for d, p in zip(ruc[:10], _PESOS_RUC))
    dv = 11 - s % 11
    dv = 0 if dv == 10 else 1 if dv == 11 else dv
    return dv == int(ruc[10])


_UNI = {"CERO": 0, "UN": 1, "UNO": 1, "UNA": 1, "DOS": 2, "TRES": 3, "CUATRO": 4, "CINCO": 5, "SEIS": 6,
        "SIETE": 7, "OCHO": 8, "NUEVE": 9, "DIEZ": 10, "ONCE": 11, "DOCE": 12, "TRECE": 13, "CATORCE": 14,
        "QUINCE": 15, "DIECISEIS": 16, "DIECISIETE": 17, "DIECIOCHO": 18, "DIECINUEVE": 19, "VEINTE": 20,
        "VEINTIUN": 21, "VEINTIUNO": 21, "VEINTIDOS": 22, "VEINTITRES": 23, "VEINTICUATRO": 24,
        "VEINTICINCO": 25, "VEINTISEIS": 26, "VEINTISIETE": 27, "VEINTIOCHO": 28, "VEINTINUEVE": 29,
        "TREINTA": 30, "CUARENTA": 40, "CINCUENTA": 50, "SESENTA": 60, "SETENTA": 70, "OCHENTA": 80,
        "NOVENTA": 90, "CIEN": 100, "CIENTO": 100, "DOSCIENTOS": 200, "TRESCIENTOS": 300,
        "CUATROCIENTOS": 400, "QUINIENTOS": 500, "SEISCIENTOS": 600, "SETECIENTOS": 700,
        "OCHOCIENTOS": 800, "NOVECIENTOS": 900}
_VOCAB_NUM = list(_UNI) + ["MIL", "MILLON", "MILLONES", "Y"]


def letras_a_numero(texto: str):
    """«TREINTA Y NUEVE MIL NOVECIENTOS Y 00/100 SOLES» -> 39900.0 (tolera errores de OCR)."""
    from difflib import get_close_matches
    t = _n(texto)
    m = re.search(r"((?:[A-Z]+\s+){1,14}?)(?:Y|CON)\s*(\d{2})\s*/\s*\S{2,4}", t)
    if not m:
        return None
    total = actual = 0
    vistos = 0
    for w in m.group(1).split():
        if w not in _VOCAB_NUM:
            c = get_close_matches(w, _VOCAB_NUM, n=1, cutoff=0.8)
            if not c:
                continue
            w = c[0]
        if w == "Y":
            continue
        vistos += 1
        if w in _UNI:
            actual += _UNI[w]
        elif w == "MIL":
            total += max(actual, 1) * 1000; actual = 0
        elif w in ("MILLON", "MILLONES"):
            total = (total + max(actual, 1)) * 1_000_000; actual = 0
    if not vistos:
        return None
    return float(total + actual) + int(m.group(2)) / 100.0


def _montos_linea(ln):
    return [v for v in parse_monto(ln.text) if 0 < v <= 200 * 5500]


def validar(doc, segmentos, ctx):
    """Contrasta los datos leídos entre fuentes independientes. Devuelve la lista
    de validaciones y AJUSTA ctx cuando una lectura errónea queda desmentida."""
    from collections import Counter
    val = []
    por_tipo = {}
    for s in segmentos or []:
        por_tipo.setdefault(s.tipo, []).append(s)

    def lineas_de(tipo, solo_primero=True):
        segs = por_tipo.get(tipo, [])[:1] if solo_primero else por_tipo.get(tipo, [])
        return [ln for s in segs for p in range(s.pagina_ini, s.pagina_fin + 1) for ln in doc.pages[p - 1].lines]

    orden = lineas_de("orden_servicio")
    if not orden:       # misma regla de respaldo que extraer_contexto (primeras hojas)
        orden = [ln for p in _paginas_orden(doc, segmentos)[:3] for ln in doc.pages[p - 1].lines]
    conf = lineas_de("conformidad", solo_primero=False)
    fact = lineas_de("comprobante_pago", solo_primero=False)

    # ---------------- monto total: votan fuentes independientes ----------------
    fuentes = {}
    tot = Counter(v for ln in orden if "TOTAL" in _n(ln.text) and "SUB" not in _n(ln.text) for v in _montos_linea(ln))
    if tot:
        fuentes["total de la orden"] = tot.most_common(1)[0][0]
    venta = [v for ln in orden if re.search(r"\bV\W{0,2}VENTA\b|VALOR VENTA", _n(ln.text)) for v in _montos_linea(ln)]
    igv = [v for ln in orden if re.search(r"\bI\W?G\W?V\b", _n(ln.text)) for v in _montos_linea(ln)]
    for a in venta:
        for b in igv:
            if abs(a * 0.18 - b) <= 0.02 * b + 0.05:
                fuentes["valor venta + IGV"] = round(a + b, 2)
    for ln in orden:
        v = letras_a_numero(ln.text)
        if v:
            fuentes["monto en letras"] = v
            break
    montos_conf = [v for ln in conf for v in _montos_linea(ln)]
    votos = Counter(fuentes.values())
    if montos_conf:
        for v in list(votos):
            if any(abs(v - c) < 0.01 for c in montos_conf):
                fuentes["conformidad"] = v
        votos = Counter(fuentes.values())
    # monto_validado: True = dos o más fuentes coinciden; None = una sola fuente (no hay
    # contradicción: se usa como antes); False = las fuentes se CONTRADICEN (no se confía)
    if votos:
        ganador, n = votos.most_common(1)[0]
        confirman = [k for k, v in fuentes.items() if abs(v - ganador) < 0.01]
        if n >= 2:
            val.append({"dato": "monto", "estado": "confirmado", "valor": ganador,
                        "detalle": "coinciden: " + ", ".join(confirman)})
            if abs((ctx.get("monto") or 0) - ganador) >= 0.01:
                val[-1]["corregido_de"] = ctx.get("monto")
                # el renglón a resaltar debe mostrar el monto confirmado, no el mal leído
                ctx["monto_linea"] = next((ln for ln in orden if any(abs(v - ganador) < 0.01
                                                                      for v in _montos_linea(ln))), None)
            ctx["monto"], ctx["monto_fuente"] = ganador, "orden"
            ctx["monto_validado"] = True
        elif len(fuentes) >= 2:
            val.append({"dato": "monto", "estado": "en conflicto", "valor": ctx.get("monto"),
                        "detalle": "las fuentes no coinciden: " + "; ".join(f"{k} {v:,.2f}" for k, v in fuentes.items())})
            ctx["monto_validado"] = False
        else:
            val.append({"dato": "monto", "estado": "sin confirmar", "valor": ctx.get("monto"),
                        "detalle": "solo una fuente: " + ", ".join(fuentes)})
            ctx["monto_validado"] = None
    else:
        ctx["monto_validado"] = None

    # ---------------- RUC del proveedor: dígito verificador + otras fuentes -----
    cands = Counter()
    for fuente, lineas in (("orden", orden), ("conformidad", conf), ("factura", fact)):
        for ln in lineas:
            t = _n(ln.text)
            if "RUC" not in t:
                continue
            dig = re.sub(r"\D", "", t.split("RUC", 1)[1])[:11]
            if len(dig) == 11 and dig != MUNI_RUC:
                cands[(dig, fuente)] += 1
    validos = Counter()
    for (r, f), n in cands.items():
        if ruc_valido(r):
            validos[r] += 1
    ruc = ctx.get("ruc", "")
    if ruc and ruc_valido(ruc):
        otros = [f for (r, f) in cands if r == ruc]
        val.append({"dato": "ruc", "estado": "confirmado", "valor": ruc,
                    "detalle": "dígito verificador correcto" + (f"; aparece en: {', '.join(sorted(set(otros)))}" if otros else "")})
    elif validos:
        bueno = validos.most_common(1)[0][0]
        val.append({"dato": "ruc", "estado": "corregido", "valor": bueno, "corregido_de": ruc,
                    "detalle": "el RUC leído no pasa el dígito verificador; se usa el de otra hoja que sí lo pasa"})
        ctx["ruc"] = bueno
    elif ruc:
        val.append({"dato": "ruc", "estado": "dudoso", "valor": ruc,
                    "detalle": "no pasa el dígito verificador de SUNAT: revíselo en el documento"})
    malos = sorted({r for (r, f) in cands if not ruc_valido(r) and r != ctx.get("ruc")})
    if malos:
        val.append({"dato": "ruc", "estado": "lectura descartada", "valor": ", ".join(malos),
                    "detalle": "lecturas de RUC con dígito verificador inválido (error de OCR)"})

    # ---------------- N° de orden citado en la conformidad ----------------------
    if ctx.get("os") and conf:
        os_n = ctx["os"].lstrip("0")
        citadas = set()
        for i, ln in enumerate(conf):
            if "ORDEN" not in _n(ln.text):
                continue
            # el número va en el mismo renglón o en el de al lado («N° DE ORDEN | 2026-105 59»)
            for cand in [ln] + conf[i + 1:i + 3]:
                t = re.sub(r"(?<=\d)[\s\-]+(?=\d)", "", cand.text)    # «2026-105 59» -> «202610559»
                for d in re.findall(r"\d{3,14}", t):
                    d0 = d.lstrip("0")
                    if re.fullmatch(r"20[1-3]\d\d{3,8}", d):          # año pegado: 2026 + 10559
                        citadas.add(d[4:].lstrip("0"))
                    citadas.add(d0)
        if os_n and os_n in citadas:
            val.append({"dato": "orden", "estado": "confirmado", "valor": ctx["os"],
                        "detalle": "la conformidad cita la misma orden"})
        elif citadas:
            val.append({"dato": "orden", "estado": "en conflicto", "valor": ctx["os"],
                        "detalle": "la conformidad cita otro número: " + ", ".join(sorted(citadas)[:3])})
    return val
