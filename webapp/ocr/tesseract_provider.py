# -*- coding: utf-8 -*-
"""OCR LOCAL (Tesseract) — funciona sin Azure, sin nube y sin costo.

Mismo contrato que el proveedor de Azure: analyze(pdf) -> OCRDocument, así que
el resto del programa (segmentación, riesgos, cortes) no cambia en nada.

Por página:
  0) Si la hoja es digital (texto nativo confiable), se usa ese texto: 100% exacto.
  1) Se dibuja a 300 DPI y se LIMPIA (fondo aplanado, sin transparencias del
     reverso, enderezada). Ver ocr/imagen.py.
  2) Si la hoja no tiene tinta real, es un reverso en blanco: no se lee (así no
     aparecen cientos de palabras basura).
  3) Se lee la imagen limpia. Si quedan palabras dudosas, se lee también la
     variante SIN SELLOS y el escaneo original, y las lecturas se FUSIONAN palabra
     por palabra (ocr/fusion.py): lo que coincide queda verificado.

Las páginas se procesan EN PARALELO. Cada Tesseract corre con un solo hilo
interno (OMP_THREAD_LIMIT=1): con hilos anidados una hoja podía tardar 15 minutos.

Requisitos en la PC:
  · pip install pytesseract pymupdf numpy opencv-python-headless
  · el programa Tesseract instalado, con el idioma español (spa).
    Windows: https://github.com/UB-Mannheim/tesseract/wiki  (marcar "Spanish")
"""
from __future__ import annotations
import os, glob, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import pymupdf
from .base import OCRWord, OCRLine, OCRPage, OCRDocument, OCRProvider
from . import imagen, nativo, fusion, calidad

os.environ.setdefault("OMP_THREAD_LIMIT", "1")

try:
    import numpy as np
    import pytesseract
    _OK = True
except Exception:
    _OK = False

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
        self.dpi = int(dpi or os.getenv("OCR_DPI", str(imagen.DPI_OCR)))
        self.tessdata = tessdata or os.getenv("TESSDATA_PREFIX")
        self.deskew = deskew
        self.relectura = os.getenv("OCR_RELECTURA", "1") != "0"
        self.objetivo = calidad.OBJETIVO_PAGINA
        self.concurrencia = max(1, int(os.getenv("OCR_CONCURRENCIA", str(min(4, (os.cpu_count() or 2))))))
        self.timeout = int(os.getenv("OCR_TIMEOUT_PAGINA", "180"))

    # ------------------------------------------------------------------------
    def _config(self, psm):
        c = f"--oem 1 --psm {psm} --dpi {self.dpi} -c preserve_interword_spaces=1"
        if self.tessdata:
            c += f' --tessdata-dir "{self.tessdata}"'
        return c

    def _orientacion(self, img) -> int:
        """Grados (0/90/180/270) que hay que girar la imagen para leerla derecha.
        Usa el detector de orientación de Tesseract (osd); 0 si no está o duda."""
        try:
            osd = pytesseract.image_to_osd(img, config="--psm 0 -c min_characters_to_try=10",
                                           output_type=pytesseract.Output.DICT, timeout=60)
            if float(osd.get("orientation_conf", 0)) >= 2.0:
                return int(osd.get("rotate", 0)) % 360
        except Exception:
            pass
        return 0

    def _tesseract(self, img, numero, W, H, psm=3, inv=None, etiqueta="") -> OCRPage:
        alto, ancho = img.shape[:2]
        d = pytesseract.image_to_data(img, lang=self.idiomas, config=self._config(psm),
                                      output_type=pytesseract.Output.DICT, timeout=self.timeout)
        grupos = {}
        for k in range(len(d["text"])):
            txt = (d["text"][k] or "").strip()
            if not txt:
                continue
            conf = float(d["conf"][k]); conf = 0.0 if conf < 0 else conf / 100.0
            x, y, w, h = d["left"][k], d["top"][k], d["width"][k], d["height"][k]
            bbox = imagen.des_rotar_bbox((x / ancho, y / alto, (x + w) / ancho, (y + h) / alto),
                                         inv, ancho, alto)
            grupos.setdefault((d["block_num"][k], d["par_num"][k], d["line_num"][k]), []).append(
                OCRWord(text=txt, conf=conf, page=numero, bbox=bbox))
        lineas = []
        for clave in sorted(grupos):
            ps = sorted(grupos[clave], key=lambda p: p.bbox[0])
            lineas.append(OCRLine(
                text=" ".join(p.text for p in ps),
                conf=sum(p.conf for p in ps) / len(ps),
                bbox=(min(p.bbox[0] for p in ps), min(p.bbox[1] for p in ps),
                      max(p.bbox[2] for p in ps), max(p.bbox[3] for p in ps)),
                page=numero, words=ps))
        return OCRPage(number=numero, width_pt=W, height_pt=H, rotation=0, lines=lineas,
                       meta={"lectura": etiqueta})

    def _pagina(self, pdf_path, numero):
        """Lee una hoja con todas las defensas. Devuelve (OCRPage, detalle)."""
        with pymupdf.open(pdf_path) as doc:
            page = doc[numero - 1]
            W, H = page.rect.width or 1, page.rect.height or 1
            diag = nativo.diagnostico(page)
            if diag["solo_texto"]:
                pg = nativo.leer(page, numero)
                pg.meta.update({"fuente": "texto-nativo", "lecturas": ["nativo"]})
                return pg, {"nativo": True}
            prep = imagen.preparar(page, self.dpi, enderezar=self.deskew)
            original = None
            if self.relectura:
                original = imagen.render(page, self.dpi)          # escaneo tal cual, en gris
        meta = {k: prep[k] for k in ("angulo", "en_blanco", "tinta", "color", "dpi_origen", "qr")}
        meta["fuente"] = "ocr"
        if prep["en_blanco"]:
            meta["lecturas"] = []
            return OCRPage(number=numero, width_pt=W, height_pt=H, rotation=0, lines=[], meta=meta), {}
        lecturas = [self._tesseract(prep["limpia"], numero, W, H, 3, prep["inv"], "limpia")]
        antes = calidad.calidad_pagina(lecturas[0])["pct"] or 0.0
        giro = 0
        costado = _de_costado(lecturas[0])
        if antes < 0.6 or costado:
            # ¿hoja escaneada de costado o de cabeza? se detecta y se lee DERECHA; las
            # coordenadas quedan en el marco derecho del texto (meta['giro'])
            giro = self._orientacion(prep["limpia"])
            if giro:
                with pymupdf.open(pdf_path) as doc:
                    prep_g = imagen.preparar(doc[numero - 1], self.dpi, enderezar=self.deskew, giro=giro)
                    original_g = imagen.girar90(original, giro) if original is not None else None
                Wg, Hg = (H, W) if giro in (90, 270) else (W, H)
                otra = self._tesseract(prep_g["limpia"], numero, Wg, Hg, 3, prep_g["inv"], "limpia")
                # si el texto corre en vertical y el detector de orientación lo confirma,
                # la lectura derecha vale aunque la vertical haya salido «confiada»
                exigido = fusion.puntaje(lecturas[0]) * (0.85 if costado else 1.0)
                if fusion.puntaje(otra) > exigido:
                    lecturas, prep, original, W, H = [otra], prep_g, original_g, Wg, Hg
                    antes = calidad.calidad_pagina(otra)["pct"] or 0.0
                    meta["giro"] = giro
                else:
                    giro = 0
        if self.relectura and antes < self.objetivo:
            if prep["sin_sellos"] is not None:
                lecturas.append(self._tesseract(prep["sin_sellos"], numero, W, H, 3, prep["inv"], "sin_sellos"))
            lecturas.append(self._tesseract(original, numero, W, H, 4, None, "original"))
        pg = fusion.fusionar(lecturas) if len(lecturas) > 1 else lecturas[0]
        meta["lecturas"] = [l.meta.get("lectura") for l in lecturas]
        pg.meta = meta
        despues = calidad.calidad_pagina(pg)["pct"] or 0.0
        return pg, {"antes": antes, "despues": despues, "lecturas": len(lecturas)}

    def analyze(self, pdf_path: str, progreso=None) -> OCRDocument:
        with pymupdf.open(pdf_path) as doc:
            total = doc.page_count
        paginas = [None] * total
        detalles, hechas = {}, 0
        with ThreadPoolExecutor(max_workers=min(self.concurrencia, max(1, total))) as pool:
            tareas = {pool.submit(self._pagina, pdf_path, n): n for n in range(1, total + 1)}
            for fut in as_completed(tareas):
                n = tareas[fut]
                try:
                    pg, det = fut.result()
                except Exception as e:
                    pg, det = OCRPage(number=n, width_pt=1, height_pt=1, rotation=0, lines=[],
                                      meta={"error": f"{type(e).__name__}: {e}"[:200]}), {}
                paginas[n - 1] = pg
                detalles[n] = det
                hechas += 1
                if progreso:
                    progreso(hechas, total, n)
        doc = OCRDocument(provider=self.name, source_path=pdf_path, pages=paginas)
        doc.meta = _meta_documento(doc, detalles, f"tesseract {self.idiomas} @ {self.dpi}dpi",
                                   self.concurrencia)
        return doc


