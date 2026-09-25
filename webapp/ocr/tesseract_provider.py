# -*- coding: utf-8 -*-
"""OCR LOCAL (Tesseract) — funciona sin Azure, sin nube y sin costo.

Mismo contrato que el proveedor de Azure: analyze(pdf) -> OCRDocument, así que
el resto del programa (segmentación, riesgos, cortes) no cambia en nada.

Por página:
  1) Se dibuja la hoja con PyMuPDF respetando la rotación del escaneo.
  2) Se lee con Tesseract en español, pidiendo posición y confianza por palabra.
  3) Si la página queda por debajo del umbral, se vuelve a dibujar más grande
     (350 y 450 DPI) y se relee; se conserva la mejor lectura.

Las páginas se procesan EN PARALELO (Tesseract corre como programa aparte), que
es lo que hace usable el modo local en un expediente de 40–50 hojas.

Requisitos en la PC:
  · pip install pytesseract pymupdf numpy   (opcional: opencv-python-headless)
  · el programa Tesseract instalado, con el idioma español (spa).
    Windows: https://github.com/UB-Mannheim/tesseract/wiki  (marcar "Spanish")
"""
from __future__ import annotations
import os, glob, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import pymupdf
from .base import OCRWord, OCRLine, OCRPage, OCRDocument, OCRProvider

try:
    import numpy as np
    import pytesseract
    _OK = True
except Exception:
    _OK = False
try:
    import cv2                      # opcional: solo para enderezar la hoja
    _CV2 = True
except Exception:
    _CV2 = False

