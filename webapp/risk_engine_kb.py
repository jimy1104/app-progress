# -*- coding: utf-8 -*-
"""Motor de riesgo dirigido por la BASE DE CONOCIMIENTO (kb.json).

No inventa nada: usa la matriz (04), los procedimientos (05) y la base legal (10)
del Excel. Para cada riesgo aplica un DETECTOR según su 'procedimiento de auditoría':

  fecha       -> compara fechas (p.ej. solicitud/CCP/conformidad vs inicio).
  presencia   -> verifica si un documento/elemento OBRA o NO en el expediente.
  acumulacion -> suma montos del mismo objeto/meta contra las 8 UIT (fraccionamiento),
                 usando un ACUMULADOR mínimo persistente (no guarda el PDF).
  patron_texto/criterio -> no se afirma solo: queda 'por revisar' con su fundamento.

Nivel de color:
  rojo    = la condición de incumplimiento se verificó con lectura clara.
  amarillo= 'por revisar': se cumple la condición pero el OCR leyó con baja
            confianza, o el riesgo es de criterio humano.
Cada hallazgo guarda página + bbox (para 'Ubicar') y arrastra del KB la base
legal resuelta, el control, quién supervisa y el ejemplo real.
"""
from __future__ import annotations
import json, re, unicodedata, os
from dataclasses import dataclass, field, asdict
from datetime import date

UIT_2026 = 5500.0
TOPE_8UIT = 8 * UIT_2026          # S/ 44,000
UMBRAL = float(os.getenv("UMBRAL_CONFIANZA_OCR", "0.72"))

def norm(t):
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.upper()).strip()

# ---- utilidades de extracción sobre el OCR ----
_FECHA = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
_MONTO = re.compile(r"S/\.?\s*([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)")

def fechas_en(texto):
    out = []
    for d,m,y in _FECHA.findall(texto):
        try:
            y = int(y); y = y+2000 if y < 100 else y
            if 2015 <= y <= 2035:
                out.append(date(y, int(m), int(d)))
        except ValueError:
            pass
    return out

def montos_en(texto):
    out = []
    for s in _MONTO.findall(texto):
        s = s.replace(".", "").replace(",", ".") if s.count(",")==1 and s.rfind(",")>s.rfind(".") else s.replace(",", "")
        try:
            v=float(s)
            if v<=200*UIT_2026:  # montos absurdos = error de OCR (contrato menor <= 8 UIT)
                out.append(v)
        except ValueError: pass
    return out

@dataclass
class Hallazgo:
    id: str; nivel: str; hecho: str; base_legal: list; control: str
    ejecuta: str; supervisa: str; pagina: int; bbox: list; confianza: float
    subproceso: str; familia: str; deteccion: str; nota: str = ""
    ejemplo: dict = None
    nivel_matriz: str = ""
    actividad: str = ""
    como_verificar: str = ""
    evidencia: str = ""
    ubicaciones: list = field(default_factory=list)
    documento: str = ""               # subdocumento donde está el hallazgo («Orden de Servicio»)
    documento_idx: int = -1           # índice en la lista de documentos del expediente (-1: expediente)
    documento_paginas: list = field(default_factory=list)   # [pág. inicial, pág. final] de ese documento

def _find_line(doc, patrones):
    """Primera línea (con su conf y bbox) que casa cualquier patrón normalizado."""
    pats = [re.compile(norm(p)) for p in patrones]
    for pg in doc.pages:
        for ln in pg.lines:
            ln_n = norm(ln.text)
            if any(p.search(ln_n) for p in pats):
                return ln
    return None

_REAL = re.compile(r"[A-ZÁÉÍÓÚÜÑ0-9]{3,}")


def _conf_prom(doc):
    """Confianza de lectura del expediente, contando solo lo que es texto.

    Las hojas en blanco (reversos de fotocopia) devuelven manchas con confianza
    bajísima; si entraran al promedio, un expediente bien leído parecería malo."""
    cs = [l.conf for pg in doc.pages for l in pg.lines if _REAL.search(norm(l.text))]
    return sum(cs)/len(cs) if cs else 0.0


