# -*- coding: utf-8 -*-
"""Proveedor de PRUEBAS: construye un OCRDocument desde la capa de texto del PDF.

No se usa en producción (allí manda Azure). Sirve para probar la segmentación y
la detección de riesgos con un texto tan ruidoso como el del OCR, sin gastar
llamadas a Azure y sin depender de la red.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pymupdf
from ocr.base import OCRWord, OCRLine, OCRPage, OCRDocument, OCRProvider


class PdfTextProvider(OCRProvider):
    name = "capa-texto-pdf (pruebas)"

    def analyze(self, pdf_path: str) -> OCRDocument:
        doc = pymupdf.open(pdf_path)
        pages = []
        for i, page in enumerate(doc):
            # get_text() entrega coordenadas SIN rotar; la página se muestra rotada.
            M = page.rotation_matrix
            W, H = page.rect.width or 1, page.rect.height or 1
            lines = []
            for blk in page.get_text("dict").get("blocks", []):
                for ln in blk.get("lines", []):
                    txt = "".join(s.get("text", "") for s in ln.get("spans", [])).strip()
                    if not txt:
                        continue
                    r = pymupdf.Rect(ln["bbox"]) * M
                    bbox = (min(r.x0, r.x1) / W, min(r.y0, r.y1) / H,
                            max(r.x0, r.x1) / W, max(r.y0, r.y1) / H)
                    lines.append(OCRLine(text=txt, conf=0.9, bbox=bbox, page=i + 1,
                                         words=[OCRWord(text=w, conf=0.9, bbox=bbox, page=i + 1)
                                                for w in txt.split()]))
            lines.sort(key=lambda l: (round(l.bbox[1], 3), l.bbox[0]))
            pages.append(OCRPage(number=i + 1, width_pt=W, height_pt=H,
                                 rotation=page.rotation, lines=lines))
        doc.close()
        return OCRDocument(provider=self.name, source_path=pdf_path, pages=pages)
