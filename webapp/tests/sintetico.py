# -*- coding: utf-8 -*-
"""Expedientes SINTÉTICOS (datos ficticios) que imitan los escaneos reales:
JPEG a 96 DPI en gris, leve inclinación, ruido, sellos azules encima del texto y
el reverso transparentándose en las hojas en blanco.

Sirven para probar la segmentación en los casos difíciles sin subir documentos
reales (el repositorio es público): documentos sin título de catálogo, dos
órdenes distintas seguidas, un TDR con cláusulas que mencionan «declaración
jurada» o «conformidad», un informe cuya 2ª hoja no repite el título.

    python tests/sintetico.py salida.pdf      -> escribe salida.pdf y salida.verdad.json
"""
import os, sys, json, random
import numpy as np
import pymupdf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

A4 = (595, 842)
LOREM = ("El presente documento se emite en el marco de la normativa vigente de contrataciones "
         "del Estado, para los fines que la entidad estime convenientes, conforme a lo solicitado "
         "por el área usuaria y a las condiciones pactadas con el proveedor del servicio. ")


def _pagina(doc, lineas, sello=None):
    """lineas: [(texto, tamaño, negrita, centrado)]"""
    pg = doc.new_page(width=A4[0], height=A4[1])
    y = 60
    for texto, tam, neg, centro in lineas:
        fuente = "hebo" if neg else "helv"
        if texto == "":
            y += tam
            continue
        rect = pymupdf.Rect(60, y, A4[0] - 60, y + 400)
        h = pg.insert_textbox(rect, texto, fontsize=tam, fontname=fuente,
                              align=pymupdf.TEXT_ALIGN_CENTER if centro else pymupdf.TEXT_ALIGN_LEFT)
        usados = 400 - h if h >= 0 else 400
        y += usados + tam * 0.6
    if sello:
        r = pymupdf.Rect(A4[0] - 190, 30, A4[0] - 40, 90)
        pg.draw_rect(r, color=(0.15, 0.25, 0.8), width=1.5)
        pg.insert_textbox(r + (6, 6, -6, -6), sello, fontsize=8, color=(0.15, 0.25, 0.8),
                          align=pymupdf.TEXT_ALIGN_CENTER)
    return pg


def _siga(doc, numero, hoja, total, concepto, monto, sigue):
    cab = [("Sistema Integrado de Gestion Administrativa\nModulo de Logistica\nVersion 26.01.00", 8, False, False),
           (f"ORDEN DE SERVICIO N° {numero:07d}", 13, True, True),
           ("UNIDAD EJECUTORA : 001 MUNICIPALIDAD DE PRUEBA\nNRO. IDENTIFICACION : 300677", 8, False, False),
           ("1. DATOS DEL PROVEEDOR          2. CONDICIONES GENERALES", 9, True, False),
           ("Senor(es): EMPRESA FICTICIA SAC      RUC: 20600000001", 8, False, False),
           (f"Concepto: {concepto}", 8, False, False)]
    if hoja > 1:
        cab.append((f"Vienen ...  {monto:,.2f}", 9, False, False))
    cuerpo = [("Codigo   Unid. Med.   Descripcion   Valor Total S/", 9, True, False),
              (LOREM * 3, 9, False, False)]
    pie = [("AFECTACION PRESUPUESTAL   Cadena Funcional   Clasif. Gasto", 8, True, False),
           ((f"Van ... S/ {monto:,.2f}" if sigue else f"TOTAL S/ {monto:,.2f}"), 10, True, False),
           ("NOTA IMPORTANTE: El Proveedor debe adjuntar a su Factura copia de la O/S", 7, False, False)]
    return _pagina(doc, cab + cuerpo + pie, sello=f"OFICINA LOGISTICA\nPagina {hoja} de {total}")