def umbral_de(doc):
    """El umbral depende de quién leyó: Tesseract puntúa más bajo que Azure
    para un mismo texto legible, así que se le pide menos."""
    if "tesseract" in (getattr(doc, "provider", "") or "").lower():
        return float(os.getenv("UMBRAL_CONFIANZA_LOCAL", "0.60"))
    return UMBRAL

# palabras-ancla por familia de documento (para 'presencia')
ANCLA_DOC = {
    "COTIZACION": ["COTIZACION", "CUADRO COMPARATIVO", "PROPUESTA ECONOMICA"],
    "CCP": ["CERTIFICACION DE CREDITO PRESUPUESTARIO", "CERTIFICACION PRESUPUESTAL", "NOTA DE CERTIFICACION"],
    "DECLARACION": ["DECLARACION JURADA"],
    "CONFORMIDAD": ["CONFORMIDAD DE SERVICIO", "CONFORMIDAD DE LA PRESTACION", "ACTA DE CONFORMIDAD"],
    "PUBLICACION": ["CONSTANCIA DE PUBLICACION", "PLADICOP", "SEACE"],
    "CCI": ["CARTA DE AUTORIZACION", "CODIGO DE CUENTA INTERBANCARI", "AUTORIZACION DE ABONO"],
}
_CLAUSULA = re.compile(r"^\W*\d+(\.\d+)*\s*[.)\-:]?\s")

# documento esperado -> tipo de documento que reconoce el segmentador (os_engine.DOCS)
SEG_DE_ANCLA = {"COTIZACION": "cotizacion", "CCP": "certificacion", "DECLARACION": "anexo",
                "CONFORMIDAD": "conformidad", "CCI": "cci", "PUBLICACION": None}


def _documento_de(pagina, segmentos):
    for i, sg in enumerate(segmentos or []):
        if sg.pagina_ini <= pagina <= sg.pagina_fin:
            return i, sg
    return -1, None


def ubicar_en_documentos(hallazgos, segmentos):
    """Cada hallazgo (y cada una de sus ubicaciones) sabe en qué subdocumento y en
    qué hojas está. Los hallazgos por AUSENCIA quedan a nivel de expediente."""
    for h in hallazgos:
        for u in h.ubicaciones or []:
            i, sg = _documento_de(u.get("pagina", 0), segmentos)
            u["documento"] = sg.etiqueta if sg else ""
            u["documento_idx"] = i
        pags = [u["pagina"] for u in (h.ubicaciones or []) if u.get("pagina")]
        if not pags:
            h.documento, h.documento_idx = "Expediente completo", -1
            continue
        i, sg = _documento_de(pags[0], segmentos)
        if sg:
            h.documento, h.documento_idx = sg.etiqueta, i
            h.documento_paginas = [sg.pagina_ini, sg.pagina_fin]
        else:
            h.documento, h.documento_idx = "Hojas sin documento identificado", -1
    return hallazgos

def _mencion(doc, anclas, excluir=()):
    """Segunda revisión: ¿se menciona en cualquier parte del texto (fuera del TDR)?"""
    pats = [re.compile(r"\b" + re.escape(norm(a)) + r"S?\b") for a in anclas]
    for pg in doc.pages:
        if pg.number in excluir: continue
        for ln in pg.lines:
            if any(p.search(norm(ln.text)) for p in pats):
                return ln
    return None

