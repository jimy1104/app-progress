# -*- coding: utf-8 -*-
"""Cliente SIMULADO de Azure Document Intelligence, para pruebas sin llaves.

Recibe exactamente lo que el proveedor real enviaría (el PDF completo o los lotes
de imágenes limpias), lo lee con Tesseract y devuelve un objeto con la MISMA forma
que el AnalyzeResult del SDK: pages[].words/lines con polygon, span(s),
confidence; paragraphs[].role; styles[].is_handwritten; barcodes.

Con sin_girar=True imita el caso en que Azure entrega las coordenadas de una hoja
con /Rotate en la orientación del papel SIN girar (lo que obligó al truco de
jobs.pagina_png), para comprobar que el proveedor las devuelve a la vista.
"""
import io, os, sys, re
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pymupdf
import pytesseract
from ocr import imagen

os.environ.setdefault("OMP_THREAD_LIMIT", "1")


class _Poller:
    def __init__(self, r): self._r = r
    def result(self): return self._r


class ClienteSimulado:
    def __init__(self, sin_girar=False, dpi=200, conf_primera=1.0):
        self.sin_girar, self.dpi, self.conf_primera = sin_girar, dpi, conf_primera
        self.llamadas = []            # (paginas, features) de cada llamada, para las pruebas

    def begin_analyze_document(self, modelo, body, locale=None, content_type=None, features=None, **kw):
        datos = body.read() if hasattr(body, "read") else body
        doc = pymupdf.open(stream=datos, filetype="pdf")
        self.llamadas.append((doc.page_count, list(features or [])))
        content, pages, paragraphs = "", [], []
        for i, page in enumerate(doc):
            gris = imagen.render(page, self.dpi)
            alto, ancho = gris.shape
            W, H = page.rect.width / 72.0, page.rect.height / 72.0          # pulgadas, como Azure
            girar = self.sin_girar and page.rotation in (90, 270)
            M = page.derotation_matrix if girar else None
            w0, h0 = (page.mediabox.width / 72.0, page.mediabox.height / 72.0) if girar else (W, H)
            d = pytesseract.image_to_data(gris, lang="spa", config="--oem 1 --psm 3",
                                          output_type=pytesseract.Output.DICT)
            grupos = {}
            for k in range(len(d["text"])):
                t = (d["text"][k] or "").strip()
                if not t:
                    continue
                x, y, w, h = d["left"][k], d["top"][k], d["width"][k], d["height"][k]
                x0, y0, x1, y1 = x / ancho * W, y / alto * H, (x + w) / ancho * W, (y + h) / alto * H
                if girar:
                    r = pymupdf.Rect(x0 * 72, y0 * 72, x1 * 72, y1 * 72) * M
                    x0, y0, x1, y1 = r.x0 / 72, r.y0 / 72, r.x1 / 72, r.y1 / 72
                c = max(0.0, float(d["conf"][k])) / 100.0
                if not self.llamadas[:-1]:            # primera llamada = PDF completo
                    c *= self.conf_primera
                grupos.setdefault((d["block_num"][k], d["par_num"][k], d["line_num"][k]), []).append(
                    (t, c, [x0, y0, x1, y0, x1, y1, x0, y1]))
            words, lines = [], []
            for clave in sorted(grupos):
                ini_linea = len(content)
                for t, c, poly in grupos[clave]:
                    off = len(content)
                    content += t + " "
                    words.append(NS(content=t, polygon=poly, span=NS(offset=off, length=len(t)), confidence=c))
                largo = len(content) - ini_linea - 1
                xs = [p for _, _, pl in grupos[clave] for p in pl[0::2]]
                ys = [p for _, _, pl in grupos[clave] for p in pl[1::2]]
                texto = " ".join(t for t, _, _ in grupos[clave])
                poly = [min(xs), min(ys), max(xs), min(ys), max(xs), max(ys), min(xs), max(ys)]
                lines.append(NS(content=texto, polygon=poly, spans=[NS(offset=ini_linea, length=largo)]))
                # títulos: renglón corto, en mayúsculas, en el tercio superior
                yc = (min(ys) + max(ys)) / 2 / (h0 if girar else H)
                if texto.isupper() and 8 <= len(texto) <= 60 and yc < 0.33:
                    paragraphs.append(NS(role="title", content=texto,
                                         spans=[NS(offset=ini_linea, length=largo)]))
                content = content[:-1] + "\n"
            pw, ph = (w0, h0) if girar else (W, H)
            # en el papel SIN girar, el texto de una hoja con /Rotate r está girado -r
            ang = float(((-page.rotation + 180) % 360) - 180) if girar else 0.0
            pages.append(NS(page_number=i + 1, width=pw, height=ph, unit="inch", angle=ang,
                            words=words, lines=lines, barcodes=[], spans=[]))
        doc.close()
        return _Poller(NS(content=content, pages=pages, paragraphs=paragraphs, styles=[],
                          model_id=modelo))
