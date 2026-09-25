# -*- coding: utf-8 -*-
"""Cómo de BUENA fue la lectura, medido con honestidad.

La cifra antigua («lectura OCR 87%») era el promedio de la confianza de TODOS los
renglones, incluidas las manchas de las hojas en blanco, los garabatos de las
firmas y las esquinas de los sellos. Eso mezcla dos cosas distintas: texto que
se leyó mal y cosas que ni siquiera son texto.

Aquí se cuenta solo el TEXTO (palabras con letras o números, fuera de hojas en
blanco y de trazos manuscritos) y se separa en:
  · segura     : confianza alta, o confirmada por dos lecturas independientes
  · dudosa     : el resto → se señala la hoja para revisión humana

«lectura_pct» = % de palabras de texto que quedaron seguras. Si una hoja baja
del objetivo, se lista en «paginas_revisar»: el sistema nunca calla una duda.
"""
from __future__ import annotations
import os, re

CONF_SEGURA = float(os.getenv("OCR_CONF_SEGURA", "0.85"))
CONF_SEGURA_VOTADA = float(os.getenv("OCR_CONF_SEGURA_VOTADA", "0.70"))
OBJETIVO_PAGINA = float(os.getenv("OCR_OBJETIVO_PAGINA", "0.95"))
_TEXTO = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]")


def es_texto(w) -> bool:
    return bool(_TEXTO.search(w.text or ""))


def segura(w) -> bool:
    return w.conf >= CONF_SEGURA or (getattr(w, "votos", 1) >= 2 and w.conf >= CONF_SEGURA_VOTADA)


def palabras_texto(pg):
    if (pg.meta or {}).get("en_blanco"):
        return []
    return [w for ln in pg.lines if not ln.manuscrita for w in ln.words if es_texto(w)]


def calidad_pagina(pg) -> dict:
    ws = palabras_texto(pg)
    if not ws:
        return {"palabras": 0, "seguras": 0, "pct": None, "conf": None,
                "en_blanco": bool((pg.meta or {}).get("en_blanco"))}
    seg = sum(1 for w in ws if segura(w))
    return {"palabras": len(ws), "seguras": seg, "pct": round(seg / len(ws), 4),
            "conf": round(sum(w.conf for w in ws) / len(ws), 4),
            "verificadas": sum(1 for w in ws if getattr(w, "votos", 1) >= 2),
            "en_blanco": False}


def calidad_documento(doc) -> dict:
    por_pag = {pg.number: calidad_pagina(pg) for pg in doc.pages}
    tot = sum(c["palabras"] for c in por_pag.values())
    seg = sum(c["seguras"] for c in por_pag.values())
    conf = (sum((c["conf"] or 0) * c["palabras"] for c in por_pag.values()) / tot) if tot else 0.0
    # confianza «a la antigua» (todas las líneas), solo para comparar
    confs = [l.conf for p in doc.pages for l in p.lines]
    return {
        "lectura_pct": round(seg / tot, 4) if tot else 0.0,
        "conf_texto": round(conf, 4),
        "conf_bruta": round(sum(confs) / len(confs), 4) if confs else 0.0,
        "palabras": tot, "seguras": seg,
        "verificadas": sum(c.get("verificadas", 0) for c in por_pag.values()),
        "hojas_en_blanco": [n for n, c in por_pag.items() if c["en_blanco"]],
        "paginas_revisar": [n for n, c in por_pag.items()
                            if c["pct"] is not None and c["pct"] < OBJETIVO_PAGINA],
        "objetivo_pagina": OBJETIVO_PAGINA,
        "por_pagina": {n: c["pct"] for n, c in por_pag.items()},
    }