def _find_doc(doc, anclas, excluir=()):
    """Busca un DOCUMENTO por su título: palabra completa, en el 40% superior de la
    página, sin contar cláusulas numeradas (p. ej. '14. DECLARACIÓN JURADA' de un TDR)
    y fuera de las páginas del TDR (que mencionan todo)."""
    pats = [re.compile(r"\b" + re.escape(norm(a)) + r"S?\b") for a in anclas]
    for pg in doc.pages:
        if pg.number in excluir: continue
        for ln in pg.lines:
            if (ln.bbox[1] + ln.bbox[3]) / 2 > 0.40: continue
            t = norm(ln.text)
            if _CLAUSULA.match(t): continue
            if any(p.search(t) for p in pats):
                return ln
    return None


# expresiones típicas (se citan, no se califican)
PAT_SUBORDINACION = [r"\bHORARIO\b", r"\bJORNADA\b", r"LUNES A VIERNES", r"\b\d{1,2}[:.]\d{2}\s*(AM|PM|HORAS|HRS)\b",
                     r"MARCACION", r"CONTROL DE ASISTENCIA", r"SUBORDINA", r"BAJO (LA )?DEPENDENCIA",
                     r"CUMPLIR (EL )?HORARIO", r"PERMANENCIA"]
PAT_RESTRICCION = [r"\bMARCA\b", r"EXCLUSIVAMENTE", r"UNICO PROVEEDOR", r"SOLO SE ACEPTARA",
                   r"NO SE ACEPTARAN EQUIVALENTES", r"EXPERIENCIA MINIMA DE \d{2,}"]

def _buscar_citas(doc, patrones, paginas=None):
    pats = [re.compile(p) for p in patrones]
    out = []
    for pg in doc.pages:
        if paginas and pg.number not in paginas: continue
        for ln in pg.lines:
            if any(p.search(norm(ln.text)) for p in pats):
                out.append(ln)
    return out

