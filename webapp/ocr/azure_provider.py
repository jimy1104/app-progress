# -*- coding: utf-8 -*-
"""OCR de producción — Azure AI Document Intelligence, con RELECTURA.

Los expedientes llegan escaneados a ~96 DPI (la mitad de lo recomendado), y en
las hojas con sellos y firmas la lectura cae mucho. Por eso el OCR se hace en
dos pasadas:

  1ª  Se envía el PDF completo (rápido, una sola llamada).
  2ª  Las páginas que quedaron por debajo del umbral se vuelven a enviar UNA POR
      UNA, redibujadas en alta resolución (300 y 400 DPI, en escala de grises y
      con el contraste realzado). De cada intento se conserva la MEJOR lectura.

Medido sobre un expediente real: una orden de servicio con sellos pasó de 47% a
77% de confianza y de 279 a 430 palabras leídas. En páginas que ya se leían bien
la relectura no cambia nada (y si sale peor, se descarta).

Tarda más, a propósito: el objetivo es la exactitud, no la rapidez.
"""
from __future__ import annotations
import io, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from .base import OCRWord, OCRLine, OCRPage, OCRDocument, OCRProvider
import config


def _poly_a_bbox(polygon, pw, ph):
    if not polygon:
        return (0.0, 0.0, 1.0, 0.05)
    xs = polygon[0::2]; ys = polygon[1::2]
    return (min(xs) / pw, min(ys) / ph, max(xs) / pw, max(ys) / ph)


def _confianza(pagina: OCRPage) -> float:
    confs = [w.conf for l in pagina.lines for w in l.words] or [l.conf for l in pagina.lines]
    return sum(confs) / len(confs) if confs else 0.0


def _palabras(pagina: OCRPage) -> int:
    return sum(len(l.words) or len(l.text.split()) for l in pagina.lines)


def _puntaje(pagina: OCRPage) -> float:
    """Confianza ponderada por cuántas palabras se leyeron: una página donde se
    leen 430 palabras al 77% es mejor lectura que una con 279 al 47%."""
    return _confianza(pagina) * (1 + 0.5 * min(_palabras(pagina), 600) / 600)


