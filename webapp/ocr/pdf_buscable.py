# -*- coding: utf-8 -*-
"""PDF BUSCABLE: el escaneo original con una capa de texto invisible (la lectura
del motor), para poder buscar (Ctrl+F), seleccionar y copiar el texto.

Ojo con los PDF que pasan por Nitro: su «OCR» no es una capa invisible, sino que
REDIBUJA las letras del escaneo como glifos vectoriales (fuentes Type3, estilo
ClearScan) con un texto Unicode mal reconocido detrás («MUNICIOA LDAD»). Esos
glifos SON lo que se ve: si se borraran, la hoja quedaría desteñida. Por eso:
  · capa invisible ajena (modo 3, GlyphLessFont) -> se borra y se reemplaza;
  · texto visible (Type3 de Nitro o texto digital) -> se conserva, y la nuestra
    se agrega encima, invisible.
Las hojas digitales (texto nativo) se dejan tal cual: ya son exactas.
"""
from __future__ import annotations
import pymupdf


def _capa_invisible(page) -> bool:
    """¿Todo el texto existente de la hoja es invisible? (solo entonces se puede
    borrar sin alterar lo que se ve)."""
    try:
        tt = page.get_texttrace()
    except Exception:
        return False
    return bool(tt) and all(sp.get("type") == 3 or sp.get("opacity", 1) == 0 for sp in tt)


def _borrar_texto(page):
    """Quita la capa de texto (no las imágenes ni los dibujos) de toda la hoja."""
    try:
        page.add_redact_annot(page.mediabox, fill=False)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                              graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                              text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    except Exception:
        pass


def escribir_capa(page, ocr_page):
    """Escribe las palabras de ocr_page (bbox en fracciones de la hoja como se ve)
    como texto invisible sobre la hoja PDF."""
    from .imagen import des_girar90_bbox
    W, H = page.rect.width, page.rect.height
    derot = page.derotation_matrix
    giro = (ocr_page.meta or {}).get("giro", 0)
    forma = page.new_shape()        # todas las palabras en UN solo flujo de contenido
    for ln in ocr_page.lines:
        for w in (ln.words or []):
            txt = (w.text or "").strip()
            if not txt:
                continue
            b = des_girar90_bbox(w.bbox, giro) if giro else w.bbox     # marco derecho -> como se ve
            x0, y0, x1, y1 = b[0] * W, b[1] * H, b[2] * W, b[3] * H
            alto = max(2.0, y1 - y0)
            fs = max(3.0, min(40.0, alto * 0.95))
            # la línea base, en coordenadas de la hoja SIN girar (así las pide el PDF)
            base = pymupdf.Point(x0, y1 - alto * 0.2) * derot
            try:
                forma.insert_text(base, txt, fontsize=fs, fontname="helv", render_mode=3,
                                  rotate=page.rotation)
            except Exception:
                continue
    forma.commit()


def hacer_buscable(pdf_path, ocr_doc, paginas=None) -> pymupdf.Document:
    """Devuelve un Document nuevo con la capa de texto. 'paginas': solo esas hojas."""
    doc = pymupdf.open(pdf_path)
    for pg in ocr_doc.pages:
        if paginas and pg.number not in paginas:
            continue
        meta = pg.meta or {}
        if meta.get("fuente") == "texto-nativo" or pg.number > doc.page_count:
            continue
        page = doc[pg.number - 1]
        if _capa_invisible(page):
            _borrar_texto(page)
        if not meta.get("en_blanco"):
            escribir_capa(page, pg)
    return doc


def texto_plano(ocr_doc, segmentos=None) -> str:
    """Todo el texto del expediente, hoja por hoja, con el documento de cada hoja."""
    doc_de = {}
    for s in segmentos or []:
        for p in range(s.pagina_ini, s.pagina_fin + 1):
            doc_de[p] = s.etiqueta
    partes = []
    for pg in ocr_doc.pages:
        meta = pg.meta or {}
        cab = f"===== Hoja {pg.number}"
        if pg.number in doc_de:
            cab += f" · {doc_de[pg.number]}"
        if meta.get("en_blanco"):
            cab += " · (en blanco)"
        partes.append(cab + " =====")
        partes.append(pg.text)
    return "\n".join(partes) + "\n"
