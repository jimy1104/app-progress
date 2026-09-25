# -*- coding: utf-8 -*-
"""Trabajos de procesamiento en segundo plano.

Azure App Service corta las peticiones HTTP que tardan más de ~230 s, y el OCR
de un expediente grande puede tardar más. Por eso: se sube el archivo, se crea
un 'trabajo' con número, un hilo lo procesa y la página consulta el avance.
El estado vive en disco (DATA_DIR/jobs/<id>/meta.json) y sobrevive reinicios."""
import os, io, json, time, uuid, shutil, threading, zipfile, traceback, dataclasses
from datetime import datetime
import pymupdf
import store, os_engine, risk_engine_kb, extractor
from cutter import cortar as cortar_pdf

BASE = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(store.DATA_DIR, "jobs"); os.makedirs(JOBS_DIR, exist_ok=True)
TTL_H = float(os.getenv("JOB_TTL_HOURS", "72"))
MAX_ZIP_BYTES = 800 * 1024 * 1024
_lock = threading.RLock()
_KB = None

def kb():
    global _KB
    if _KB is None:
        with open(os.path.join(BASE, "kb", "kb.json"), encoding="utf-8") as f: _KB = json.load(f)
    return _KB

def _dir(jid): return os.path.join(JOBS_DIR, os.path.basename(jid))

def meta(jid):
    try:
        with open(os.path.join(_dir(jid), "meta.json"), encoding="utf-8") as f: return json.load(f)
    except Exception:
        return None