class AzureDocIntelligenceProvider(OCRProvider):
    name = "azure-document-intelligence"

    def __init__(self, endpoint=None, modelo=None, locale=None):
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from secrets_azure import resolver_credencial
        self.endpoint = endpoint or config.AZURE_DI_ENDPOINT
        self.modelo = modelo or config.AZURE_DI_MODELO
        self.locale = locale or getattr(config, "AZURE_DI_LOCALE", "es")
        self.min_conf = float(os.getenv("OCR_MIN_CONF", "0.90"))
        self.relectura = os.getenv("OCR_RELECTURA", "1") != "0"
        self.max_relecturas = int(os.getenv("OCR_MAX_RELECTURAS", "60"))
        # Las relecturas son llamadas independientes: se hacen en paralelo.
        # 4 a la vez va cómodo dentro de los límites del nivel S0 de Azure.
        self.concurrencia = max(1, int(os.getenv("OCR_CONCURRENCIA", "4")))
        credencial, self.cred_desc = resolver_credencial()
        self.client = DocumentIntelligenceClient(endpoint=self.endpoint, credential=credencial)

    # ------------------------------------------------------------ llamadas ---
    def _analizar(self, datos: bytes, content_type="application/octet-stream"):
        poller = self.client.begin_analyze_document(
            self.modelo, body=io.BytesIO(datos), locale=self.locale, content_type=content_type)
        return poller.result()

    def _a_paginas(self, resultado, offset=0):
        paginas = []
        for pg in resultado.pages:
            pw, ph = (pg.width or 1.0), (pg.height or 1.0)
            palabras = list(pg.words or [])
            lineas = []
            for ln in (pg.lines or []):
                dentro = [w for w in palabras if _solapa(w, ln)]
                conf = sum((w.confidence or 0) for w in dentro) / len(dentro) if dentro else 0.85
                lineas.append(OCRLine(
                    text=ln.content, conf=conf, bbox=_poly_a_bbox(ln.polygon, pw, ph),
                    page=pg.page_number + offset,
                    words=[OCRWord(text=w.content, conf=(w.confidence or 0),
                                   bbox=_poly_a_bbox(w.polygon, pw, ph),
                                   page=pg.page_number + offset) for w in dentro]))
            paginas.append(OCRPage(number=pg.page_number + offset, width_pt=pw, height_pt=ph,
                                   rotation=int(getattr(pg, "angle", 0) or 0), lines=lineas))
        return paginas

    # ------------------------------------------------------- alta resolución --
    def _render(self, pdf_path, num, dpi, realzar):
        import pymupdf
        with pymupdf.open(pdf_path) as doc:
            pix = doc[num - 1].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
            png = pix.tobytes("png")
        if not realzar:
            return png
        try:
            import numpy as np
            arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width).astype(np.float32)
            p2, p98 = np.percentile(arr, 2), np.percentile(arr, 98)
            if p98 > p2:
                arr = np.clip((arr - p2) * 255.0 / (p98 - p2), 0, 255)
            import pymupdf
            pm = pymupdf.Pixmap(pymupdf.csGRAY, pix.width, pix.height, arr.astype(np.uint8).tobytes(), 0)
            return pm.tobytes("png")
        except Exception:
            return png

    def _releer(self, pdf_path, pagina: OCRPage) -> OCRPage:
        """Reintenta una página floja en alta resolución; devuelve la mejor lectura."""
        mejor = pagina
        for dpi, realzar in ((300, False), (400, True)):
            try:
                png = self._render(pdf_path, pagina.number, dpi, realzar)
                nuevas = self._a_paginas(self._analizar(png, "image/png"), offset=pagina.number - 1)
                if nuevas and _puntaje(nuevas[0]) > _puntaje(mejor):
                    nuevas[0].number = pagina.number
                    mejor = nuevas[0]
                if _confianza(mejor) >= self.min_conf:
                    break
            except Exception:
                continue
        return mejor

    # ---------------------------------------------------------------- API ----
    def analyze(self, pdf_path: str, progreso=None) -> OCRDocument:
        """progreso: función opcional (hechas, total, pagina) para informar avance."""
        paginas = self._a_paginas(self._analizar(open(pdf_path, "rb").read()))
        releidas, mejoradas = [], []
        if self.relectura:
            flojas = [p for p in paginas if _confianza(p) < self.min_conf and _palabras(p) > 0]
            flojas.sort(key=_confianza)                       # primero las peores
            flojas = flojas[:self.max_relecturas]
            total, hechas = len(flojas), 0
            if progreso and total:
                progreso(0, total, None)
            with ThreadPoolExecutor(max_workers=min(self.concurrencia, max(1, total))) as pool:
                tareas = {pool.submit(self._releer, pdf_path, p): p for p in flojas}
                for fut in as_completed(tareas):
                    p = tareas[fut]
                    releidas.append(p.number)
                    hechas += 1
                    try:
                        nueva = fut.result()
                    except Exception:
                        nueva = p
                    if nueva is not p:
                        antes = _confianza(p)
                        paginas[p.number - 1] = nueva
                        mejoradas.append({"pagina": p.number, "antes": round(antes, 3),
                                          "despues": round(_confianza(nueva), 3)})
                    if progreso:
                        progreso(hechas, total, p.number)
        doc = OCRDocument(provider=self.name, source_path=pdf_path, pages=paginas)
        doc.meta = {"modelo": self.modelo, "relecturas": len(releidas),
                    "concurrencia": self.concurrencia,
                    "paginas_mejoradas": sorted(mejoradas, key=lambda m: m["pagina"]),
                    "paginas_bajo_umbral": [p.number for p in paginas if _confianza(p) < self.min_conf],
                    "umbral": self.min_conf,
                    "confianza_por_pagina": {p.number: round(_confianza(p), 3) for p in paginas}}
        return doc


def _solapa(palabra, linea):
    try:
        spans = (palabra.span,) if hasattr(palabra, "span") else palabra.spans
        for ws in spans:
            for s in (linea.spans or []):
                if not (ws.offset + ws.length <= s.offset or s.offset + s.length <= ws.offset):
                    return True
    except Exception:
        return False
    return False
