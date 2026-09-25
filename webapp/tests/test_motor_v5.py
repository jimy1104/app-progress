# -*- coding: utf-8 -*-
"""Pruebas del motor v5 (lectura + cortes + validación). Ejecutar:

    cd webapp && python -m pytest tests -q

Las pruebas marcadas «lentas» hacen OCR real con Tesseract (se saltan si no está
instalado). Todo usa datos FICTICIOS: los expedientes reales no van al repositorio.
"""
import os, sys, json, shutil
import pytest
import numpy as np
import pymupdf

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)

from ocr.base import OCRWord, OCRLine, OCRPage, OCRDocument
from ocr import fusion, imagen, calidad
import extractor, os_engine

HAY_TESSERACT = bool(shutil.which("tesseract"))
lenta = pytest.mark.skipif(not HAY_TESSERACT, reason="Tesseract no está instalado")


# ------------------------------------------------------------ validaciones ---
def test_ruc_digito_verificador():
    assert extractor.ruc_valido("20131369558")        # Municipalidad Provincial del Callao
    assert extractor.ruc_valido("20600000001") in (True, False)
    assert not extractor.ruc_valido("20131369551")
    assert not extractor.ruc_valido("12345")


def test_monto_en_letras_tolera_ocr():
    assert extractor.letras_a_numero("(TREINTA Y NUEVE MIL NOVECIENTOS Y 00/100 SOLES)") == 39900.0
    assert extractor.letras_a_numero("TREINTA Y NUEVE MIL NOVECIENTOS Y 00/LON SOLES") == 39900.0
    assert extractor.letras_a_numero("SON: UN MILLON DOSCIENTOS MIL QUINIENTOS VEINTIUNO CON 50/100 SOLES") == 1200521.5
    assert extractor.letras_a_numero("sin monto") is None


# ------------------------------------------------------------------ fusión ---
def _pag(palabras, n=1):
    ws = [OCRWord(t, c, b, n) for t, c, b in palabras]
    ln = OCRLine(" ".join(w.text for w in ws), sum(w.conf for w in ws) / len(ws),
                 (min(w.bbox[0] for w in ws), min(w.bbox[1] for w in ws),
                  max(w.bbox[2] for w in ws), max(w.bbox[3] for w in ws)), n, ws)
    return OCRPage(n, 595, 842, 0, [ln])


def test_fusion_coinciden_y_discrepan():
    a = _pag([("ORDEN", 0.80, (0.1, 0.1, 0.2, 0.12)), ("0010559", 0.60, (0.25, 0.1, 0.35, 0.12))])
    b = _pag([("ORDEN", 0.85, (0.1, 0.1, 0.2, 0.12)), ("0010558", 0.40, (0.25, 0.1, 0.35, 0.12)),
              ("SELLO", 0.90, (0.7, 0.5, 0.8, 0.52))])
    f = fusion.fusionar([a, b])
    ws = {w.text: w for ln in f.lines for w in ln.words}
    assert ws["ORDEN"].votos == 2 and ws["ORDEN"].conf > 0.85           # coinciden: sube
    assert "0010559" in ws and ws["0010559"].conf < 0.60                 # discrepan: baja
    assert "SELLO" in ws                                                 # solo la vio una: se agrega


def test_calidad_no_cuenta_hojas_en_blanco_ni_firmas():
    p = _pag([("Texto", 0.95, (0.1, 0.1, 0.2, 0.12))])
    blanca = _pag([("~", 0.1, (0.1, 0.1, 0.2, 0.12))], n=2)
    blanca.meta = {"en_blanco": True}
    firma = _pag([("Garabato", 0.2, (0.5, 0.8, 0.7, 0.85))], n=3)
    firma.lines[0].manuscrita = True
    d = OCRDocument("x", "x", [p, blanca, firma])
    c = calidad.calidad_documento(d)
    assert c["lectura_pct"] == 1.0 and c["hojas_en_blanco"] == [2]