def _set(jid, **kw):
    with _lock:
        m = meta(jid) or {}
        m.update(kw); m["actualizado"] = time.time()
        tmp = os.path.join(_dir(jid), "meta.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f: json.dump(m, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(_dir(jid), "meta.json"))
        return m

def resultado(jid):
    try:
        with open(os.path.join(_dir(jid), "resultado.json"), encoding="utf-8") as f: return json.load(f)
    except Exception:
        return None

def pdf_path(jid): return os.path.join(_dir(jid), "expediente.pdf")
def ocr_path(jid): return os.path.join(_dir(jid), "ocr.json")
def buscable_path(jid): return os.path.join(_dir(jid), "expediente_buscable.pdf")

def texto(jid):
    """Todo el texto leído, hoja por hoja, con el documento al que pertenece cada hoja."""
    from ocr.base import OCRDocument
    from ocr.pdf_buscable import texto_plano
    doc = OCRDocument.from_json(ocr_path(jid))
    res = resultado(jid) or {}
    segs = [os_engine.Segmento(**{k: d[k] for k in ("tipo", "etiqueta", "pagina_ini", "pagina_fin", "confianza")})
            for d in res.get("documentos", [])]
    return texto_plano(doc, segs)

# ---------------- proveedor de OCR ----------------
class _CacheProvider:
    """SOLO PRUEBAS: devuelve un OCR ya hecho (OCR_FAKE_CACHE). Nunca en producción."""
    name = "cache-pruebas"
    def __init__(self, path): self.path = path
    def analyze(self, pdf):
        from ocr.base import OCRDocument
        d = OCRDocument.from_json(self.path); d.provider = self.name; return d

def _quien_lee():
    """Decide quién hace el OCR: 'azure', 'local' o automático.

    OCR_PROVIDER manda. Si no está puesto: Azure cuando hay endpoint+llave,
    y si no, el OCR local (Tesseract). Así la app funciona sin nube."""
    elegido = (os.getenv("OCR_PROVIDER") or "").strip().lower()
    if elegido in ("azure", "local", "tesseract"):
        return "local" if elegido in ("local", "tesseract") else "azure"
    if os.getenv("AZURE_DI_ENDPOINT") and os.getenv("AZURE_DI_KEY"):
        return "azure"
    return "local"

def estado_ocr():
    """Para /api/config: qué motor de lectura está activo y si está listo."""
    quien = _quien_lee()
    if os.getenv("OCR_FAKE_CACHE"):
        return {"motor": "cache", "listo": True, "detalle": "caché de pruebas"}
    if quien == "azure":
        listo = bool(os.getenv("AZURE_DI_ENDPOINT") and os.getenv("AZURE_DI_KEY"))
        return {"motor": "azure", "listo": listo,
                "detalle": "Azure Document Intelligence" if listo else "faltan endpoint o llave"}
    try:
        from ocr.tesseract_provider import estado_local
        e = estado_local()
    except Exception as ex:
        return {"motor": "local", "listo": False, "detalle": str(ex)}
    if e["listo"]:
        det = "Tesseract %s (%s)" % ("español" if e["espanol"] else "inglés", e["programa"])
    elif not e["librerias"]:
        det = "falta: pip install pytesseract numpy pymupdf"
    elif not e["programa"]:
        det = "falta instalar el programa Tesseract en esta PC"
    else:
        det = "falta el idioma español (spa.traineddata)"
    return {"motor": "local", "listo": e["listo"], "detalle": det, "idiomas": e.get("idiomas", [])}

def get_provider():
    fake = os.getenv("OCR_FAKE_CACHE")
    if fake and os.path.exists(fake):
        return _CacheProvider(fake)
    if _quien_lee() == "local":
        from ocr.tesseract_provider import TesseractProvider
        return TesseractProvider()
    from ocr.azure_provider import AzureDocIntelligenceProvider
    return AzureDocIntelligenceProvider()

# ---------------- crear ----------------
def _preparar_pdf(raw, nombre, destino):
    low = nombre.lower()
    if low.endswith(".zip"):
        with zipfile.ZipFile(raw) as zf:
            total = sum(i.file_size for i in zf.infolist())
            if total > MAX_ZIP_BYTES: raise ValueError("El ZIP es demasiado grande (más de 800 MB descomprimido).")
            pdfs = sorted([i for i in zf.infolist() if i.filename.lower().endswith(".pdf") and not i.is_dir()
                           and "__MACOSX" not in i.filename], key=lambda i: i.filename.lower())
            if not pdfs: raise ValueError("El ZIP no contiene archivos PDF.")
            out = pymupdf.open()
            for i in pdfs:
                with pymupdf.open(stream=zf.read(i), filetype="pdf") as src:
                    out.insert_pdf(src)
            out.save(destino); out.close()
            return [os.path.basename(i.filename) for i in pdfs]
    elif low.endswith(".pdf"):
        shutil.move(raw, destino)
        with pymupdf.open(destino) as d:
            if d.page_count == 0: raise ValueError("El PDF no tiene páginas.")
        return [nombre]
    raise ValueError("Formato no admitido: sube un .pdf o un .zip con PDFs.")

def crear(user, fs, familia, subproceso, cortar):
    os.makedirs(JOBS_DIR, exist_ok=True)
    limpiar_antiguos()
    jid = datetime.now(store.PE).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    d = _dir(jid); os.makedirs(d)
    nombre = os.path.basename(fs.filename or "expediente.pdf")
    raw = os.path.join(d, "subido" + os.path.splitext(nombre)[1].lower())
    fs.save(raw)
    try:
        archivos = _preparar_pdf(raw, nombre, pdf_path(jid))
    except zipfile.BadZipFile:
        shutil.rmtree(d, ignore_errors=True); raise ValueError("El ZIP está dañado o no es un ZIP válido.")
    except Exception:
        shutil.rmtree(d, ignore_errors=True); raise
    finally:
        if os.path.exists(raw): os.remove(raw)
    with pymupdf.open(pdf_path(jid)) as doc: paginas = doc.page_count
    _set(jid, id=jid, usuario=user["nombre"], usuario_id=user["id"], rol=user["rol"], area=user.get("area", ""),
         familia=familia, subproceso=subproceso, cortar=cortar, archivo=nombre, archivos=archivos,
         paginas=paginas, creado=store.ahora(), creado_ts=time.time(),
         estado="en_cola", etapa="en_cola", etapa_txt="En cola")
    store.log(user["nombre"], user.get("area", ""), "Subió expediente", nombre, f"{paginas} págs · {subproceso}")
    threading.Thread(target=_run, args=(jid,), daemon=True).start()
    return jid

# ---------------- varios expedientes de una vez (lote) ----------------
LOTES_DIR = os.path.join(store.DATA_DIR, "lotes"); os.makedirs(LOTES_DIR, exist_ok=True)

def _grupos(zf):
    """Reparte los PDF del ZIP en expedientes.

    · Si el ZIP trae carpetas, CADA CARPETA es un expediente (sus PDF se unen en
      orden alfabético, igual que cuando se sube un expediente solo).
    · Los PDF sueltos en la raíz cuentan como un expediente cada uno."""
    pdfs = [i for i in zf.infolist() if i.filename.lower().endswith(".pdf")
            and not i.is_dir() and "__MACOSX" not in i.filename]
    if not pdfs:
        raise ValueError("El ZIP no contiene archivos PDF.")
    grupos = {}
    for i in pdfs:
        partes = i.filename.replace("\\", "/").split("/")
        nombre = partes[0] if len(partes) > 1 else os.path.splitext(partes[-1])[0]
        grupos.setdefault(nombre, []).append(i)
    for g in grupos.values():
        g.sort(key=lambda i: i.filename.lower())
    return dict(sorted(grupos.items(), key=lambda kv: kv[0].lower()))

def lote_meta(lid):
    try:
        with open(os.path.join(LOTES_DIR, os.path.basename(lid) + ".json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _lote_set(lid, m):
    with _lock:
        tmp = os.path.join(LOTES_DIR, os.path.basename(lid) + ".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f: json.dump(m, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(LOTES_DIR, os.path.basename(lid) + ".json"))

def crear_lote(user, fs, familia, subproceso, cortar):
    """Un ZIP con varios expedientes: se crea un trabajo por expediente y se
    procesan uno detrás de otro (en fila) para no saturar la PC ni Azure."""
    os.makedirs(JOBS_DIR, exist_ok=True); limpiar_antiguos()
    lid = datetime.now(store.PE).strftime("%Y%m%d-%H%M%S") + "-L" + uuid.uuid4().hex[:5]
    nombre_zip = os.path.basename(fs.filename or "expedientes.zip")
    tmp = os.path.join(JOBS_DIR, "_" + lid + ".zip"); fs.save(tmp)
    hijos = []
    try:
        with zipfile.ZipFile(tmp) as zf:
            if sum(i.file_size for i in zf.infolist()) > MAX_ZIP_BYTES:
                raise ValueError("El ZIP es demasiado grande (más de 800 MB descomprimido).")
            grupos = _grupos(zf)
            if len(grupos) < 2:
                raise ValueError("Ese ZIP trae un solo expediente. Súbelo como expediente individual, "
                                 "o arma un ZIP con una carpeta por expediente.")
            for nombre, items in grupos.items():
                jid = lid + "-" + str(len(hijos) + 1).zfill(2)
                d = _dir(jid); os.makedirs(d, exist_ok=True)
                out = pymupdf.open()
                for i in items:
                    with pymupdf.open(stream=zf.read(i), filetype="pdf") as src: out.insert_pdf(src)
                paginas = out.page_count
                out.save(pdf_path(jid)); out.close()
                _set(jid, id=jid, lote=lid, orden=len(hijos) + 1, usuario=user["nombre"], usuario_id=user["id"],
                     rol=user["rol"], area=user.get("area", ""), familia=familia, subproceso=subproceso,
                     cortar=cortar, archivo=nombre, archivos=[os.path.basename(i.filename) for i in items],
                     paginas=paginas, creado=store.ahora(), creado_ts=time.time(),
                     estado="en_cola", etapa="en_cola", etapa_txt="En fila")
                hijos.append(jid)
    except zipfile.BadZipFile:
        raise ValueError("El ZIP está dañado o no es un ZIP válido.")
    finally:
        if os.path.exists(tmp): os.remove(tmp)
    _lote_set(lid, {"id": lid, "archivo": nombre_zip, "usuario": user["nombre"], "usuario_id": user["id"],
                    "familia": familia, "subproceso": subproceso, "cortar": cortar,
                    "creado": store.ahora(), "creado_ts": time.time(), "hijos": hijos})
    store.log(user["nombre"], user.get("area", ""), "Subió lote de expedientes", nombre_zip,
              f"{len(hijos)} expedientes")
    threading.Thread(target=_run_lote, args=(lid,), daemon=True).start()
    return lid

def _run_lote(lid):
    m = lote_meta(lid) or {}
    for jid in m.get("hijos", []):
        if (meta(jid) or {}).get("estado") in ("listo", "error"):
            continue
        _run(jid)

def lote_estado(lid):
    m = lote_meta(lid)
    if not m: return None
    hijos = []
    for jid in m["hijos"]:
        j = meta(jid) or {}
        hijos.append({"id": jid, "archivo": j.get("archivo", ""), "paginas": j.get("paginas", 0),
                      "estado": j.get("estado", "en_cola"), "etapa_txt": j.get("etapa_txt", "En fila"),
                      "resumen": j.get("resumen"), "error": j.get("error", "")})
    listos = sum(1 for h in hijos if h["estado"] == "listo")
    errores = sum(1 for h in hijos if h["estado"] == "error")
    return {**m, "hijos": hijos, "listos": listos, "errores": errores, "total": len(hijos),
            "terminado": listos + errores == len(hijos)}

# ---------------- procesar ----------------
def _run(jid):
    m = meta(jid)
    try:
        motor = {"azure": "Azure Document Intelligence", "local": "OCR local (Tesseract)",
                 "cache": "caché de pruebas"}.get(estado_ocr()["motor"], "OCR")
        _set(jid, estado="procesando", etapa="ocr", t_ocr=time.time(),
             etapa_txt="Leyendo el expediente con " + motor)
        provider = get_provider()
        ETAPAS = ["Azure está leyendo todas las hojas", "Revisando qué hojas quedaron dudosas",
                  "Releyendo las hojas dudosas con la imagen limpia y sin sellos", "Lectura terminada"]
        def _avance(hechas, total, pagina):
            if pagina is None:          # el proveedor informa etapas, no páginas
                txt = ETAPAS[min(hechas, len(ETAPAS) - 1)] if total == len(ETAPAS) - 1 else "Leyendo el expediente"
            else:
                txt = f"Leyendo el expediente: página {hechas} de {total}" if total else "Leyendo el expediente"
            _set(jid, etapa_txt=txt)
        import inspect
        acepta = "progreso" in inspect.signature(provider.analyze).parameters
        doc = provider.analyze(pdf_path(jid), progreso=_avance) if acepta else provider.analyze(pdf_path(jid))

        try:
            doc.to_json(ocr_path(jid))          # la lectura completa, para texto y PDF buscable
        except Exception:
            pass

        _set(jid, etapa="segmentando", etapa_txt="Identificando los documentos del expediente")
        segs = os_engine.segmentar(doc)
        mapa = os_engine.mapa_paginas(doc, segs)
        buscable = None
        if os.getenv("PDF_BUSCABLE", "1") != "0":
            try:
                from ocr.pdf_buscable import hacer_buscable
                with hacer_buscable(pdf_path(jid), doc) as bd:
                    bd.save(buscable_path(jid), garbage=1, deflate=True)
                buscable = buscable_path(jid)
            except Exception:
                traceback.print_exc()
        cortes = []
        if m.get("cortar"):
            tipos = [os_engine.CORTES_UI.get(t, t) for t in m["cortar"]]
            cdir = os.path.join(_dir(jid), "cortes")
            # los cortes salen del PDF buscable: cada documento cortado se puede buscar (Ctrl+F)
            cortes = cortar_pdf(buscable or pdf_path(jid), segs, tipos, cdir)
            for c in cortes: c["archivo"] = os.path.basename(c["archivo"])

        _set(jid, etapa="riesgo", etapa_txt="Contrastando con la matriz de riesgos y la normativa")
        ctx = extractor.extraer_contexto(doc, segs, m.get("archivo", ""))
        clave = extractor.clave_objeto(ctx["objeto"]) if ctx["objeto"] else ""
        anio = ctx["anio"] or datetime.now(store.PE).year
        previos = store.acumulado_previo(clave, anio, ctx["os"]) if clave else []
        ctx_eng = {"monto": ctx["monto"],
                   "monto_fuente": ctx["monto_fuente"] if ctx.get("monto_validado") is not False else "estimado",
                   "objeto": clave,
                   "objeto_txt": ctx["objeto"], "monto_linea": ctx["monto_linea"]}
        verificados = []
        hall = risk_engine_kb.detectar(doc, kb()["riesgos"], m["familia"],
                                       accumulator=({clave: previos} if clave else {}), contexto=ctx_eng,
                                       segmentos=segs, verificados=verificados)
        if ctx["os"] and clave and ctx["monto_fuente"] == "orden" and ctx.get("monto_validado") is not False:
            store.acumulado_guardar(anio, ctx["os"], clave, {
                "monto": ctx["monto"], "ruc": ctx["ruc"], "objeto": ctx["objeto"],
                "familia": m["familia"], "usuario": m["usuario"]})

        from ocr.calidad import calidad_documento
        cal = calidad_documento(doc)
        documentos = []
        for i, s_ in enumerate(segs):
            d_ = dataclasses.asdict(s_)
            d_["i"] = i
            d_["riesgos"] = [{"id": h.id, "nivel": h.nivel, "hecho": h.hecho} for h in hall if h.documento_idx == i]
            documentos.append(d_)
        res = {
            "id": jid, "provider": doc.provider, "paginas": doc.n_pages,
            # «lectura OCR»: % de palabras de texto que quedaron SEGURAS (alta confianza
            # o confirmadas por dos lecturas). Ver ocr/calidad.py.
            "conf_ocr": cal["lectura_pct"],
            "calidad": {k: cal[k] for k in ("lectura_pct", "conf_texto", "conf_bruta", "palabras", "seguras",
                                            "verificadas", "hojas_en_blanco", "paginas_revisar", "objetivo_pagina",
                                            "por_pagina")},
            "ocr": getattr(doc, "meta", {}) or {},
            "familia": m["familia"], "subproceso": m["subproceso"], "archivo": m["archivo"],
            "contexto": {k: ctx.get(k) for k in ("os", "ruc", "monto", "monto_fuente", "objeto", "anio",
                                                 "monto_validado")},
            "validaciones": ctx.get("validaciones", []),
            "acumulado_previo": {"ordenes": len(previos), "monto": round(sum(previos), 2)},
            "paginas_dim": {p.number: [p.width_pt, p.height_pt] for p in doc.pages},
            "paginas_giro": {p.number: (p.meta or {}).get("giro", 0) for p in doc.pages
                             if (p.meta or {}).get("giro")},
            "documentos": documentos,
            "mapa_paginas": mapa,
            "buscable": bool(buscable),
            "cortes": [{"i": i, **{k: c[k] for k in ("tipo", "etiqueta", "pagina_ini", "pagina_fin", "archivo")}}
                       for i, c in enumerate(cortes)],
            "riesgos": [dataclasses.asdict(h) for h in hall],
            "verificados": verificados,
            "fecha": store.ahora(), "usuario": m["usuario"],
        }
        with open(os.path.join(_dir(jid), "resultado.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False)
        rojo = sum(1 for h in hall if h.nivel == "rojo"); amar = len(hall) - rojo
        _set(jid, estado="listo", etapa="listo", etapa_txt="Completado",
             resumen={"rojo": rojo, "amarillo": amar, "documentos": len(segs), "cortes": len(cortes),
                      "os": ctx["os"]})
        store.log(m["usuario"], m.get("area", ""), "Detección de riesgo" + (" + corte" if cortes else ""),
                  (("OS " + ctx["os"]) if ctx["os"] else m["archivo"]), f"{rojo} confirmados · {amar} por revisar")
        _copiar_blob(jid)
    except Exception as e:
        traceback.print_exc()
        msg = f"{type(e).__name__}: {e}"
        if "401" in msg or "Unauthorized" in msg or "PermissionDenied" in msg:
            msg = "Azure rechazó la llave de Document Intelligence (revisa AZURE_DI_KEY / AZURE_DI_ENDPOINT)."
        _set(jid, estado="error", etapa="error", etapa_txt="Error", error=msg)
        store.log(m.get("usuario", "?"), m.get("area", ""), "Error al procesar", m.get("archivo", ""), msg[:200])

# ---------------- copia temporal en Blob ----------------
def _blob():
    conn = os.getenv("AZURE_BLOB_CONN")
    if not conn or os.getenv("BLOB_COPIAS", "1") == "0": return None
    from azure.storage.blob import BlobServiceClient
    cc = BlobServiceClient.from_connection_string(conn).get_container_client(os.getenv("AZURE_BLOB_CONTAINER", "expedientes"))
    try: cc.create_container()
    except Exception: pass
    return cc

def _copiar_blob(jid):
    try:
        cc = _blob()
        if not cc: return
        pref = f"consultas/{jid[:8]}/{jid}/"
        d = _dir(jid)
        for root, _, files in os.walk(d):
            for fn in files:
                if fn.endswith(".tmp"): continue
                full = os.path.join(root, fn)
                with open(full, "rb") as f:
                    cc.upload_blob(pref + os.path.relpath(full, d).replace("\\", "/"), f, overwrite=True)
        _set(jid, blob=pref)
    except Exception as e:
        _set(jid, blob_error=f"{type(e).__name__}: {e}"[:300])

def _borrar_blob(jid, pref):
    try:
        cc = _blob()
        if cc and pref:
            for b in cc.list_blobs(name_starts_with=pref): cc.delete_blob(b.name)
    except Exception:
        pass

# ---------------- listar / borrar ----------------
def listar(user):
    os.makedirs(JOBS_DIR, exist_ok=True)
    out = []
    for jid in sorted(os.listdir(JOBS_DIR), reverse=True):
        m = meta(jid)
        if not m: continue
        if m.get("estado") in ("procesando", "en_cola") and time.time() - m.get("actualizado", 0) > 3600:
            m = _set(jid, estado="error", etapa="error", error="El proceso se interrumpió (reinicio del servidor). Vuelve a subir el expediente.")
        if user["rol"] != "admin" and m.get("usuario_id") != user["id"]: continue
        out.append({k: m.get(k) for k in ("id", "usuario", "area", "familia", "subproceso", "archivo", "paginas",
                                           "creado", "estado", "etapa_txt", "resumen", "error")})
    return out

def borrar(jid):
    m = meta(jid)
    if m: _borrar_blob(jid, m.get("blob"))
    shutil.rmtree(_dir(jid), ignore_errors=True)

def limpiar_antiguos(horas=None):
    horas = TTL_H if horas is None else horas
    n = 0
    for jid in os.listdir(JOBS_DIR):
        m = meta(jid)
        if m and m.get("estado") not in ("procesando", "en_cola") and time.time() - m.get("creado_ts", time.time()) > horas * 3600:
            borrar(jid); n += 1
    return n

# ---------------- páginas ----------------
def pagina_png(jid, n, zoom=1.5, dim_ocr=None, giro=None):
    """Dibuja la página. Si el OCR la leyó en la otra orientación (las hojas
    escaneadas vienen rotadas), se gira la imagen para que el resaltado calce."""
    with pymupdf.open(pdf_path(jid)) as d:
        n = max(1, min(n, d.page_count))
        pg = d[n - 1]
        m = pymupdf.Matrix(zoom, zoom)
        if giro is not None:
            # resultados v5: coordenadas en el marco derecho del texto (giro horario)
            if not giro:
                return pg.get_pixmap(matrix=m).tobytes("png")
            from ocr import imagen
            import numpy as np
            pix = pg.get_pixmap(matrix=m, alpha=False)
            a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
            return imagen.a_png(np.ascontiguousarray(imagen.girar90(a, giro)[:, :, ::-1]))
        if dim_ocr and dim_ocr[0] and dim_ocr[1]:
            apaisado_ocr = dim_ocr[0] > dim_ocr[1]
            if apaisado_ocr != (pg.rect.width > pg.rect.height):
                m = m * pymupdf.Matrix(90)
        return pg.get_pixmap(matrix=m).tobytes("png")

def pagina_pdf(jid, n):
    with pymupdf.open(pdf_path(jid)) as d:
        n = max(1, min(n, d.page_count))
        out = pymupdf.open(); out.insert_pdf(d, from_page=n - 1, to_page=n - 1)
        b = out.tobytes(); out.close(); return b
