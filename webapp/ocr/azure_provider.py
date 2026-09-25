# -*- coding: utf-8 -*-
"""OCR de producción — Azure AI Document Intelligence (prebuilt-layout), reforzado.

Los expedientes llegan escaneados a ~96 DPI (JPEG), con sellos y firmas encima
del texto y el reverso transparentándose. Por eso la lectura se hace así:

  1ª pasada  Se envía el PDF completo UNA vez, con el complemento
             «ocrHighResolution» (lee letra chica y escaneos pobres) y «barcodes»
             (QR de facturas electrónicas). Azure devuelve además el ROL de cada
             párrafo (title, sectionHeading, pageHeader, pageFooter, pageNumber) y
             marca lo MANUSCRITO; ambos alimentan al segmentador.
  Texto      Las hojas digitales (capa de texto real, no la del escáner) se toman
  nativo     tal cual: exactitud 100%, sin gastar OCR.
  Blancas    Se detectan por TINTA real (ocr/imagen.py). Lo que Azure «leyó» en
             un reverso transparentado se descarta si no es claramente texto.
  2ª pasada  Las hojas con palabras dudosas se vuelven a enviar como imágenes a
             300 DPI LIMPIAS (fondo aplanado, sin transparencia) y, si tienen
             sellos de color, también SIN SELLOS. Van agrupadas en pocos PDF (no
             una llamada por hoja) y en paralelo.
  Fusión     Las 2–3 lecturas de cada hoja se combinan palabra por palabra
             (ocr/fusion.py). Donde coinciden, la palabra queda verificada.

Tarda más que una sola llamada, a propósito: el objetivo es la exactitud.
Costo: la 2ª pasada solo toca hojas flojas (tope OCR_MAX_RELECTURAS).
"""
from __future__ import annotations
import io, os, re, bisect, time
from concurrent.futures import ThreadPoolExecutor
import pymupdf
from .base import OCRWord, OCRLine, OCRPage, OCRDocument, OCRProvider
from . import imagen, nativo, fusion, calidad
import config


def _poly_a_bbox(polygon, pw, ph):
    if not polygon:
        return (0.0, 0.0, 1.0, 0.05)
    xs = polygon[0::2]; ys = polygon[1::2]
    return (max(0.0, min(xs) / pw), max(0.0, min(ys) / ph), min(1.0, max(xs) / pw), min(1.0, max(ys) / ph))


def _features():
    txt = os.getenv("AZURE_DI_FEATURES", "ocrHighResolution,barcodes")
    return [f.strip() for f in txt.split(",") if f.strip()]


class _Orientacion:
    """Azure puede devolver las coordenadas en la orientación del papel SIN girar
    (/Rotate del PDF) mientras la hoja se muestra girada. Aquí se lleva todo a la
    hoja tal como se VE, que es como se dibuja y se resalta en la aplicación."""

    def __init__(self, page):
        self.W, self.H = page.rect.width or 1, page.rect.height or 1        # como se ve
        mb = page.mediabox
        self.w0, self.h0 = mb.width or 1, mb.height or 1                    # sin girar
        self.M = page.rotation_matrix
        self.rot = page.rotation

    def a_vista(self, bbox, apaisada_azure: bool):
        apaisada_vista = self.W > self.H
        if not self.rot or apaisada_azure == apaisada_vista:
            return bbox
        r = pymupdf.Rect(bbox[0] * self.w0, bbox[1] * self.h0, bbox[2] * self.w0, bbox[3] * self.h0) * self.M
        return (max(0.0, min(r.x0, r.x1) / self.W), max(0.0, min(r.y0, r.y1) / self.H),
                min(1.0, max(r.x0, r.x1) / self.W), min(1.0, max(r.y0, r.y1) / self.H))