_WIN = [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")]


def buscar_tesseract():
    """Ubica el programa Tesseract (PATH o instalación típica de Windows)."""
    if os.getenv("TESSERACT_CMD"):
        return os.getenv("TESSERACT_CMD")
    p = shutil.which("tesseract")
    if p:
        return p
    for c in _WIN:
        if os.path.exists(c):
            return c
    return None


def idiomas_disponibles(cmd=None):
    base = os.getenv("TESSDATA_PREFIX")
    dirs = [base] if base else []
    if cmd:
        dirs.append(os.path.join(os.path.dirname(cmd), "tessdata"))
    dirs += ["/usr/share/tesseract-ocr/5/tessdata", "/usr/share/tesseract-ocr/4.00/tessdata",
             "/usr/share/tessdata"]
    idiomas = set()
    for d in dirs:
        if d and os.path.isdir(d):
            for f in glob.glob(os.path.join(d, "*.traineddata")):
                idiomas.add(os.path.splitext(os.path.basename(f))[0])
    return idiomas


def estado_local():
    """Diagnóstico para la pantalla de configuración."""
    cmd = buscar_tesseract()
    idis = idiomas_disponibles(cmd)
    return {"librerias": _OK, "programa": cmd, "idiomas": sorted(idis),
            "espanol": "spa" in idis,
            "listo": bool(_OK and cmd and ("spa" in idis or "eng" in idis))}


def _a_gris(pix):
    buf = np.frombuffer(pix.samples, np.uint8)
    if pix.n == 1:
        return buf.reshape(pix.height, pix.width)
    img = buf.reshape(pix.height, pix.width, pix.n)[:, :, :3].astype(np.uint16)
    return ((img[:, :, 0] * 299 + img[:, :, 1] * 587 + img[:, :, 2] * 114) // 1000).astype(np.uint8)


def _enderezar(gris):
    if not _CV2:
        return gris
    try:
        thr = cv2.threshold(cv2.bitwise_not(gris), 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        pts = np.column_stack(np.where(thr > 0))
        if pts.shape[0] < 50:
            return gris
        ang = cv2.minAreaRect(pts)[-1]
        ang = -(90 + ang) if ang < -45 else -ang
        if abs(ang) < 0.4 or abs(ang) > 15:
            return gris
        h, w = gris.shape
        M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
        return cv2.warpAffine(gris, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    except Exception:
        return gris


class TesseractProvider(OCRProvider):
    name = "tesseract-local"

    def __init__(self, idiomas=None, dpi=None, tessdata=None, deskew=True):
        est = estado_local()
        if not est["listo"]:
            falta = ("las librerías (pip install pytesseract numpy)" if not _OK
                     else "el programa Tesseract" if not est["programa"]
                     else "el idioma español (spa.traineddata)")
            raise RuntimeError(f"OCR local no disponible: falta {falta}.")
        self.cmd = est["programa"]
        pytesseract.pytesseract.tesseract_cmd = self.cmd
        self.idiomas = idiomas or os.getenv("OCR_IDIOMAS") or ("spa" if est["espanol"] else "eng")
        self.dpi = int(dpi or os.getenv("OCR_DPI", "220"))
        self.tessdata = tessdata or os.getenv("TESSDATA_PREFIX")
        self.deskew = deskew
        self.min_conf = float(os.getenv("OCR_MIN_CONF", "0.90"))
        self.relectura = os.getenv("OCR_RELECTURA", "1") != "0"
        self.concurrencia = max(1, int(os.getenv("OCR_CONCURRENCIA", str(min(4, (os.cpu_count() or 2))))))

    # ------------------------------------------------------------------------
    def _config(self, psm=4):
        c = f"--oem 1 --psm {psm}"
        if self.tessdata:
            c += f' --tessdata-dir "{self.tessdata}"'
        return c

    def _leer(self, pdf_path, numero, dpi, realzar=False) -> OCRPage:
        with pymupdf.open(pdf_path) as doc:
            page = doc[numero - 1]
            W, H = page.rect.width or 1, page.rect.height or 1
            pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        gris = _a_gris(pix)
        if self.deskew:
            gris = _enderezar(gris)
        if realzar:
            a = gris.astype(np.float32)
            p2, p98 = np.percentile(a, 2), np.percentile(a, 98)
            if p98 > p2:
                gris = np.clip((a - p2) * 255.0 / (p98 - p2), 0, 255).astype(np.uint8)
        alto, ancho = gris.shape
        d = pytesseract.image_to_data(gris, lang=self.idiomas, config=self._config(),
                                      output_type=pytesseract.Output.DICT)
        grupos = {}
        for k in range(len(d["text"])):
            txt = (d["text"][k] or "").strip()
            if not txt:
                continue
            conf = float(d["conf"][k]); conf = 0.0 if conf < 0 else conf / 100.0
            x, y, w, h = d["left"][k], d["top"][k], d["width"][k], d["height"][k]
            pal = OCRWord(text=txt, conf=conf, page=numero,
                          bbox=(x / ancho, y / alto, (x + w) / ancho, (y + h) / alto))
            grupos.setdefault((d["block_num"][k], d["par_num"][k], d["line_num"][k]), []).append(pal)
        lineas = []
        for clave in sorted(grupos):
            ps = grupos[clave]
            lineas.append(OCRLine(
                text=" ".join(p.text for p in ps),
                conf=sum(p.conf for p in ps) / len(ps),
                bbox=(min(p.bbox[0] for p in ps), min(p.bbox[1] for p in ps),
                      max(p.bbox[2] for p in ps), max(p.bbox[3] for p in ps)),
                page=numero, words=ps))
        return OCRPage(number=numero, width_pt=W, height_pt=H, rotation=0, lines=lineas)

    def _pagina(self, pdf_path, numero) -> tuple:
        """Lee una página y, si queda floja, la relee más grande."""
        mejor = self._leer(pdf_path, numero, self.dpi)
        antes = _conf(mejor)
        if self.relectura and antes < self.min_conf and _pal(mejor) > 0:
            for dpi, realzar in ((350, False), (450, True)):
                try:
                    otra = self._leer(pdf_path, numero, dpi, realzar)
                    if _puntaje(otra) > _puntaje(mejor):
                        mejor = otra
                    if _conf(mejor) >= self.min_conf:
                        break
                except Exception:
                    break
        return mejor, antes

    def analyze(self, pdf_path: str, progreso=None) -> OCRDocument:
        with pymupdf.open(pdf_path) as doc:
            total = doc.page_count
        paginas = [None] * total
        mejoradas, hechas = [], 0
        with ThreadPoolExecutor(max_workers=min(self.concurrencia, max(1, total))) as pool:
            tareas = {pool.submit(self._pagina, pdf_path, n): n for n in range(1, total + 1)}
            for fut in as_completed(tareas):
                n = tareas[fut]
                try:
                    pg, antes = fut.result()
                except Exception:
                    pg, antes = OCRPage(number=n, width_pt=1, height_pt=1, rotation=0, lines=[]), 0.0
                paginas[n - 1] = pg
                if _conf(pg) > antes + 0.01:
                    mejoradas.append({"pagina": n, "antes": round(antes, 3), "despues": round(_conf(pg), 3)})
                hechas += 1
                if progreso:
                    progreso(hechas, total, n)
        doc = OCRDocument(provider=self.name, source_path=pdf_path, pages=paginas)
        doc.meta = {"modelo": f"tesseract {self.idiomas} @ {self.dpi}dpi",
                    "relecturas": len(mejoradas), "concurrencia": self.concurrencia,
                    "paginas_mejoradas": sorted(mejoradas, key=lambda m: m["pagina"]),
                    "paginas_bajo_umbral": [p.number for p in paginas if _conf(p) < self.min_conf],
                    "umbral": self.min_conf,
                    "confianza_por_pagina": {p.number: round(_conf(p), 3) for p in paginas}}
        return doc


def _conf(p):
    cs = [w.conf for l in p.lines for w in l.words] or [l.conf for l in p.lines]
    return sum(cs) / len(cs) if cs else 0.0


def _pal(p):
    return sum(len(l.words) for l in p.lines)


def _puntaje(p):
    return _conf(p) * (1 + 0.5 * min(_pal(p), 600) / 600)
