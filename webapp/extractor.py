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
    return ctx

def clave_objeto(objeto):
    """Clave estable para agrupar el mismo objeto contractual."""
    t = _n(objeto)
    t = re.sub(r"[^A-Z0-9 ]", " ", t)
    t = re.sub(r"\b(DE|DEL|LA|LAS|LOS|EL|EN|Y|A|AL|PARA|POR)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()[:70]