def _tdr(doc, n_hojas):
    clausulas = ["1. DENOMINACION DE LA CONTRATACION\nSERVICIO DE MANTENIMIENTO DE AREAS VERDES",
                 "2. AREA USUARIA\nSUBGERENCIA DE PRUEBA", "3. FINALIDAD PUBLICA\n" + LOREM,
                 "4. PLAZO DE EJECUCION\n" + LOREM, "5. CONFORMIDAD DE LA PRESTACION DEL SERVICIO\n" + LOREM,
                 "6. FORMA DE PAGO\n" + LOREM, "7. PENALIDADES\n" + LOREM,
                 "8. DECLARACION JURADA\nEl proveedor presentara declaracion jurada de no tener impedimentos. " + LOREM,
                 "9. RESPONSABILIDAD POR VICIOS OCULTOS\n" + LOREM, "10. SOLUCION DE CONTROVERSIAS\n" + LOREM,
                 "11. MODALIDAD DE PAGO\nA suma alzada."]
    por = max(1, len(clausulas) // n_hojas + 1)
    for i in range(n_hojas):
        lineas = [("GERENCIA DE PRUEBA\nSUBGERENCIA DEL PROGRAMA DE PRUEBA", 8, False, False),
                  ("TERMINOS DE REFERENCIA", 13, True, True)]
        lineas += [(c, 9, False, False) for c in clausulas[i * por:(i + 1) * por]]
        _pagina(doc, lineas, sello="GERENCIA DE ADMINISTRACION\nFolio N° %d" % (10 + i))


def _carta(doc):
    _pagina(doc, [("Lima, 10 de marzo de 2026", 9, False, False),
                  ("CARTA N° 010-2026-EF/SAC", 12, True, False),
                  ("Senores:\nMUNICIPALIDAD DE PRUEBA\nPresente.-", 9, False, False),
                  ("Asunto: Remito entregable del servicio", 9, True, False),
                  ("De mi consideracion:\n" + LOREM * 2, 9, False, False),
                  ("Atentamente,\n\nEMPRESA FICTICIA SAC", 9, False, False)])


def _factura(doc):
    _pagina(doc, [("EMPRESA FICTICIA SAC\nAv. Siempre Viva 123", 9, False, False),
                  ("FACTURA ELECTRONICA\nRUC: 20600000001\nE001-458", 12, True, True),
                  ("Fecha de Emision: 15/03/2026\nSenor(es): MUNICIPALIDAD DE PRUEBA\nRUC: 20131369558", 9, False, False),
                  ("Descripcion: SERVICIO DE MANTENIMIENTO DE AREAS VERDES - PRIMER ENTREGABLE", 9, False, False),
                  ("Op. Gravada: S/ 8,474.58\nIGV: S/ 1,525.42\nImporte Total: S/ 10,000.00", 10, True, False),
                  ("Representacion impresa de la Factura Electronica", 7, False, True)])


def _conformidad(doc):
    _pagina(doc, [("MUNICIPALIDAD DE PRUEBA", 12, True, False),
                  ("CONFORMIDAD DE SERVICIOS N° 055-2026-MP/SGP", 12, True, True),
                  ("Por la presente se da la conformidad a la prestacion brindada.", 9, False, False),
                  ("PROVEEDOR: EMPRESA FICTICIA SAC\nRUC: 20600000001\nN° DE ORDEN DE SERVICIO: 2026-12345\n"
                   "MONTO TOTAL S/. 30,000.00\nFECHA DE CONFORMIDAD 20/03/2026", 10, False, False),
                  ("VERIFICACION DE LA PRESTACION\nCALIDAD Conforme ( X ) No Conforme ( )", 9, False, False),
                  ("OBSERVACION: De acuerdo a los terminos de referencia.", 9, False, False)],
            sello="Folio N° 31")


def _informe(doc):
    _pagina(doc, [("MUNICIPALIDAD DE PRUEBA\nSUBGERENCIA DE PRUEBA", 9, False, False),
                  ("INFORME N° 120-2026-SGP/MP", 12, True, False),
                  ("A : GERENCIA DE ADMINISTRACION\nDE : SUBGERENCIA DE PRUEBA\n"
                   "ASUNTO : Conformidad del primer entregable\nREFERENCIA : ORDEN DE SERVICIO N° 0012345\n"
                   "FECHA : 18/03/2026", 9, False, False),
                  ("I. ANTECEDENTES\n" + LOREM * 3, 9, False, False),
                  ("II. ANALISIS\n" + LOREM * 3, 9, False, False)])
    _pagina(doc, [(LOREM * 4, 9, False, False),
                  ("III. CONCLUSIONES\n" + LOREM * 2, 9, False, False),
                  ("IV. RECOMENDACIONES\n" + LOREM, 9, False, False),
                  ("Atentamente,\n\nJEFE DE LA SUBGERENCIA DE PRUEBA", 9, False, False)])


def _en_blanco(doc):
    doc.new_page(width=A4[0], height=A4[1])


def construir(semilla=None):
    """Devuelve (pdf_digital, verdad). Sin semilla: el expediente fijo de referencia.
    Con semilla: documentos en otro orden, largos distintos y reversos al azar."""
    doc = pymupdf.open()
    docs = []

    def marca(tipo, fn):
        ini = doc.page_count + 1
        fn()
        docs.append({"tipo": tipo, "pagina_ini": ini, "pagina_fin": doc.page_count})

    if semilla is not None:
        rnd = random.Random(semilla)
        n_tdr, n_os = rnd.randint(2, 4), rnd.randint(1, 3)
        num = rnd.randint(10000, 19999)
        piezas = [
            ("orden_servicio", lambda: [_siga(doc, num, h, n_os, "SERVICIO DE LIMPIEZA DE LOCALES", 25000, h < n_os)
                                        for h in range(1, n_os + 1)]),
            ("orden_servicio", lambda: _siga(doc, num + rnd.randint(3, 90), 1, 1, "ADQUISICION DE TONER", 3200, False)),
            ("tdr", lambda: _tdr(doc, n_tdr)),
            ("otro", lambda: _carta(doc)),
            ("informe", lambda: _informe(doc)),
            ("comprobante_pago", lambda: _factura(doc)),
            ("conformidad", lambda: _conformidad(doc)),
        ]
        rnd.shuffle(piezas)
        # dos órdenes nunca quedan separadas solo por azar de un mismo tipo pegado:
        for tipo, fn in piezas:
            marca(tipo, fn)
            if rnd.random() < 0.35:
                _en_blanco(doc)
        blancas = [i + 1 for i, p in enumerate(doc) if not p.get_text().strip()]
        return doc, {"documentos": docs, "blancas": blancas, "semilla": semilla,
                     "descripcion": "Expediente sintético aleatorio (datos ficticios)."}

    marca("orden_servicio", lambda: (_siga(doc, 12345, 1, 2, "SERVICIO DE MANTENIMIENTO DE AREAS VERDES", 30000, True),
                                     _en_blanco(doc),
                                     _siga(doc, 12345, 2, 2, "SERVICIO DE MANTENIMIENTO DE AREAS VERDES", 30000, False)))
    _en_blanco(doc)                                           # reverso de la última hoja de la orden
    marca("orden_servicio", lambda: _siga(doc, 12399, 1, 1, "ADQUISICION DE UTILES DE ESCRITORIO", 4500, False))
    marca("tdr", lambda: _tdr(doc, 3))
    marca("otro", lambda: _carta(doc))
    marca("informe", lambda: _informe(doc))
    marca("comprobante_pago", lambda: _factura(doc))
    _en_blanco(doc)                                           # reverso de la factura
    marca("conformidad", lambda: _conformidad(doc))
    blancas = [i + 1 for i, p in enumerate(doc) if not p.get_text().strip()]
    return doc, {"documentos": docs, "blancas": blancas,
                 "descripcion": "Expediente sintético (datos ficticios) con casos difíciles de segmentación."}


def escanear(doc, dpi=96, semilla=7):
    """Convierte cada hoja en un «escaneo»: gris, JPEG, ruido, inclinación y reverso transparentado."""
    import cv2
    rnd = random.Random(semilla)
    np.random.seed(semilla)
    imgs = []
    for pg in doc:
        pix = pg.get_pixmap(dpi=dpi * 2, colorspace=pymupdf.csRGB)
        a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).copy()
        imgs.append(a)
    salida = pymupdf.open()
    for i, a in enumerate(imgs):
        h, w = a.shape[:2]
        # reverso transparentado: la hoja siguiente, en espejo y muy tenue
        if i + 1 < len(imgs):
            atras = cv2.flip(cv2.resize(imgs[i + 1], (w, h)), 1).astype(np.float32)
            a = (a.astype(np.float32) * 0.93 + 255 * 0.07 * (atras / 255.0) + 0.0)
            a = np.clip(a - (255 - atras) * 0.10, 0, 255)
        ang = rnd.uniform(-1.2, 1.2)
        M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
        a = cv2.warpAffine(a.astype(np.uint8), M, (w, h), borderValue=(250, 250, 248))
        a = np.clip(a.astype(np.float32) + np.random.normal(0, 6, a.shape), 0, 255).astype(np.uint8)
        a = cv2.resize(a, (w // 2, h // 2), interpolation=cv2.INTER_AREA)          # 96 DPI reales
        ok, jpg = cv2.imencode(".jpg", cv2.cvtColor(a, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 70])
        pg = salida.new_page(width=A4[0], height=A4[1])
        pg.insert_image(pg.rect, stream=jpg.tobytes())
    return salida


def crear(ruta_pdf, semilla=None):
    doc, verdad = construir(semilla)
    esc = escanear(doc, semilla=semilla or 7)
    esc.save(ruta_pdf)
    with open(os.path.splitext(ruta_pdf)[0] + ".verdad.json", "w", encoding="utf-8") as f:
        json.dump(verdad, f, ensure_ascii=False, indent=1)
    return verdad


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "sintetico.pdf"
    sem = int(sys.argv[2]) if len(sys.argv) > 2 else None
    print(json.dumps(crear(ruta, sem), ensure_ascii=False, indent=1))
