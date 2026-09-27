# -*- coding: utf-8 -*-
"""RELECTURA DIRIGIDA de los números que identifican cada documento.

El número de un documento («PEDIDO DE SERVICIO N° 000966», «INFORME N° 132-2026-…»)
es lo que más importa para reconocerlo y lo que más daño hace si sale mal: un 6
leído como 8 cambia de documento. Cuando la palabra con cifras del renglón de título
no salió segura, se vuelve a leer SOLO ese recorte, ampliado y con el lector
restringido a cifras y separadores, dos veces (a 300 y a 400 ppp). Si las dos
lecturas coinciden entre sí y tienen la forma de lo que se leyó (mismo largo, mismos
separadores), reemplazan a la primera; si no coinciden, se deja lo que había.

Usa Tesseract si está instalado; si no (p. ej. en Azure App Service sin el binario),
no hace nada. Nunca tumba el procesamiento.
"""
from __future__ import annotations
import re
import shutil

_TITULO = re.compile(r"\b(N|NRO|NUM|NUMERO)\s?\W{0,3}\s*\d|\b(ORDEN|PEDIDO|INFORME|MEMORANDO|OFICIO|CARTA|"
                     r"CONFORMIDAD|CONTRATO|RESOLUCION|FACTURA|CERTIFICACION)\b")
CONF_SEGURA = 0.95


def _n(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", t or "")
    return "".join(c for c in t if not unicodedata.combining(c)).upper()


def objetivos(doc, segmentos):
    """(página, renglón, palabra) de las cifras dudosas en el renglón de título de cada
    documento (primer tercio de su primera hoja)."""
    out = []
    for s in segmentos:
        pg = doc.pages[s.pagina_ini - 1]
        if (pg.meta or {}).get("fuente") == "texto-nativo":
            continue                                         # texto digital: ya es exacto
        for ln in pg.lines:
            if (ln.bbox[1] + ln.bbox[3]) / 2 > 0.4 or not _TITULO.search(_n(ln.text)):
                continue
            for w in ln.words:
                cifras = sum(c.isdigit() for c in w.text)
                if cifras >= 3 and cifras >= 0.6 * len(re.sub(r"[-/.]", "", w.text)) and (w.conf or 0) < CONF_SEGURA:
                    out.append((s.pagina_ini, ln, w))
    return out


def _forma(t):
    return re.sub(r"\d", "9", t)


def releer_numeros(doc, segmentos, pdf_path, dpis=(300, 400)) -> list:
    """Relee las cifras dudosas de los títulos. Devuelve [{pagina, antes, despues}]."""
    if not shutil.which("tesseract"):
        return []
    try:
        import pymupdf
        import pytesseract
        from . import imagen
    except Exception:
        return []
    cambios = []
    obj = objetivos(doc, segmentos)
    if not obj:
        return cambios
    try:
        with pymupdf.open(pdf_path) as pdf:
            por_pagina = {}
            for p, ln, w in obj:
                por_pagina.setdefault(p, []).append((ln, w))
            for p, items in por_pagina.items():
                page = pdf[p - 1]
                giro = (doc.pages[p - 1].meta or {}).get("giro", 0)
                imgs = {}
                for dpi in dpis:
                    g = imagen.render(page, imagen.dpi_seguro(page, dpi))
                    imgs[dpi] = imagen.girar90(g, giro) if giro else g
                for ln, w in items:
                    lecturas = []
                    for dpi, g in imgs.items():
                        h, ww = g.shape[:2]
                        x0, y0, x1, y1 = w.bbox
                        mx, my = 0.012, 0.008
                        rec = g[max(0, int((y0 - my) * h)):min(h, int((y1 + my) * h)),
                                max(0, int((x0 - mx) * ww)):min(ww, int((x1 + mx) * ww))]
                        if rec.size == 0:
                            continue
                        t = pytesseract.image_to_string(
                            rec, config="--psm 7 -c tessedit_char_whitelist=0123456789-/.").strip()
                        lecturas.append(re.sub(r"\s+", "", t))
                    nuevo = lecturas[0] if lecturas and all(x == lecturas[0] for x in lecturas) else ""
                    viejo = re.sub(r"[^\d\-/.]", "", w.text)
                    if nuevo and nuevo != viejo and _forma(nuevo) == _forma(viejo):
                        ln.text = ln.text.replace(viejo, nuevo, 1) if viejo in ln.text else ln.text
                        w.text = w.text.replace(viejo, nuevo, 1)
                        w.conf, w.votos = max(w.conf or 0, 0.9), 2
                        cambios.append({"pagina": p, "antes": viejo, "despues": nuevo})
                    elif nuevo and nuevo == viejo:
                        w.conf, w.votos = max(w.conf or 0, 0.9), 2          # confirmada
    except Exception:
        return cambios
    return cambios