# ------------------------------------------------------------------ imagen ---
def test_reverso_transparentado_es_hoja_en_blanco():
    rnd = np.random.default_rng(1)
    h, w = 1200, 850
    papel = np.full((h, w), 245, np.float32) + rnd.normal(0, 3, (h, w))
    reverso = papel.copy()
    reverso[200:900:40, 100:700] = 205                       # texto del reverso, gris claro
    limpia = imagen.suprimir_transparencia(imagen.aplanar_fondo(np.clip(reverso, 0, 255).astype(np.uint8)))
    assert imagen.es_blanca(limpia)
    escrita = papel.copy()
    for y in range(200, 900, 40):
        for x in range(100, 700, 12):
            escrita[y:y + 14, x:x + 7] = 40                   # «letras» reales, negras
    limpia = imagen.suprimir_transparencia(imagen.aplanar_fondo(np.clip(escrita, 0, 255).astype(np.uint8)))
    assert not imagen.es_blanca(limpia)


# ------------------------------------------------------------ segmentación ---
def _linea(texto, y, alto=0.012, x0=0.1, conf=0.95, role=""):
    ws, x = [], x0
    for t in texto.split():
        ancho = 0.012 * len(t)
        ws.append(OCRWord(t, conf, (x, y, x + ancho, y + alto), 1))
        x += ancho + 0.01
    return OCRLine(texto, conf, (x0, y, x, y + alto), 1, ws, role=role)


def _hoja(n, lineas):
    ls = []
    for ln in lineas:
        for w in ln.words:
            w.page = n
        ln.page = n
        ls.append(ln)
    return OCRPage(n, 595, 842, 0, ls)


def test_viterbi_separa_documento_sin_catalogo():
    cuerpo = [_linea("El presente servicio se ejecutara conforme a lo pactado con la entidad y el area usuaria", 0.3 + i * 0.02)
              for i in range(10)]
    tdr = lambda n: _hoja(n, [_linea("GERENCIA DE PRUEBA SUBGERENCIA DEL PROGRAMA", 0.05),
                               _linea("TERMINOS DE REFERENCIA", 0.1, alto=0.016, x0=0.35)] + cuerpo)
    carta = _hoja(4, [_linea("Lima, 10 de marzo de 2026", 0.05),
                      _linea("CARTA N 010-2026-EF", 0.09, alto=0.02),
                      _linea("Senores MUNICIPALIDAD DE PRUEBA Presente", 0.13)] + cuerpo)
    conf = _hoja(5, [_linea("MUNICIPALIDAD DE PRUEBA", 0.05),
                     _linea("CONFORMIDAD DE SERVICIOS N 055-2026-MP", 0.1, x0=0.3)] + cuerpo)
    doc = OCRDocument("prueba", "x", [tdr(1), tdr(2), tdr(3), carta, conf])
    segs = [(s.tipo, s.pagina_ini, s.pagina_fin) for s in os_engine.segmentar(doc)]
    assert segs == [("tdr", 1, 3), ("otro", 4, 4), ("conformidad", 5, 5)]


def _escaneo(titulo, cuerpo="", rotate=0, de_costado=0):
    """Hoja «escaneada» (imagen). rotate: /Rotate del PDF con la imagen guardada de
    costado para que SE VEA derecha (como los PDF de Nitro). de_costado: la hoja se
    VE girada esos grados (escaneo mal puesto)."""
    d = pymupdf.open()
    pg = d.new_page(width=595, height=842)
    pg.insert_textbox(pymupdf.Rect(60, 80, 535, 200), titulo, fontsize=18, fontname="hebo")
    if cuerpo:
        pg.insert_textbox(pymupdf.Rect(60, 220, 535, 780), cuerpo, fontsize=11)
    pix = pg.get_pixmap(dpi=150)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    guardada = imagen.girar90(a, (360 - rotate + de_costado) % 360)
    h, w = guardada.shape[:2]
    W, H = (842, 595) if w > h else (595, 842)
    out = pymupdf.open()
    p2 = out.new_page(width=W, height=H)
    p2.insert_image(p2.rect, stream=imagen.a_png(np.ascontiguousarray(guardada[:, :, ::-1])))
    if rotate:
        p2.set_rotation(rotate)
    return out