def _de_costado(pg) -> bool:
    """¿El texto corre en vertical? (palabras más altas que anchas: hoja de costado)."""
    n = vert = 0
    for ln in pg.lines:
        for w in ln.words:
            if len(w.text) >= 4:
                n += 1
                ancho = (w.bbox[2] - w.bbox[0]) * pg.width_pt
                alto = (w.bbox[3] - w.bbox[1]) * pg.height_pt
                vert += alto > 1.2 * ancho
    return n >= 5 and vert >= 0.5 * n


def _meta_documento(doc, detalles, modelo, concurrencia):
    cal = calidad.calidad_documento(doc)
    mejoradas = [{"pagina": n, "antes": round(d["antes"], 3), "despues": round(d["despues"], 3)}
                 for n, d in sorted(detalles.items()) if d.get("lecturas", 1) > 1
                 and d.get("despues", 0) > d.get("antes", 0) + 0.005]
    return {"modelo": modelo, "concurrencia": concurrencia,
            "relecturas": sum(1 for d in detalles.values() if d.get("lecturas", 1) > 1),
            "paginas_mejoradas": mejoradas,
            "paginas_bajo_umbral": cal["paginas_revisar"],
            "umbral": cal["objetivo_pagina"],
            "hojas_en_blanco": cal["hojas_en_blanco"],
            "paginas_texto_nativo": [p.number for p in doc.pages if (p.meta or {}).get("fuente") == "texto-nativo"],
            "calidad": {k: cal[k] for k in ("lectura_pct", "conf_texto", "conf_bruta", "palabras",
                                            "seguras", "verificadas")},
            "confianza_por_pagina": {p.number: round(fusion.conf_pagina(p), 3) for p in doc.pages},
            "lectura_por_pagina": cal["por_pagina"]}


# compatibilidad con código que importaba estas funciones
def _conf(p):
    return fusion.conf_pagina(p)


def _pal(p):
    return fusion.n_palabras(p)


def _puntaje(p):
    return fusion.puntaje(p)
