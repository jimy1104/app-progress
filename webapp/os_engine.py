# -*- coding: utf-8 -*-
"""Segmentador de expedientes: decide dónde empieza y termina cada documento.

Reglas aprendidas de los expedientes reales de la Oficina:

1. Un documento se reconoce por su TÍTULO en la cabecera de la hoja, no por
   cualquier mención en el cuerpo. Un informe que dice «…a la ORDEN DE SERVICIO
   N° 0010559» NO es una orden de servicio.
2. Por eso cada tipo exige SEÑALES PROPIAS: una orden impresa del SIGA siempre
   trae «UNIDAD EJECUTORA», «DATOS DEL PROVEEDOR» o «SISTEMA INTEGRADO DE
   GESTIÓN». Si no están, la mención se ignora.
3. El OCR rompe las tildes («TÉRMINOS» -> «T RMINOS», «DENOMINACIÓN» ->
   «DENOMINACIN»), así que las anclas se comparan de forma tolerante.
4. Las hojas en blanco del final de un documento (el reverso de la última hoja)
   no forman parte del corte; las intermedias sí se conservan.

Versión 5 — decisión GLOBAL (programación dinámica sobre todas las hojas)
------------------------------------------------------------------------
Antes cada hoja se juzgaba sola: si tenía título abría documento; si no, se
pegaba al anterior. Eso fallaba en dos casos: (a) un documento sin título
reconocible (una carta, una ficha RUC) quedaba absorbido por el documento previo
y el corte salía con hojas de más; (b) dos órdenes seguidas se fundían en una.

Ahora cada hoja aporta EVIDENCIA a favor de «sigue el documento» o de «empieza
uno nuevo», y el algoritmo de Viterbi elige la partición del expediente entero
que mejor explica toda la evidencia a la vez:

  empieza   título del tipo (con sus señales propias), rol «title» de Azure,
            «Página 1 de N», cambio de membrete, número de documento distinto.
  sigue     «Página k de N» (k>1), «VIENEN…» (SIGA), mismo N° de documento,
            mismo membrete que la hoja anterior, vocabulario del mismo tipo.
  en contra un título FUERTE de otro tipo en esta hoja; exceder las hojas de un
            documento de tamaño fijo (factura y conformidad: 1 hoja).

Los documentos sin título conocido salen como «Otro documento: <título leído>»,
en lugar de contaminar el corte vecino. Cada hoja queda descrita (a qué documento
pertenece, si es inicio, continuación o reverso en blanco, y por qué).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import re, unicodedata
from difflib import SequenceMatcher
from ocr.base import OCRDocument

ZONA_CABECERA = 0.45      # se buscan los títulos en el 45% superior de la hoja
ZONA_MEMBRETE = 0.22      # el membrete (lo que se repite hoja a hoja) vive arriba
TITULO_MAX = 75           # un título es una línea corta; el cuerpo es largo
UMBRAL_FUZZY = 0.86       # tolerancia a errores de OCR en el ancla
MIN_CARACTERES = 25       # menos que esto = hoja en blanco (reverso)


def normaliza(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.upper()
    txt = re.sub(r"[^A-Z0-9 ]+", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def _compacta(txt: str) -> str:
    """Sin espacios ni signos: absorbe los cortes de palabra del OCR
    («T RMINOS» -> «TRMINOS»)."""
    return re.sub(r"[^A-Z0-9]", "", normaliza(txt))


def _buscar(texto: str, ancla: str, umbral: float = UMBRAL_FUZZY):
    """Busca 'ancla' dentro de 'texto' tolerando errores del OCR.
    Devuelve (puntaje, posición) o (0, -1) si no aparece."""
    i = texto.find(ancla)
    if i >= 0:
        return 1.0, i
    n = len(ancla)
    if n < 8 or len(texto) < n - 2:
        return 0.0, -1
    mejor, pos = 0.0, -1
    sm = SequenceMatcher(autojunk=False)
    sm.set_seq2(ancla)
    for i in range(0, len(texto) - n + 3):
        sm.set_seq1(texto[i:i + n + 2])
        if sm.real_quick_ratio() < umbral or sm.quick_ratio() < umbral:
            continue
        r = sm.ratio()
        if r > mejor:
            mejor, pos = r, i
            if mejor > 0.97:
                break
    return (mejor, pos) if mejor >= umbral else (0.0, -1)


def _parecido(texto: str, ancla: str, umbral: float = UMBRAL_FUZZY) -> float:
    return _buscar(texto, ancla, umbral)[0]


_ARTICULOS = ("LOS", "LAS", "DEL", "DE", "EN", "LA", "EL", "AL", "A", "Y", "CON", "POR", "SEGUN")


def _encabeza(texto: str, pos: int) -> bool:
    """¿El título empieza la línea? Se admite un numeral delante («1. TÉRMINOS…») y
    un fragmento corto que el OCR pegó desde la izquierda (el pie del logo:
    «CALLAO TÉRMINOS DE REFERENCIA»), siempre que no sea un artículo o preposición
    («…de LOS términos de referencia» es una mención, no un título)."""
    i = pos
    while i > 0 and texto[i - 1].isdigit():
        i -= 1
    if i == 0 or texto[i - 1] == "|":
        return True
    ini = texto.rfind("|", 0, i) + 1
    prefijo = texto[ini:i]
    return len(prefijo) <= 8 and not prefijo.endswith(_ARTICULOS)


# ---------------------------------------------------------------- catálogo ---
# anclas   : títulos que identifican el documento
# requiere : al menos una de estas señales debe estar en la hoja (evita que una
#            simple mención abra un documento nuevo)
# excluye  : si el título va precedido de esto, es una referencia, no un título
# hojas    : documentos de tamaño fijo (la factura y la conformidad son de 1 hoja)
# vocab    : vocabulario típico del CUERPO (ayuda a decidir si una hoja sin título
#            sigue siendo del mismo documento)
DOCS = {
    "orden_servicio": dict(
        etiqueta="Orden de Servicio",
        anclas=["ORDENDESERVICION", "ORDENDECOMPRAN"],
        requiere=["SISTEMAINTEGRADODEGESTI", "MODULODELOGISTICA", "UNIDADEJECUTORA",
                  "DATOSDELPROVEEDOR", "CUADROADQUISIC"],
        excluye=["ALAORDENDESERVICIO", "CONFORMIDADALAORDEN", "RELACIONALAORDEN",
                 "CORRESPONDIENTEALAORDEN", "NOTIFICACIONDELAORDEN", "RECEPCIONDELAORDEN"],
        vocab=["UNIDADEJECUTORA", "DATOSDELPROVEEDOR", "CONDICIONESGENERALES", "AFECTACION",
               "CADENAFUNCIONAL", "CLASIFGASTO", "FACTURARANOMBRE", "RESPONSABLEDEADQUISICIONES",
               "SISTEMAINTEGRADO", "VIENEN", "NOTAIMPORTANTE", "EXPSIAF", "CUADROADQUISIC"],
        hojas=None),
    "pedido_servicio": dict(
        etiqueta="Pedido / Requerimiento",
        anclas=["PEDIDODESERVICION", "PEDIDODECOMPRAN", "PEDIDODEBIENES"],
        requiere=["UNIDADEJECUTORA", "NROIDENTIFICACION", "ACTIVIDADOPERATIVA", "AREASOLICITANTE"],
        excluye=[],
        vocab=["AREASOLICITANTE", "ACTIVIDADOPERATIVA", "NROIDENTIFICACION", "JUSTIFICACION",
               "METAPRESUPUESTAL", "UNIDADDEMEDIDA", "UNIDADEJECUTORA"],
        hojas=None),
    "tdr": dict(
        etiqueta="Términos de Referencia (TDR)",
        anclas=["TERMINOSDEREFERENCIA", "DENOMINACIONDELACONTRATACION",
                "ESPECIFICACIONESTECNICAS"],
        requiere=[], excluye=["ALOSTERMINOSDEREFERENCIA", "LOSPRESENTESTERMINOSDEREFERENCIA",
                              "ENLOSTERMINOSDEREFERENCIA", "CUMPLIMIENTODELOSTERMINOS",
                              "DEACUERDOALOSTERMINOS", "LOSTERMINOSDEREFERENCIA"],
        vocab=["DENOMINACIONDELACONTRATACION", "FINALIDADPUBLICA", "OBJETIVO", "AREAUSUARIA",
               "PLAZODEEJECUCI", "LUGARDE", "FORMADEPAGO", "PENALIDAD", "REQUISITOS",
               "CONFORMIDADDELAPRESTACI", "ENTREGABLE", "VICIOSOCULTOS", "ANTICORRUPCI",
               "CONTROVERSIAS", "MODALIDADDEPAGO", "CONFIDENCIALIDAD", "CLAUSULA", "ARBITRAJE"],
        inicio_linea=True, hojas=None),
    "certificacion": dict(
        etiqueta="Certificación de Crédito Presupuestario",
        anclas=["CERTIFICACIONDECREDITOPRESUPUESTARIO", "CERTIFICACIONPRESUPUESTAL"],
        requiere=["CREDITOPRESUPUESTARIO", "DETALLEDEGASTO", "CADENAFUNCIONAL", "META"],
        excluye=[],
        vocab=["CREDITOPRESUPUESTARIO", "CADENAFUNCIONAL", "FUENTEDEFINANCIAMIENTO", "RUBRO",
               "ESPECIFICADEGASTO", "DETALLEDEGASTO", "SIAF"],
        hojas=None),
    "conformidad": dict(
        etiqueta="Conformidad de Servicios",
        anclas=["CONFORMIDADDESERVICIO", "CONFORMIDADDESERVICIOS", "ACTADECONFORMIDAD"],
        requiere=[], excluye=["CONFORMIDADALA", "CONFORMIDADCORRESPONDIENTE", "LACONFORMIDADDEL",
                              "CONFORMIDADDELAPRESTACION", "BCONFORMIDADDESERVICIO",
                              "EMITIRLACONFORMIDAD", "BRINDARLACONFORMIDAD"],
        vocab=["FECHADECONFORMIDAD", "AREAQUEOTORGA", "VERIFICACIONDELAPRESTACI", "NOCONFORME",
               "MONTOPARCIAL", "PROVEEDOR", "OBSERVACI"],
        con_numero=True, hojas=1),
    "comprobante_pago": dict(
        etiqueta="Comprobante de Pago (Factura)",
        anclas=["FACTURAELECTRONICA", "RECIBOPORHONORARIOS", "BOLETADEVENTAELECTRONICA"],
        requiere=[], excluye=["CONLAFACTURA", "SUFACTURACOPIA"],
        vocab=["FACTURAELECTRONICA", "OPGRAVADA", "IGV", "IMPORTETOTAL", "VALORDEVENTA",
               "FECHADEEMISI", "REPRESENTACIONIMPRESA", "RECIBOPORHONORARIOS", "RETENCI"],
        hojas=1),
    "validez_cpe": dict(
        etiqueta="Consulta de validez del comprobante",
        anclas=["CONSULTAVALIDEZDELCOMPROBANTE"], requiere=[], excluye=[],
        vocab=["CONSULTAVALIDEZ", "COMPROBANTEDEPAGOELECTRONICO", "ESUNCOMPROBANTEVALIDO", "SUNAT"],
        hojas=1),
    "informe": dict(
        etiqueta="Informe",
        anclas=["INFORMEN", "INFORMEDELSERVICIO"], requiere=[],
        excluye=["REFERENCIAINFORMEN", "ELINFORMEN", "SEGUNINFORMEN", "MEDIANTEINFORMEN",
                 "CONELINFORMEN"],
        vocab=["ASUNTO", "REFERENCIA", "ANTECEDENTES", "ANALISIS", "CONCLUSION", "RECOMENDACION",
               "ATENTAMENTE"],
        hojas=None),
    "memorando": dict(
        etiqueta="Memorando",
        anclas=["MEMORANDON", "MEMORANDUMN", "OFICION"], requiere=[],
        excluye=["REFERENCIAMEMORANDON", "ELMEMORANDON", "SEGUNMEMORANDON", "MEDIANTEMEMORANDON",
                 "MEDIANTEOFICION"],
        vocab=["MEMORANDO", "ASUNTO", "REFERENCIA", "ATENTAMENTE"],
        hojas=None),
    "anexo": dict(
        etiqueta="Anexo / Declaración jurada",
        anclas=["ANEXO0", "ANEXON", "DECLARACIONJURADA"], requiere=[], excluye=[],
        vocab=["DECLARACIONJURADA", "DECLAROBAJOJURAMENTO", "ELQUESUSCRIBE", "IDENTIFICADO"],
        hojas=1),
    "cotizacion": dict(
        etiqueta="Cotización / Cuadro comparativo",
        anclas=["COTIZACIONN", "CUADROCOMPARATIVO", "PROFORMAN", "SOLICITUDDECOTIZACION"],
        requiere=[], excluye=[],
        vocab=["COTIZACION", "VALIDEZDELAOFERTA", "PRECIOUNITARIO", "PRECIOTOTAL", "PROFORMA",
               "CUADROCOMPARATIVO", "PROPUESTAECONOMICA"],
        inicio_linea=True, hojas=None),
    "cci": dict(
        etiqueta="Carta de autorización (CCI)",
        anclas=["CARTADEAUTORIZACION", "CODIGODECUENTAINTERBANCARIO", "AUTORIZACIONDEABONO"],
        requiere=["CUENTA", "BANCO", "CCI", "INTERBANCARI"], excluye=["ADJUNTARCARTADEAUTORIZACION"],
        vocab=["CODIGODECUENTAINTERBANCARI", "BANCO", "ABONO", "CUENTA", "CCI"],
        inicio_linea=True, hojas=1),
    "rnp": dict(
        etiqueta="Constancia RNP",
        anclas=["REGISTRONACIONALDEPROVEEDORES", "CONSTANCIADEINSCRIPCION"],
        requiere=["RNP", "OSCE", "PROVEEDOR", "VIGENCIA"], excluye=["CONTARCONRNP", "INSCRITOENEL"],
        vocab=["REGISTRONACIONALDEPROVEEDORES", "RNP", "VIGENCIA", "OSCE", "CONSTANCIA"],
        inicio_linea=True, hojas=1),
    "ficha_ruc": dict(
        etiqueta="Ficha / Consulta RUC",
        anclas=["FICHARUC", "CONSULTARUC", "REPORTEFICHARUC", "CONSULTADERUC"],
        requiere=["CONTRIBUYENTE", "SUNAT", "DOMICILIOFISCAL"], excluye=[],
        vocab=["CONTRIBUYENTE", "ESTADODELCONTRIBUYENTE", "CONDICIONDELCONTRIBUYENTE", "HABIDO",
               "DOMICILIOFISCAL", "ACTIVIDADECONOMICA", "SUNAT"],
        hojas=None),
    "contrato": dict(
        etiqueta="Contrato",
        anclas=["CONTRATON"], requiere=["CLAUSULA", "CONTRATISTA", "LASPARTES", "LAENTIDAD"],
        excluye=["ELCONTRATON", "DELCONTRATON", "ALCONTRATON"],
        vocab=["CONTRATISTA", "OBJETODELCONTRATO", "LASPARTES", "SUSCRIBEN", "DOMICILIO"],
        inicio_linea=True, hojas=None),
    "otro": dict(
        etiqueta="Otro documento", anclas=[], requiere=[], excluye=[], vocab=[], hojas=None),
}

# etiquetas de los campos de un memorando/oficio (cuando no se lee el título)
CAMPOS_MEMO = ["ASUNTO", "REFERENCIA", "FECHA", "DE", "A"]

# opciones a)-d) de la interfaz -> tipos de documento
CORTES_UI = {"tdr": "tdr", "requerimiento": "pedido_servicio",
             "pago": "comprobante_pago", "os": "orden_servicio"}

# tipos "débiles": sus títulos también aparecen como cláusulas dentro de un TDR
DEBILES = {"anexo", "informe", "memorando", "cotizacion", "cci", "rnp", "contrato"}


@dataclass
class Segmento:
    tipo: str
    etiqueta: str
    pagina_ini: int
    pagina_fin: int
    confianza: float
    titulo: str = ""                      # el título tal como se leyó
    evidencia: float = 0.0                # fuerza de la decisión de corte (0..1)
    revisar: bool = False                 # el corte es dudoso: conviene mirarlo
    blancas: List[int] = field(default_factory=list)       # reversos en blanco intermedios


def _lineas_cabecera(pg):
    return [l for l in pg.lines if (l.bbox[1] + l.bbox[3]) / 2 <= ZONA_CABECERA]


_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]{3,}")


def texto_util(pg) -> str:
    """Texto de la página descartando la basura del OCR.

    En una hoja en blanco (el reverso de una copia) el OCR local devuelve
    manchas sueltas: trozos de 1–2 letras con confianza muy baja. Aquí se
    conservan solo las palabras legibles (3+ caracteres y confianza decente),
    que es lo que de verdad permite decir si la hoja tiene contenido."""
    buenas = []
    for ln in pg.lines:
        ps = ln.words or []
        if ps:
            buenas += [w.text for w in ps if w.conf >= 0.45 and _PALABRA.fullmatch(w.text or "")]
        elif ln.conf >= 0.45:
            buenas += [t for t in (ln.text or "").split() if _PALABRA.fullmatch(t)]
    return " ".join(buenas)


def _pagina_vacia(pg) -> bool:
    if (getattr(pg, "meta", None) or {}).get("en_blanco"):
        return True
    if len(normaliza(pg.text)) < MIN_CARACTERES:
        return True
    return len(normaliza(texto_util(pg))) < MIN_CARACTERES


def _es_memo(pg) -> bool:
    """Memorando/oficio reconocido por sus campos (A:, DE:, ASUNTO:, ...)."""
    cortas = {normaliza(l.text) for l in _lineas_cabecera(pg) if len(normaliza(l.text)) <= 14}
    return sum(1 for c in CAMPOS_MEMO if c in cortas) >= 3


def _titulos_de_pagina(pg) -> dict:
    """{tipo: (puntaje, texto_del_titulo)} de cada tipo cuyo título ABRE la hoja."""
    cab = _lineas_cabecera(pg)
    if not cab:
        return {}
    # El título puede venir pegado al membrete en una sola línea larga, así que se
    # busca en toda la cabecera; '|' separa líneas para no unir palabras de líneas
    # distintas por accidente.
    lineas_cab = [_compacta(l.text) for l in cab]
    texto_cab = "|".join(lineas_cab)
    texto_pagina = _compacta(pg.text)
    out = {}
    for tipo, d in DOCS.items():
        if not d["anclas"]:
            continue
        if d["requiere"] and not any(_parecido(texto_pagina, r, 0.90) for r in d["requiere"]):
            continue
        for ancla in d["anclas"]:
            # Se mira la cabecera entera (por si el título viene partido en dos
            # renglones) y también renglón por renglón: cuando el OCR se come una
            # letra («T~RMINOS»), la ventana difusa puede correrse unos caracteres
            # y hacer creer que el título va en medio del texto. Renglón a
            # renglón eso no pasa.
            for k, texto in enumerate([texto_cab] + lineas_cab):
                score, pos = _buscar(texto, ancla)
                if not score:
                    continue
                # la exclusión se juzga SOLO en el contexto inmediato del título:
                # «…conformidad A LA ORDEN DE SERVICIO…» es una referencia, no un título
                ctx = texto[max(0, pos - 45): pos + len(ancla) + 5]
                if any(_parecido(ctx, e, 0.97) for e in d["excluye"]):
                    continue
                # anclas genéricas: solo valen si ENCABEZAN la línea (no en medio del cuerpo)
                if d.get("inicio_linea") and not _encabeza(texto, pos):
                    continue
                # títulos que llevan número: «CONFORMIDAD DE SERVICIOS N° 300-2026».
                # Sin número es una mención («la conformidad del servicio estará a cargo…»)
                if d.get("con_numero") and not re.match(r"[SNO]{0,3}\d", texto[pos + len(ancla): pos + len(ancla) + 10]):
                    continue
                # renglón donde está el título (en la cabecera unida, por los '|')
                ln = cab[k - 1] if k > 0 else cab[min(len(cab) - 1, texto.count("|", 0, pos))]
                if ln is not None and ln.role in ("title", "sectionHeading"):
                    score = min(1.0, score + 0.1)       # Azure también lo ve como título
                if tipo not in out or score > out[tipo][0]:
                    out[tipo] = (score, (ln.text if ln is not None else "").strip()[:120])
    # Una hoja con el membrete del TDR que menciona «declaración jurada», «informe» o
    # «anexo» en una cláusula sigue siendo TDR: esos títulos débiles no cuentan.
    if "tdr" in out:
        for t in list(out):
            if t in DEBILES:
                del out[t]
    if not out and _es_memo(pg):
        out["memorando"] = (0.75, "")
    return out


def _tipo_de_pagina(pg):
    """Devuelve (tipo, confianza) si la hoja ABRE un documento; si no, None."""
    t = _titulos_de_pagina(pg)
    if not t:
        return None
    tipo = max(t, key=lambda k: t[k][0])
    return (tipo, t[tipo][0])


def detectar_inicios(doc: OCRDocument):
    out = []
    for pg in doc.pages:
        r = _tipo_de_pagina(pg) if pg.lines else None
        if r is None:
            continue
        confs = [l.conf for l in _lineas_cabecera(pg)]
        out.append((pg.number, r[0], sum(confs) / len(confs) if confs else 0.0))
    return out


# ------------------------------------------------------------------ rasgos ---
_RE_PAG = re.compile(r"\b(?:PAG(?:INA)?|HOJA)\W{0,3}(\d{1,2})\s*(?:DE|/)\s*(\d{1,2})\b")
_RE_NUM = re.compile(r"\bN(?:RO|O|UMERO)?(?:\s+[A-Z]{1,2}(?=\s))?\s+0*(\d{2,8})(?:\s+(20\d\d))?\b")
_RE_VIENEN = re.compile(r"\bVIENEN\b")
_RE_VAN = re.compile(r"\bVAN\b\s*(?:S\b|\.|$)")
_MEMBRETE_COMUN = {"MUNICIPALIDAD", "PROVINCIAL", "CALLAO", "FOLIO", "GERENCIA", "OFICINA",
                   "LOGISTICA", "ADMINISTRACION"}          # sellos y membrete institucional
_GENERICO = re.compile(r"^(?:CARTA|SOLICITUD|CONSTANCIA|CERTIFICADO|ACTA|RESOLUCION|INFORME|"
                       r"DECLARACION|REQUERIMIENTO|NOTA|OFICIO|CONTRATO|ADENDA|LIQUIDACION|"
                       r"REPORTE|RECIBO|COMPROBANTE|PLANILLA|VALORIZACION|ENTREGABLE|PLAN|"
                       r"CUADRO|FICHA|FORMATO|ANEXO|PROPUESTA|EXPEDIENTE|DECRETO|PROVEIDO|HOJA DE)\b")


@dataclass
class Rasgos:
    numero: int
    vacia: bool
    titulos: dict                    # tipo -> (puntaje, texto)
    generico: tuple                  # (puntaje, texto) de un título no catalogado
    numeros: set                     # N° de documento leídos en la cabecera
    pag: Optional[tuple]             # (k, n) de «Página k de n»
    vienen: bool
    van: bool
    membrete: set
    vocab: dict                      # tipo -> 0..1
    conf: float


def _vocab(texto_c):
    out = {}
    for tipo, d in DOCS.items():
        v = d.get("vocab") or []
        if v:
            hits = sum(1 for k in v if k in texto_c)
            out[tipo] = min(1.0, hits / 3.0)
    return out


def _numeros(pg, titulos, generico):
    """N° del documento: se lee SOLO del renglón del título (o del renglón siguiente,
    donde el SIGA suele dejar el número). Los folios, el N° de expediente SIAF o el
    RUC no identifican al documento y confundirían la comparación hoja a hoja."""
    cab = _lineas_cabecera(pg)
    textos_titulo = {t for _, t in titulos.values() if t} | ({generico[1]} if generico[1] else set())
    nums = set()
    for i, ln in enumerate(cab):
        if ln.text.strip()[:120] not in textos_titulo:
            continue
        for cand in [ln] + cab[i + 1:i + 2]:
            t = normaliza(cand.text)
            if cand is not ln and not re.fullmatch(r"\W*N?\W*0*\d{3,8}\W*", t):
                continue
            if cand is not ln:
                t = "N " + re.sub(r"\D", "", t)
            for m in _RE_NUM.finditer(t):
                if len(m.group(1)) >= 3:
                    nums.add(m.group(1) + ("-" + m.group(2) if m.group(2) else ""))
    return nums


def _tam_letra(ln) -> float:
    """Tamaño de letra aproximado a partir del alto de la caja del renglón. Una
    línea en MAYÚSCULAS sin letras con descendente mide solo la altura de las
    mayúsculas (~72% del cuerpo); una en minúsculas con g, j, p, q, y mide el cuerpo
    casi completo. Sin esta corrección un título grande en mayúsculas parece del
    mismo tamaño que el texto normal."""
    alto = ln.bbox[3] - ln.bbox[1]
    letras = [c for c in (ln.text or "") if c.isalpha()]
    if not letras:
        return alto
    desc = any(c in "gjpqy,;" for c in ln.text)
    mayus = all(c.isupper() for c in letras)
    factor = (0.72 if mayus else 0.76) + (0.2 if desc else 0.0)
    return alto / factor


def _prominente(ln, tam_medio):
    """¿El renglón se destaca como título? (letra más grande que la normal, o
    centrado y corto). Evita tomar «Referencia: Carta N° …» del cuerpo como título."""
    centro = (ln.bbox[0] + ln.bbox[2]) / 2
    return (tam_medio > 0 and _tam_letra(ln) >= 1.15 * tam_medio) or \
           (0.35 <= centro <= 0.65 and (ln.bbox[2] - ln.bbox[0]) <= 0.6)


def _generico(pg):
    """Título de un documento que no está en el catálogo (carta, constancia…)."""
    mejor = (0.0, "")
    tams = sorted(_tam_letra(l) for l in pg.lines if len((l.text or "").strip()) >= 8)
    tam_medio = tams[len(tams) // 2] if tams else 0.0
    for ln in _lineas_cabecera(pg):
        t = normaliza(ln.text)
        if not (6 <= len(t) <= 70) or ln.manuscrita:
            continue
        palabras = set(t.split())
        if palabras and palabras <= _MEMBRETE_COMUN | {"DEL", "DE", "LA", "EL"}:
            continue
        s = 0.0
        if ln.role == "title":
            s = 0.8
        elif ln.role == "sectionHeading":
            s = 0.5
        if _GENERICO.match(t):
            con_numero = bool(re.search(r"\bN(?:RO|O)?\s*\d", t))
            if ln.role in ("title", "sectionHeading") or _prominente(ln, tam_medio):
                s = max(s, 0.8 if con_numero else 0.6) + (0.2 if con_numero else 0.0)
            else:
                s = max(s, 0.3)
        if s > mejor[0]:
            mejor = (min(1.0, s), ln.text.strip()[:120])
    return mejor


def rasgos_de(pg) -> Rasgos:
    vacia = _pagina_vacia(pg)
    if vacia:
        return Rasgos(pg.number, True, {}, (0.0, ""), set(), None, False, False, set(), {}, 0.0)
    texto_n = normaliza(pg.text)
    m = _RE_PAG.search(texto_n)
    pag = (int(m.group(1)), int(m.group(2))) if m and 0 < int(m.group(1)) <= int(m.group(2)) <= 60 else None
    membrete = {w for l in pg.lines if (l.bbox[1] + l.bbox[3]) / 2 <= ZONA_MEMBRETE
                for w in normaliza(l.text).split() if len(w) >= 4 and not w.isdigit()}
    confs = [l.conf for l in _lineas_cabecera(pg)]
    titulos, generico = _titulos_de_pagina(pg), _generico(pg)
    return Rasgos(pg.number, False, titulos, generico, _numeros(pg, titulos, generico), pag,
                  bool(_RE_VIENEN.search(texto_n)), bool(_RE_VAN.search(texto_n)), membrete,
                  _vocab(_compacta(pg.text)), sum(confs) / len(confs) if confs else 0.0)


def _similar(a: set, b: set) -> float:
    """Parecido del membrete de dos hojas. Se usa el SOLAPAMIENTO (no Jaccard):
    la zona alta también recoge renglones del cuerpo, que cambian de hoja a hoja
    y diluirían el parecido del membrete que sí se repite."""
    a2, b2 = a - _MEMBRETE_COMUN, b - _MEMBRETE_COMUN
    if len(a2) < 3 or len(b2) < 3:
        return 0.0
    return len(a2 & b2) / min(len(a2), len(b2))


# ------------------------------------------------------------------ pesos ----
# Puntos de evidencia (escala tipo log-verosimilitud). Calibrados con los
# expedientes reales de la Oficina; ver benchmark.py para volver a medirlos.
PESOS = dict(
    nuevo=3.0,          # costo de abrir un documento (sin evidencia no se corta)
    otro=1.0,           # costo extra de abrir un documento no catalogado
    mismo_tipo=5.0,     # costo extra de abrir un doc. del MISMO tipo que el actual
    titulo_mismo=3.0,   # la hoja repite el título del documento en curso (membrete del TDR,
                        # cabecera del SIGA en cada hoja de la orden): es continuación
    titulo=6.0,         # título del tipo, con sus señales propias
    generico=5.0,       # título no catalogado (carta, constancia…)
    vocab=1.5,          # vocabulario del tipo en el cuerpo de la hoja
    pag1=2.5,           # «Página 1 de N»
    pag_sigue=5.0,      # «Página k de N», k>1, coherente con la hoja anterior
    vienen=4.0,         # «VIENEN» (continuación de orden SIGA)
    van_prev=3.0,       # la hoja anterior decía «VAN»
    num_igual=3.0,      # mismo N° de documento que la hoja anterior
    num_distinto=4.0,   # N° distinto con el mismo título: es OTRO documento
    membrete=2.5,       # mismo membrete que la hoja anterior
    cambio=1.5,         # membrete distinto al de la hoja anterior
    titulo_otro=4.0,    # hoja con título fuerte de OTRO tipo: no puede ser continuación
    sin_membrete=3.0,   # el documento repetía su título en cada hoja y esta ya no lo trae
    largo=4.0,          # por cada hoja que excede un documento de tamaño fijo
)


def _t(r: Rasgos, tipo):
    return r.titulos.get(tipo, (0.0, ""))[0]


def _puntaje_inicio(r: Rasgos, prev: Optional[Rasgos], tipo: str, actual: Optional[str]) -> float:
    P = PESOS
    s = -P["nuevo"]
    if tipo == "otro":
        s += -P["otro"] + P["generico"] * r.generico[0]
    else:
        s += P["titulo"] * _t(r, tipo)
    s += P["vocab"] * r.vocab.get(tipo, 0.0)
    if r.pag and r.pag[0] == 1:
        s += P["pag1"]
    if prev is not None:
        s += P["cambio"] * (1.0 - _similar(r.membrete, prev.membrete))
        if r.numeros and prev.numeros and not (r.numeros & prev.numeros) and _t(prev, tipo) > 0:
            s += P["num_distinto"]
    if actual == tipo:
        s -= P["mismo_tipo"]
    return s


def _puntaje_sigue(r: Rasgos, prev: Optional[Rasgos], tipo: str, k: int,
                   prev2: Optional[Rasgos] = None) -> float:
    P = PESOS
    s = P["vocab"] * r.vocab.get(tipo, 0.0)
    if r.pag and r.pag[0] > 1:
        s += P["pag_sigue"] if (prev is None or not prev.pag or prev.pag[0] < r.pag[0]) else 0.5 * P["pag_sigue"]
    if r.pag and r.pag[0] == 1:
        s -= P["pag1"]
    if r.vienen:
        s += P["vienen"]
    if prev is not None:
        if prev.van:
            s += P["van_prev"]
        if r.numeros and prev.numeros:
            if r.numeros & prev.numeros:
                s += P["num_igual"]
            elif _t(r, tipo) > 0 and _t(prev, tipo) > 0:
                s -= P["num_distinto"]
        s += P["membrete"] * _similar(r.membrete, prev.membrete)
    s += P["titulo_mismo"] * _t(r, tipo)
    # membrete que desaparece: las dos hojas anteriores traían el título (TDR, orden
    # del SIGA) y esta no. En un informe o una carta solo la 1ª hoja lo trae, así
    # que ahí no aplica.
    if k >= 2 and prev is not None and prev2 is not None and not _t(r, tipo) \
            and _t(prev, tipo) > 0 and _t(prev2, tipo) > 0 and not r.vienen \
            and not (r.pag and r.pag[0] > 1):
        # si el resto del membrete sigue igual, lo más probable es que el OCR no
        # alcanzó a leer el título: la penalidad se atenúa
        s -= P["sin_membrete"] * (1.0 - _similar(r.membrete, prev.membrete))
    # un título fuerte de otro tipo en esta hoja: difícilmente es continuación
    otros = [v[0] for t, v in r.titulos.items() if t != tipo]
    if r.generico[0] >= 0.9 and not _t(r, tipo):
        otros.append(r.generico[0])          # «CARTA N° 010-2026» bien destacado
    if otros:
        s -= P["titulo_otro"] * max(otros)
    hojas = DOCS[tipo]["hojas"]
    if hojas and k >= hojas:
        s -= P["largo"] * (k - hojas + 1)
    return s


# ---------------------------------------------------------------- Viterbi ----
KMAX = 3


def _viterbi(rs: List[Rasgos]):
    """Partición óptima. Devuelve [(tipo, pag_ini, pag_fin, margen_de_decision)]."""
    tipos = list(DOCS)
    llenas = [r for r in rs if not r.vacia]
    if not llenas:
        return []
    NEG = float("-inf")
    # estado: (tipo, k) ; k = hojas con contenido ya en el documento (tope KMAX)
    puntaje = {}
    atras = []            # por hoja con contenido: {estado: (estado_previo, empezó)}
    prev_r = prev2_r = None
    for idx, r in enumerate(llenas):
        nuevo, bp = {}, {}
        if idx == 0:
            for t in tipos:
                nuevo[(t, 1)] = _puntaje_inicio(r, None, t, None)
                bp[(t, 1)] = (None, True)
        else:
            mejor_prev = max(puntaje.items(), key=lambda kv: kv[1])
            for (t0, k0), s0 in puntaje.items():
                est = (t0, min(KMAX, k0 + 1))
                v = s0 + _puntaje_sigue(r, prev_r, t0, k0, prev2_r)
                if v > nuevo.get(est, NEG):
                    nuevo[est], bp[est] = v, ((t0, k0), False)
            for t in tipos:
                est = (t, 1)
                # el mejor estado previo desde el que abrir (considera 'mismo_tipo')
                cand = [(s0 + _puntaje_inicio(r, prev_r, t, t0), (t0, k0))
                        for (t0, k0), s0 in puntaje.items()]
                v, origen = max(cand, key=lambda c: c[0])
                if v > nuevo.get(est, NEG):
                    nuevo[est], bp[est] = v, (origen, True)
        puntaje = nuevo
        atras.append(bp)
        prev2_r, prev_r = prev_r, r
    # reconstrucción
    est = max(puntaje, key=puntaje.get)
    decisiones = []
    for idx in range(len(llenas) - 1, -1, -1):
        origen, empezo = atras[idx][est]
        decisiones.append((llenas[idx].numero, est[0], empezo))
        est = origen if origen is not None else est
    decisiones.reverse()
    # margen: qué tan clara fue cada decisión de corte/continuación
    margenes = {}
    prev_r = None
    tipo_act = None
    for (num, t, empezo), r in zip(decisiones, llenas):
        if prev_r is None:
            margenes[num] = 9.0
        else:
            si = max(_puntaje_inicio(r, prev_r, tt, tipo_act) for tt in tipos)
            ss = _puntaje_sigue(r, prev_r, tipo_act, 1)
            margenes[num] = abs(si - ss)
        tipo_act, prev_r = t, r
    segs = []
    for num, t, empezo in decisiones:
        if empezo or not segs:
            segs.append([t, num, num, margenes[num], [margenes[num]]])
        else:
            segs[-1][2] = num
            segs[-1][4].append(margenes[num])
    return segs


def segmentar(doc: OCRDocument) -> List[Segmento]:
    rs = [rasgos_de(pg) for pg in doc.pages]
    bruto = _viterbi(rs)
    por_num = {r.numero: r for r in rs}
    segs: List[Segmento] = []
    for i, (tipo, ini, fin, _, margenes) in enumerate(bruto):
        # las hojas en blanco entre dos documentos se quedan con el anterior (y luego
        # se recortan si están al final); las del final del expediente también
        fin_real = (bruto[i + 1][1] - 1) if i + 1 < len(bruto) else doc.n_pages
        r0 = por_num[ini]
        titulo = r0.titulos.get(tipo, (0, ""))[1] if tipo != "otro" else r0.generico[1]
        etiqueta = DOCS[tipo]["etiqueta"]
        if tipo == "otro" and titulo:
            etiqueta = f"Otro documento: {titulo[:60]}"
        m = min(margenes)
        evid = round(min(1.0, m / 6.0), 3)
        segs.append(Segmento(tipo, etiqueta, ini, fin_real, round(r0.conf, 3), titulo=titulo,
                             evidencia=evid, revisar=bool(m < 1.5)))
    segs = [_recorta_blancos(doc, s) for s in segs]
    # hojas en blanco que antecedan al primer documento: sin documento (se reportan aparte)
    return segs


def _fusiona_contiguos(segs):
    """(compatibilidad) Une hojas seguidas del mismo tipo."""
    out = []
    for s in segs:
        if out and s.tipo == out[-1].tipo and s.pagina_ini <= out[-1].pagina_fin + 1 \
                and not DOCS[s.tipo]["hojas"]:
            out[-1].pagina_fin = max(out[-1].pagina_fin, s.pagina_fin)
            out[-1].confianza = round((out[-1].confianza + s.confianza) / 2, 3)
        else:
            out.append(s)
    return out


def _recorta_blancos(doc, seg):
    """Quita las hojas en blanco del final (reversos); conserva las intermedias."""
    fin = seg.pagina_fin
    while fin > seg.pagina_ini and _pagina_vacia(doc.pages[fin - 1]):
        fin -= 1
    seg.pagina_fin = fin
    seg.blancas = [p for p in range(seg.pagina_ini, fin + 1) if _pagina_vacia(doc.pages[p - 1])]
    return seg


def mapa_paginas(doc: OCRDocument, segs: List[Segmento]) -> List[dict]:
    """Qué es cada hoja del expediente: a qué documento pertenece y qué papel cumple."""
    out = []
    for pg in doc.pages:
        n = pg.number
        s = next((x for i, x in enumerate(segs) if x.pagina_ini <= n <= x.pagina_fin), None)
        idx = segs.index(s) if s else None
        vacia = _pagina_vacia(pg)
        if s is None:
            rol = "reverso en blanco" if vacia else "sin documento"
        elif vacia:
            rol = "reverso en blanco"
        elif n == s.pagina_ini:
            rol = "inicio"
        else:
            rol = "continuación"
        out.append({"pagina": n, "documento": idx, "tipo": s.tipo if s else None,
                    "etiqueta": s.etiqueta if s else "", "rol": rol})
    return out


def resumen(segs: List[Segmento]) -> str:
    return "\n".join(f"  pág {s.pagina_ini:>2}-{s.pagina_fin:<2}  {s.etiqueta:<40} "
                     f"(conf OCR {s.confianza:.0%}, evidencia {s.evidencia:.0%}"
                     f"{', REVISAR' if s.revisar else ''})" for s in segs)