@lenta
def test_expediente_sintetico_cortes_exactos(tmp_path):
    import sintetico
    from ocr.tesseract_provider import TesseractProvider
    pdf = str(tmp_path / "sint.pdf")
    verdad = sintetico.crear(pdf)
    doc = TesseractProvider().analyze(pdf)
    segs = os_engine.segmentar(doc)
    obtenidos = {(s.tipo, s.pagina_ini, s.pagina_fin) for s in segs}
    for d in verdad["documentos"]:
        assert (d["tipo"], d["pagina_ini"], d["pagina_fin"]) in obtenidos, (d, obtenidos)
    assert sorted(doc.meta["hojas_en_blanco"]) == verdad["blancas"]


@lenta
def test_azure_simulado_hojas_giradas_y_lotes(tmp_path):
    """El camino de Azure completo (1ª pasada, relectura en lotes, fusión) con un
    cliente simulado que devuelve coordenadas SIN girar para hojas con /Rotate."""
    from azure_simulado import ClienteSimulado
    from ocr.azure_provider import AzureDocIntelligenceProvider
    src = pymupdf.open()
    for rot in (0, 270, 90):
        src.insert_pdf(_escaneo("CONFORMIDAD DE SERVICIOS N 055-2026",
                                "Texto de prueba del servicio prestado a la entidad. " * 18, rotate=rot))
    ruta = str(tmp_path / "girado.pdf")
    src.save(ruta)
    cli = ClienteSimulado(sin_girar=True, conf_primera=0.6)   # 1ª pasada floja: fuerza relectura
    prov = AzureDocIntelligenceProvider(client=cli)
    doc = prov.analyze(ruta)
    assert len(cli.llamadas) >= 2                        # PDF completo + al menos un lote
    d = pymupdf.open(ruta)
    for pg, page in zip(doc.pages, d):
        tit = [ln for ln in pg.lines if "CONFORMIDAD" in ln.text.upper()]
        assert tit, pg.number
        # el título debe caer ARRIBA de la hoja tal como se ve
        yc = (tit[0].bbox[1] + tit[0].bbox[3]) / 2
        assert yc < 0.25, (pg.number, tit[0].bbox)
        assert abs(pg.width_pt - page.rect.width) < 1


@lenta
def test_pdf_buscable_en_hoja_girada(tmp_path):
    from ocr.tesseract_provider import TesseractProvider
    from ocr.pdf_buscable import hacer_buscable
    esc = _escaneo("TERMINOS DE REFERENCIA", "Objeto de la contratacion y alcance del servicio. " * 10, rotate=270)
    ruta = str(tmp_path / "esc.pdf")
    esc.save(ruta)
    doc = TesseractProvider().analyze(ruta)
    out = hacer_buscable(ruta, doc)
    assert out[0].search_for("REFERENCIA")


@lenta
def test_hoja_escaneada_de_costado_se_lee_derecha(tmp_path):
    from ocr.tesseract_provider import TesseractProvider
    esc = _escaneo("TERMINOS DE REFERENCIA", "Objeto de la contratacion y alcance del servicio. " * 12,
                   de_costado=90)
    ruta = str(tmp_path / "costado.pdf")
    esc.save(ruta)
    doc = TesseractProvider().analyze(ruta)
    texto = os_engine.normaliza(doc.pages[0].text)
    assert "TERMINOS DE REFERENCIA" in texto, texto[:200]
    assert doc.pages[0].meta.get("giro") in (90, 270)
