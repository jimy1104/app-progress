# -*- coding: utf-8 -*-
"""Texto NATIVO del PDF: cuando una hoja es digital (factura descargada de SUNAT,
reporte impreso a PDF desde el SIGA, consulta RUC), su capa de texto es exacta al
100% y no hace falta adivinar nada con OCR.

Pero no toda capa de texto es confiable: los escáneres (Nitro, Adobe, ABBYY)
agregan una capa INVISIBLE hecha con su propio OCR, muchas veces de mala calidad
(«MUNICIOA LDAD», «4UNIOIPA LIO AD»). Esa se descarta: se reconoce porque el
texto se pinta en modo invisible (render mode 3) o con la fuente GlyphLessFont.
"""
from __future__ import annotations
import re
import pymupdf
from .base import OCRWord, OCRLine, OCRPage

_LETRAS = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,}")


def diagnostico(page) -> dict:
    """¿La capa de texto de esta hoja es digital de verdad?"""
    visibles = invisibles = 0
    try:
        for sp in page.get_texttrace():
            n = len(sp.get("chars", ()))
            if sp.get("type") == 3 or sp.get("opacity", 1) == 0:
                invisibles += n
            else:
                visibles += n
    except Exception:
        visibles = len(page.get_text("text") or "")
    fuentes = " ".join(f[3] for f in page.get_fonts(full=False)) if hasattr(page, "get_fonts") else ""
    glyphless = "GlyphLess" in fuentes
    texto = page.get_text("text") or ""
    palabras = _LETRAS.findall(texto)
    area = abs(page.rect.width * page.rect.height) or 1.0
    cobertura_img = 0.0
    try:
        for im in page.get_images(full=True):
            for r in page.get_image_rects(im[0]):
                cobertura_img = max(cobertura_img, abs(r.width * r.height) / area)
    except Exception:
        pass
    # Si un escaneo tapa toda la hoja, el texto que hay debajo (o invisible) lo puso
    # el OCR del escáner: no es texto digital y no se confía en él.
    capa_ocr_ajena = cobertura_img >= 0.9 or glyphless or invisibles > visibles
    digital = (visibles >= 40 and not capa_ocr_ajena and len(palabras) >= 5)
    return {"visibles": visibles, "invisibles": invisibles, "glyphless": glyphless,
            "palabras": len(palabras), "cobertura_imagen": round(min(1.0, cobertura_img), 3),
            "digital": digital, "capa_ocr_ajena": bool(capa_ocr_ajena and (visibles + invisibles) > 0),
            # hoja 100% digital (sin escaneo debajo): se usa su texto y no se hace OCR
            "solo_texto": digital and cobertura_img < 0.5}


def leer(page, numero: int, conf: float = 0.995) -> OCRPage:
    """OCRPage desde la capa de texto, con coordenadas ya giradas como se ve la hoja."""
    M = page.rotation_matrix
    W, H = page.rect.width or 1, page.rect.height or 1
    grupos = {}
    for x0, y0, x1, y1, txt, b, l, _ in page.get_text("words"):
        if not txt.strip():
            continue
        r = pymupdf.Rect(x0, y0, x1, y1) * M
        bbox = (max(0.0, min(r.x0, r.x1) / W), max(0.0, min(r.y0, r.y1) / H),
                min(1.0, max(r.x0, r.x1) / W), min(1.0, max(r.y0, r.y1) / H))
        grupos.setdefault((b, l), []).append(OCRWord(text=txt, conf=conf, bbox=bbox, page=numero, votos=2))
    lineas = []
    for ws in grupos.values():
        ws.sort(key=lambda w: w.bbox[0])
        lineas.append(OCRLine(text=" ".join(w.text for w in ws), conf=conf,
                              bbox=(min(w.bbox[0] for w in ws), min(w.bbox[1] for w in ws),
                                    max(w.bbox[2] for w in ws), max(w.bbox[3] for w in ws)),
                              page=numero, words=ws))
    lineas.sort(key=lambda l: (round(l.bbox[1], 3), l.bbox[0]))
    return OCRPage(number=numero, width_pt=W, height_pt=H, rotation=page.rotation, lines=lineas,
                   meta={"fuente": "texto-nativo"})