def detectar(doc, kb, familia, accumulator=None, contexto=None, segmentos=None, verificados=None):
    """doc=OCRDocument, kb=lista de riesgos, familia='CM'|'LS'.
    accumulator: dict persistente {clave_objeto: [montos]} para fraccionamiento.
    contexto: dict opcional {objeto, meta, monto, ruc, fecha} del expediente."""
    conf_doc = _conf_prom(doc)
    umbral = umbral_de(doc)
    pags_tdr = {p for sg in (segmentos or []) if sg.tipo in ("tdr", "pedido_servicio")
                for p in range(sg.pagina_ini, sg.pagina_fin + 1)}
    pags_solo_tdr = {p for sg in (segmentos or []) if sg.tipo == "tdr"
                     for p in range(sg.pagina_ini, sg.pagina_fin + 1)}
    texto_norm = norm(doc.text())
    hall = []
    for r in kb:
        if r["familia"] != familia:
            continue
        modo = r["deteccion_pista"]; clase = r["deteccion"]
        nivel = None; pag=1; bbox=[0.06,0.06,0.94,0.16]; conf=conf_doc; nota=""; evidencia=""; ubic=[]

        if clase == "ASSIST":
            rn = norm(r["hecho"])
            pats = None
            if any(k in rn for k in ("SUBORDIN", "HORARIO", "PERSONAL SUJETA", "NATURALEZA")):
                pats = PAT_SUBORDINACION
            elif any(k in rn for k in ("RESTRIN", "DIRECCION")):
                pats = PAT_RESTRICCION
            nivel = "amarillo"
            citas = _buscar_citas(doc, pats, pags_tdr or None) if pats else []
            if citas:
                ln0 = citas[0]
                pag, bbox, conf = ln0.page, list(ln0.bbox), ln0.conf
                evidencia = " | ".join(f"«{c.text.strip()[:140]}» (pág. {c.page})" for c in citas[:4])
                ubic = [{"pagina": c.page, "bbox": list(c.bbox), "texto": c.text.strip()[:140]} for c in citas[:6]]
                nota = "Se encontraron expresiones que podrían configurar el riesgo; valórelas con el procedimiento."
            else:
                nota = "No se hallaron expresiones típicas; igual requiere lectura de la persona."
        elif clase == "REVIEW":
            nivel = "amarillo"; nota = "Riesgo de criterio: verifíquelo con el procedimiento de auditoría."

        elif modo == "presencia":
            # ¿qué documento/elemento se espera? se infiere del texto del riesgo
            rn = norm(r["hecho"]); objetivo=None; clave_doc=None
            for key,anclas in ANCLA_DOC.items():
                if any(norm(a) in rn for a in anclas) or re.search(r"\b" + key + r"\b", rn):
                    objetivo=anclas; clave_doc=key; break
            tipo_seg = SEG_DE_ANCLA.get(clave_doc)
            seg_doc = next((sg for sg in (segmentos or []) if tipo_seg and sg.tipo == tipo_seg), None)
            if objetivo and seg_doc is not None:
                # el segmentador ya lo ubicó como documento propio: obra en el expediente
                nivel = None
                if verificados is not None:
                    verificados.append({"id": r["id"], "hecho": r["hecho"], "nivel_matriz": r.get("nivel", ""),
                        "motivo": f"Obra como documento propio: {seg_doc.etiqueta} "
                                  f"(pág. {seg_doc.pagina_ini}{'–' + str(seg_doc.pagina_fin) if seg_doc.pagina_fin != seg_doc.pagina_ini else ''}).",
                        "pagina": seg_doc.pagina_ini})
            elif objetivo:
                ln=_find_doc(doc, objetivo, excluir=pags_solo_tdr)
                if ln is None:      # 1ra revisión: no hay documento con ese título
                    ln2 = _mencion(doc, objetivo, excluir=pags_solo_tdr)   # 2da revisión: texto completo
                    buscado = ", ".join(a.title() for a in objetivo)
                    if ln2 is None:
                        nivel = "rojo" if conf_doc >= umbral else "amarillo"
                        nota = f"No obra en el expediente (revisado dos veces: títulos y texto completo): {buscado}."
                        evidencia = f"Se revisaron las {doc.n_pages} páginas (sin contar el TDR)."
                        if nivel == "amarillo":
                            nota += " La lectura del escaneo fue de baja calidad; confírmelo."
                    else:
                        nivel = "amarillo"
                        pag, bbox, conf = ln2.page, list(ln2.bbox), ln2.conf
                        nota = f"No se halló el documento como tal ({buscado}), aunque se menciona en el expediente."
                        evidencia = f"«{ln2.text.strip()[:140]}» (pág. {ln2.page})"
                        ubic = [{"pagina": ln2.page, "bbox": list(ln2.bbox), "texto": ln2.text.strip()[:140]}]
                else:               # sí obra -> sin hallazgo por ausencia
                    nivel=None
                    if verificados is not None:
                        verificados.append({"id": r["id"], "hecho": r["hecho"], "nivel_matriz": r.get("nivel", ""),
                            "motivo": f"Se ubicó «{ln.text.strip()[:90]}» (pág. {ln.page}).", "pagina": ln.page})
            else:
                nivel="amarillo"; nota="Verificación de presencia: revisar manualmente."

        elif modo == "fecha":
            # Solo se listan las fechas leídas y dónde; la comparación exigida por
            # el procedimiento la confirma la persona (no se afirma 'rojo').
            vistas = []
            for pg in doc.pages:
                for ln in pg.lines:
                    for fch in fechas_en(ln.text):
                        vistas.append((fch, pg.number, ln))
            nivel = "amarillo"
            if vistas:
                vistas.sort(key=lambda t: t[0])
                f0, pag, ln0 = vistas[0][0], vistas[0][1], vistas[0][2]
                bbox, conf = list(ln0.bbox), ln0.conf
                uniq = []
                for fch, pgn, lnx in vistas:
                    _, sgx = _documento_de(pgn, segmentos)
                    tag = f"{fch.strftime('%d/%m/%Y')} (pág. {pgn}{', ' + sgx.etiqueta if sgx else ''})"
                    if tag not in uniq:
                        uniq.append(tag)
                        if len(ubic) < 8:
                            ubic.append({"pagina": pgn, "bbox": list(lnx.bbox),
                                         "texto": f"{fch.strftime('%d/%m/%Y')} — {lnx.text.strip()[:110]}"})
                evidencia = "; ".join(uniq[:12]) + (" …" if len(uniq) > 12 else "")
                nota = "Contraste las fechas según el procedimiento de auditoría."
            else:
                nota = "No se leyeron fechas legibles; verifique en el expediente físico o el SIGA."

        elif modo == "acumulacion":
            ctx = contexto or {}
            monto_exp = ctx.get("monto") or 0
            fiable = bool(monto_exp) and ctx.get("monto_fuente") == "orden"
            clave = ctx.get("objeto") or "(objeto no identificado)"
            previos = list((accumulator or {}).get(clave, []))
            total = sum(previos) + (monto_exp or 0)
            partes = []
            if monto_exp:
                partes.append(f"Monto de la orden: S/ {monto_exp:,.2f} ({monto_exp/UIT_2026:.2f} UIT)")
            if previos:
                partes.append(f"Acumulado del objeto «{(ctx.get('objeto_txt') or clave)[:70]}» en el ejercicio: S/ {total:,.2f} en {len(previos)+1} órdenes")
            evidencia = "; ".join(partes)
            usa_acum = any(k in norm(r["hecho"]) for k in ("VARIAS", "MISMO", "CORRELATIV", "CONCENTRE",
                                                           "MISMA NECESIDAD", "UNICO REQUERIMIENTO"))
            if usa_acum:
                # riesgo de fraccionamiento: lo que importa es el ACUMULADO del objeto
                if previos and total > TOPE_8UIT:
                    nivel = "rojo" if fiable else "amarillo"
                    nota = (f"El acumulado del mismo objeto supera las 8 UIT "
                            f"(S/ {total:,.2f} de S/ {TOPE_8UIT:,.0f}).")
            else:
                # riesgo del valor de ESTA orden: pegado al tope de 8 UIT
                if monto_exp and monto_exp >= 0.9 * TOPE_8UIT:
                    nivel = "rojo" if (fiable and conf_doc >= umbral) else "amarillo"
                    nota = f"El valor de la orden alcanza el {monto_exp/TOPE_8UIT:.0%} del tope de 8 UIT (S/ {TOPE_8UIT:,.0f})."
            if nivel is None:
                if not monto_exp:
                    nivel = "amarillo"; nota = "No se pudo leer el monto de la orden; revise."
                elif verificados is not None:
                    verificados.append({"id": r["id"], "hecho": r["hecho"], "nivel_matriz": r.get("nivel", ""),
                        "motivo": (evidencia + ". Dentro del tope de 8 UIT (S/ 44,000)"
                                   + (" con las órdenes procesadas hasta hoy." if usa_acum else ".")),
                        "pagina": pag})
            if ln_monto := ctx.get("monto_linea"):
                pag, bbox = ln_monto.page, list(ln_monto.bbox)
                ubic = [{"pagina": pag, "bbox": bbox, "texto": ln_monto.text.strip()[:140]}]

        else:
            nivel="amarillo"; nota="Revisar manualmente."

        if nivel:
            hall.append(Hallazgo(
                id=r["id"], nivel=nivel, hecho=r["hecho"], base_legal=r["base_legal"],
                control=r["control"], ejecuta=r["ejecuta"], supervisa=r["supervisa"],
                pagina=pag, bbox=bbox, confianza=round(conf,3),
                subproceso=r["subproceso"], familia=familia, deteccion=clase,
                nota=nota, ejemplo=r.get("ejemplo"),
                nivel_matriz=r.get("nivel",""), actividad=r.get("actividad",""),
                como_verificar=(r.get("procedimientos") or [{}])[0].get("procedimiento",""),
                evidencia=evidencia, ubicaciones=ubic))
    return ubicar_en_documentos(hall, segmentos)