class AzureDocIntelligenceProvider(OCRProvider):
    name = "azure-document-intelligence"

    def __init__(self, endpoint=None, modelo=None, locale=None, client=None):
        self.endpoint = endpoint or config.AZURE_DI_ENDPOINT
        self.modelo = modelo or config.AZURE_DI_MODELO
        self.locale = locale or getattr(config, "AZURE_DI_LOCALE", "es")
        self.features = _features()
        self.relectura = os.getenv("OCR_RELECTURA", "1") != "0"
        self.max_relecturas = int(os.getenv("OCR_MAX_RELECTURAS", "60"))
        self.objetivo = calidad.OBJETIVO_PAGINA
        self.hojas_por_lote = max(1, int(os.getenv("OCR_HOJAS_POR_LOTE", "15")))
        # Las llamadas son independientes: se hacen en paralelo.
        # 4 a la vez va cómodo dentro de los límites del nivel S0 de Azure.
        self.concurrencia = max(1, int(os.getenv("OCR_CONCURRENCIA", "4")))
        self.dpi = int(os.getenv("OCR_DPI", str(imagen.DPI_OCR)))
        if client is not None:                       # pruebas: cliente simulado
            self.client, self.cred_desc = client, "cliente de pruebas"
        else:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from secrets_azure import resolver_credencial
            credencial, self.cred_desc = resolver_credencial()
            self.client = DocumentIntelligenceClient(endpoint=self.endpoint, credential=credencial)

    # ------------------------------------------------------------ llamadas ---
    def _analizar(self, datos: bytes, content_type="application/octet-stream", features=None):
        features = self.features if features is None else features
        kw = dict(locale=self.locale, content_type=content_type)
        if features:
            kw["features"] = features
        ultimo = None
        for intento in range(5):
            try:
                poller = self.client.begin_analyze_document(self.modelo, body=io.BytesIO(datos), **kw)
                return poller.result()
            except Exception as e:
                ultimo = e
                msg = f"{type(e).__name__}: {e}"
                codigo = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
                # 1º saturación / tiempo: se espera y se reintenta (con los mismos complementos)
                if codigo == 429 or "429" in msg or "Too Many" in msg or "timeout" in msg.lower():
                    if intento < 4:
                        time.sleep(2 * (intento + 1) ** 2)
                        continue
                    raise
                # 2º el recurso no admite un complemento (p. ej. nivel gratuito): sin complementos
                if kw.get("features") and (codigo == 400 or codigo is None) and \
                        re.search(r"feature|InvalidParameter|UnsupportedFeature|InvalidArgument", msg, re.I):
                    kw.pop("features", None)
                    continue
                raise
        raise ultimo

    def _a_paginas(self, resultado, orientaciones=None, mapa=None, dims=None):
        """AnalyzeResult -> [OCRPage]. 'mapa' traduce el número de página del
        resultado al número de hoja del expediente (para los lotes de relectura)."""
        content = getattr(resultado, "content", "") or ""
        # rol de cada párrafo por rango de caracteres (title, sectionHeading, ...)
        roles = sorted(((sp.offset, sp.offset + sp.length, p.role)
                        for p in (getattr(resultado, "paragraphs", None) or []) if getattr(p, "role", None)
                        for sp in (p.spans or [])), key=lambda t: t[0])
        ini_roles = [r[0] for r in roles]
        manus = sorted(((sp.offset, sp.offset + sp.length)
                        for s in (getattr(resultado, "styles", None) or [])
                        if getattr(s, "is_handwritten", False) and (s.confidence or 0) >= 0.5
                        for sp in (s.spans or [])), key=lambda t: t[0])
        ini_man = [m[0] for m in manus]

        def rol_de(spans):
            for sp in spans or []:
                i = bisect.bisect_right(ini_roles, sp.offset) - 1
                if i >= 0 and roles[i][0] <= sp.offset < roles[i][1]:
                    return roles[i][2]
            return ""

        def manuscrita(spans):
            tot = dentro = 0
            for sp in spans or []:
                tot += sp.length
                i = max(0, bisect.bisect_right(ini_man, sp.offset) - 1)
                while i < len(manus) and manus[i][0] < sp.offset + sp.length:
                    a, b = manus[i]
                    dentro += max(0, min(b, sp.offset + sp.length) - max(a, sp.offset))
                    i += 1
            return tot > 0 and dentro / tot > 0.5

        paginas = []
        for pg in resultado.pages:
            numero = mapa.get(pg.page_number, pg.page_number) if mapa else pg.page_number
            pw, ph = (pg.width or 1.0), (pg.height or 1.0)
            ori = (orientaciones or {}).get(numero)
            apaisada = pw > ph
            conv = (lambda b: ori.a_vista(b, apaisada)) if ori else (lambda b: b)
            # el ángulo del texto lo mide Azure en SU marco; si las coordenadas se
            # llevaron del papel sin girar a la vista, el ángulo también gira /Rotate
            angulo = float(getattr(pg, "angle", 0) or 0)
            if ori and ori.rot and apaisada != (ori.W > ori.H):
                angulo = (angulo + ori.rot + 180.0) % 360.0 - 180.0
            palabras = list(pg.words or [])
            offs = [(w.span.offset if getattr(w, "span", None) else -1) for w in palabras]
            orden = sorted(range(len(palabras)), key=lambda i: offs[i])
            offs_ord = [offs[i] for i in orden]
            lineas = []
            for ln in (pg.lines or []):
                dentro = []
                for sp in (ln.spans or []):
                    a = bisect.bisect_left(offs_ord, sp.offset)
                    b = bisect.bisect_left(offs_ord, sp.offset + sp.length)
                    dentro += [palabras[orden[k]] for k in range(a, b)]
                if not dentro:
                    dentro = [w for w in palabras if _solapa(w, ln)]
                conf = sum((w.confidence or 0) for w in dentro) / len(dentro) if dentro else 0.85
                lineas.append(OCRLine(
                    text=ln.content, conf=conf, bbox=conv(_poly_a_bbox(ln.polygon, pw, ph)),
                    page=numero, role=rol_de(ln.spans), manuscrita=manuscrita(ln.spans),
                    words=[OCRWord(text=w.content, conf=(w.confidence or 0),
                                   bbox=conv(_poly_a_bbox(w.polygon, pw, ph)), page=numero)
                           for w in dentro]))
            codigos = [{"tipo": getattr(b, "kind", ""), "valor": getattr(b, "value", ""),
                        "conf": getattr(b, "confidence", 0) or 0,
                        "bbox": list(conv(_poly_a_bbox(getattr(b, "polygon", None), pw, ph)))}
                       for b in (getattr(pg, "barcodes", None) or [])]
            W, H = (ori.W, ori.H) if ori else (dims or {}).get(numero, (pw, ph))
            paginas.append(OCRPage(number=numero, width_pt=W, height_pt=H, rotation=0, lines=lineas,
                                   meta={"angulo_azure": angulo, "codigos": codigos}))
        return paginas

    # ------------------------------------------------------- preparación -----
    def _preparar_todas(self, pdf_path, n):
        """1ª fase (mientras Azure lee): texto nativo y hoja en blanco, barato (150 DPI).
        Un error en una hoja no tumba el expediente: esa hoja queda con lo de Azure."""
        def una(i):
            try:
                with pymupdf.open(pdf_path) as d:
                    page = d[i - 1]
                    diag = nativo.diagnostico(page)
                    nat = nativo.leer(page, i) if diag["solo_texto"] else None
                    return i, diag, nat, imagen.preparar_ligero(page)
            except Exception as e:
                return i, {}, None, {"en_blanco": False, "error": f"{type(e).__name__}: {e}"[:200]}
        out = {}
        with ThreadPoolExecutor(max_workers=max(1, min(4, os.cpu_count() or 2))) as pool:
            for i, diag, nat, prep in pool.map(una, range(1, n + 1)):
                out[i] = (diag, nat, prep)
        return out

    def _variantes(self, pdf_path, hojas):
        """2ª fase, SOLO para las hojas que se releen: imagen limpia y sin sellos a
        300 DPI, guardadas como JPEG (~0,5 MB por hoja, no ~17 MB en memoria)."""
        def una(i):
            try:
                with pymupdf.open(pdf_path) as d:
                    prep = imagen.preparar(d[i - 1], self.dpi, enderezar=False)
                return i, {v: (None if prep.get(v) is None else imagen.a_jpg(prep[v], 90))
                           for v in ("limpia", "sin_sellos")}
            except Exception:
                return i, {"limpia": None, "sin_sellos": None}
        out = {}
        with ThreadPoolExecutor(max_workers=max(1, min(4, os.cpu_count() or 2))) as pool:
            for i, v in pool.map(una, hojas):
                out[i] = v
        return out

    def _pdf_de_imagenes(self, hojas, variante, variantes, dims):
        """Arma un PDF con la variante pedida de cada hoja (en escala de grises)."""
        out = pymupdf.open()
        mapa = {}
        for k, n in enumerate(hojas, start=1):
            jpg = variantes[n][variante]
            W, H = dims[n]
            pg = out.new_page(width=W, height=H)
            pg.insert_image(pg.rect, stream=jpg)
            mapa[k] = n
        datos = out.tobytes(deflate=True)
        out.close()
        return datos, mapa

    def _releer(self, hojas, variantes, dims):
        """2ª pasada en lotes: {hoja: [lecturas]}."""
        trabajos = []
        for variante in ("limpia", "sin_sellos"):
            cand = [n for n in hojas if variantes.get(n, {}).get(variante) is not None]
            for i in range(0, len(cand), self.hojas_por_lote):
                trabajos.append((variante, cand[i:i + self.hojas_por_lote]))
        resultado = {}

        def uno(t):
            variante, lote = t
            datos, mapa = self._pdf_de_imagenes(lote, variante, variantes, dims)
            res = self._analizar(datos, "application/pdf")
            pags = self._a_paginas(res, mapa=mapa, dims=dims)
            for p in pags:
                p.meta["lectura"] = variante
            return pags

        with ThreadPoolExecutor(max_workers=min(self.concurrencia, max(1, len(trabajos)))) as pool:
            for pags in pool.map(lambda t: _seguro(uno, t), trabajos):
                for p in pags or []:
                    resultado.setdefault(p.number, []).append(p)
        return resultado

    # ---------------------------------------------------------------- API ----
    def analyze(self, pdf_path: str, progreso=None) -> OCRDocument:
        """progreso: función opcional (hechas, total, pagina). Aquí avanza por ETAPAS
        (pagina=None): 0 lectura de Azure, 1 hojas dudosas, 2 relectura, 3 listo."""
        with pymupdf.open(pdf_path) as d:
            n = d.page_count
            orient = {i + 1: _Orientacion(d[i]) for i in range(n)}
            dims = {i + 1: (d[i].rect.width or 1, d[i].rect.height or 1) for i in range(n)}
        if progreso:
            progreso(0, 3, None)
        with ThreadPoolExecutor(max_workers=2) as pool:           # Azure y la limpieza a la vez
            f_ocr = pool.submit(lambda: self._analizar(open(pdf_path, "rb").read()))
            f_prep = pool.submit(self._preparar_todas, pdf_path, n)
            primera = self._a_paginas(f_ocr.result(), orientaciones=orient)
            preps = f_prep.result()
        if progreso:
            progreso(1, 3, None)
        paginas = {p.number: p for p in primera}
        giros = {}
        for p in primera:
            # Azure informa hacia dónde está girado el texto (grados, sentido horario).
            # Una hoja escaneada de costado se lleva al marco derecho del texto.
            ang = p.meta.get("angulo_azure", 0) or 0
            k = round(ang / 90.0)
            if k and abs(ang - 90 * k) <= 10:
                giros[p.number] = (-90 * k) % 360
                p.girar(giros[p.number])
        for i in range(1, n + 1):
            diag, nat, prep = preps[i]
            pg = paginas.get(i) or OCRPage(number=i, width_pt=dims[i][0], height_pt=dims[i][1],
                                           rotation=0, lines=[])
            meta = {k: prep[k] for k in ("tinta", "color", "dpi_origen", "en_blanco", "error") if k in prep}
            if i in giros and nat is None:        # el texto nativo ya viene en el marco de la vista
                meta["giro"] = giros[i]
            meta.update({"fuente": "ocr", "lecturas": ["original"],
                         "codigos": pg.meta.get("codigos", []), "angulo_azure": pg.meta.get("angulo_azure", 0)})
            if nat is not None:
                pg = nat
                meta.update({"fuente": "texto-nativo", "lecturas": ["nativo"], "en_blanco": False})
            elif prep.get("en_blanco"):
                # reverso transparentado: solo sobrevive lo que es texto claro de verdad
                pg.lines = [l for l in pg.lines if l.conf >= 0.85 and len(l.text.strip()) >= 4]
                meta["en_blanco"] = not pg.lines
            pg.meta = meta
            paginas[i] = pg

        releidas, mejoradas = [], []
        if self.relectura:
            flojas = [p for p in paginas.values()
                      if p.meta.get("fuente") == "ocr" and not p.meta.get("en_blanco") and p.lines
                      and (calidad.calidad_pagina(p)["pct"] or 0) < self.objetivo]
            flojas.sort(key=lambda p: calidad.calidad_pagina(p)["pct"] or 0)
            hojas = [p.number for p in flojas[:self.max_relecturas]]
            if hojas:
                if progreso:
                    progreso(2, 3, None)
                variantes = self._variantes(pdf_path, hojas)
                extra = self._releer(hojas, variantes, dims)
                for h in hojas:
                    otras = [o.girar(giros.get(h, 0)) for o in extra.get(h, [])]
                    if not otras:
                        continue
                    base = paginas[h]
                    antes = calidad.calidad_pagina(base)["pct"] or 0
                    base.meta["lectura"] = "original"
                    nueva = fusion.fusionar([base] + otras)
                    nueva.meta = dict(base.meta)
                    nueva.meta["lecturas"] = ["original"] + [o.meta.get("lectura") for o in otras]
                    paginas[h] = nueva
                    releidas.append(h)
                    despues = calidad.calidad_pagina(nueva)["pct"] or 0
                    if despues > antes + 0.005:
                        mejoradas.append({"pagina": h, "antes": round(antes, 3), "despues": round(despues, 3)})
        if progreso:
            progreso(3, 3, None)
        doc = OCRDocument(provider=self.name, source_path=pdf_path,
                          pages=[paginas[i] for i in range(1, n + 1)])
        cal = calidad.calidad_documento(doc)
        doc.meta = {"modelo": self.modelo, "complementos": self.features, "relecturas": len(releidas),
                    "concurrencia": self.concurrencia,
                    "paginas_mejoradas": sorted(mejoradas, key=lambda m: m["pagina"]),
                    "paginas_bajo_umbral": cal["paginas_revisar"],
                    "umbral": cal["objetivo_pagina"],
                    "hojas_en_blanco": cal["hojas_en_blanco"],
                    "paginas_texto_nativo": [p.number for p in doc.pages if p.meta.get("fuente") == "texto-nativo"],
                    "calidad": {k: cal[k] for k in ("lectura_pct", "conf_texto", "conf_bruta", "palabras",
                                                    "seguras", "verificadas")},
                    "confianza_por_pagina": {p.number: round(fusion.conf_pagina(p), 3) for p in doc.pages},
                    "lectura_por_pagina": cal["por_pagina"]}
        return doc


def _seguro(f, *a):
    try:
        return f(*a)
    except Exception:
        return []


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


# compatibilidad
_confianza = fusion.conf_pagina
_palabras = fusion.n_palabras
_puntaje = fusion.puntaje
