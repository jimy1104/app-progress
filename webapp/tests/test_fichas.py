# -*- coding: utf-8 -*-
"""Pruebas de la FICHA de cada documento: título con número, de/para, firmantes,
sellos y relectura de números. Solo datos sintéticos (nombres inventados)."""
import os, sys, shutil
from collections import Counter
import numpy as np
import pymupdf
import pytest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)

from ocr.base import OCRWord, OCRLine, OCRPage, OCRDocument
from os_engine import Segmento
import fichas


def _linea(texto, y, x0=0.1, conf=0.95, alto=0.012, n=1):
    ws, x = [], x0
    for t in texto.split():
        ancho = 0.012 * len(t)
        ws.append(OCRWord(t, conf, (x, y, x + ancho, y + alto), n))
        x += ancho + 0.01
    return OCRLine(texto, conf, (x0, y, x, y + alto), n, ws)


def _hoja(n, lineas, meta=None):
    for ln in lineas:
        ln.page = n
        for w in ln.words:
            w.page = n
    return OCRPage(n, 595, 842, 0, lineas, dict(meta or {}))


def _doc(*paginas):
    return OCRDocument(provider="prueba", source_path="", pages=list(paginas))


SIGLAS = Counter({"MPC": 9, "GPS": 5, "SGPVL": 6, "OGAF": 4, "OLG": 4})


def test_numero_repara_siglas_pegadas():
    assert fichas.numero_de("INFORME N' 132-2026-MPCIGPS/SGPVL ocacion |", SIGLAS) == "132-2026-MPC/GPS/SGPVL"
    assert fichas.numero_de("MEMORANDO N° 2809-2026-MPC/0GAF/OLG", SIGLAS) == "2809-2026-MPC/OGAF/OLG"


def test_numero_en_blanco_es_sin_numero():
    assert fichas.numero_de("MEMORANDO N° -2026-MPC-OGAF-OLG", SIGLAS).startswith("S/N")


def test_sigla_larga_con_dos_errores_se_repara_si_es_unica():
    s = Counter(SIGLAS)
    s["OGPMPI"] = 2
    assert fichas.numero_de("INFORME N° 01493-2025-MPC/C0GPAPI-OPR", s) == "01493-2025-MPC/OGPMPI-OPR"


def test_cabecera_con_dos_puntos_mal_leidos():
    pg = _hoja(1, [
        _linea("INFORME N° 15-2026-MPC/GPS", 0.15, x0=0.35),
        _linea("A : ABOG. JUAN CARLOS PEREZ QUISPE", 0.22),
        _linea("Gerente de la Oficina General de Administración", 0.235, x0=0.36),
        _linea("DE ! Sr. ROSA ELENA TORRES VILCA", 0.27),
        _linea("Subgerente del Programa de Vaso de Leche", 0.285, x0=0.36),
        _linea("ASUNTO : Contratación del servicio de transporte", 0.32),
        _linea("FECHA : Callao, 23 de abril del 2026", 0.36),
    ])
    c = fichas.campos_cabecera(pg)
    assert c["para"]["nombre"] == "JUAN CARLOS PEREZ QUISPE"
    assert "Gerente" in c["para"]["cargo"]
    assert c["de"]["nombre"] == "ROSA ELENA TORRES VILCA"
    assert c["asunto"].startswith("Contratación")
    assert c["fecha"] == "23/04/2026"


def test_nombre_destrozado_por_la_firma_se_reconoce():
    r = fichas.Registro()
    r.agregar("ROSA ELENA TORRES VILCA", "Subgerente", "cabecera")
    r.agregar("JUAN CARLOS PEREZ QUISPE", "", "cabecera")
    assert [p["nombre"] for p in r.buscar_difuso("ROSA EL NA T RRES V LCA")] == ["ROSA ELENA TORRES VILCA"]
    assert r.buscar_difuso("Gerencia de Administración OFICINA LOGISTICA") == []


def test_cargo_mal_leido_y_cortado_en_la_siguiente_casilla():
    assert fichas.cargo_en("sun GENENTEFecha ,") == "Sub Gerente"
    assert fichas.cargo_en("RESPONSABLE DE ADQUISICIONES Y SERV, AUXILIARES E RESPONSABLE DE X") == \
        "Responsable de Adquisiciones y Serv. Auxiliares"
    assert fichas.cargo_en("JEFE DE AREA USUARIA") == "Jefe de Área Usuaria"


def test_pulir_confusiones_tipicas():
    pg = _hoja(1, [_linea("Subgerencia del Programa de Vaso de Leche y la Oficina de Logística", 0.5)])
    lex = fichas.Lexico(_doc(pg))
    assert fichas.pulir("Subgerencia dei Pro:rama de Vaso de Leche", lex) == "Subgerencia del Programa de Vaso de Leche"
    assert fichas.pulir("Subgerencia de ia Oficina", lex) == "Subgerencia de la Oficina"
    assert fichas.pulir("ORDEN DE SERVICIO N*0010559", lex) == "ORDEN DE SERVICIO N° 0010559"


def test_texto_de_sello_corregido_y_sin_migas():
    pg = _hoja(1, [_linea("MUNICIPALIDAD PROVINCIAL DEL CALLAO Gerencia de Administración Oficina de Logística", 0.5)])
    lex = fichas.Lexico(_doc(pg))
    renglones = fichas.texto_legible([_linea("Gerencia de Adminisiración", 0.1), _linea("AA ab |", 0.12),
                                      _linea("Gerencia de Adminisiración", 0.14), _linea("OFICINA LOGÍS TICA", 0.16)], lex)
    assert renglones[0] == "Gerencia de Administración"
    assert len(renglones) == 2 and renglones[1].upper() == "OFICINA LOGÍSTICA"


def test_memorando_firmado_por_remitente_aunque_el_sello_no_se_lea():
    pg = _hoja(1, [
        _linea("MEMORANDO N° 44-2026-MPC/GPS", 0.15, x0=0.35),
        _linea("A : Sr. JUAN CARLOS PEREZ QUISPE", 0.22),
        _linea("Subgerente de la Oficina de Logística", 0.235, x0=0.36),
        _linea("DE : Sr. ROSA ELENA TORRES VILCA", 0.27),
        _linea("Subgerente del Programa de Vaso de Leche", 0.285, x0=0.36),
        _linea("ASUNTO : Conformidad del servicio", 0.32),
        _linea("Atentamente,", 0.55),
        _linea("ERÍNCIA AS DEL |", 0.65, x0=0.4, conf=0.5),
    ])
    doc = _doc(pg)
    segs = [Segmento("memorando", "Memorando", 1, 1, 0.9, titulo="MEMORANDO N° 44-2026-MPC/GPS")]
    fs, reg = fichas.fichas(doc, segs)
    f = fs[0]
    assert f["titulo"] == "MEMORANDO N° 44-2026-MPC/GPS"
    assert f["de"]["nombre"] == "ROSA ELENA TORRES VILCA"
    assert [x["nombre"] for x in f["firmantes"]] == ["ROSA ELENA TORRES VILCA"]
    assert f["firmantes"][0]["por"] == "remitente"
    assert "Subgerente del Programa" in f["firmantes"][0]["cargo"]
    assert "Firma: ROSA ELENA TORRES VILCA" in f["resumen"]


def test_formulario_con_nombre_bajo_casilla_y_cargo_en_su_columna():
    # la fila de abajo junta dos casillas en un solo renglón (como hace el OCR en tablas)
    pg = _hoja(1, [
        _linea("ORDEN DE SERVICIO N° 0001234", 0.1, x0=0.3),
        _linea("Señor(es): LUCIA MARTA QUISPE HUAMAN", 0.2),
        _linea("ELABORADO POR", 0.8, x0=0.12),
        _linea("CONFORMIDAD DEL SERVICIO", 0.8, x0=0.72),
        _linea("PEREZ QUISPE, JUAN CARLOS", 0.84, x0=0.1),
        _linea("ROSA ELENA TORRES VILCA", 0.86, x0=0.72),
        _linea("RESPONSABLE DE ABASTECIMIENTO SUB GERENTE", 0.88, x0=0.36),
    ])
    doc = _doc(pg)
    reg = fichas.Registro()
    reg.agregar("JUAN CARLOS PEREZ QUISPE", "Oficina de Logística", "cabecera")
    reg.agregar("ROSA ELENA TORRES VILCA", "Subgerente del Programa", "cabecera")
    seg = Segmento("orden_servicio", "Orden de servicio", 1, 1, 0.9, titulo="ORDEN DE SERVICIO N° 0001234")
    fir = {x["nombre"]: x for x in fichas.firmantes_de(seg, doc, reg, [])}
    assert fir["JUAN CARLOS PEREZ QUISPE"]["rol"] == "elaboró"
    assert fir["ROSA ELENA TORRES VILCA"]["cargo"] == "Sub Gerente"
    assert fir["ROSA ELENA TORRES VILCA"]["rol"] == "da conformidad"


def test_numero_ilegible_se_completa_con_la_cita_de_otro_documento():
    p1 = _hoja(1, [_linea("MEMORANDO N° 28%-2026-MPC/OGAF/OLG", 0.15, x0=0.35),
                   _linea("DE : Sr. ROSA ELENA TORRES VILCA", 0.27)])
    p2 = _hoja(2, [_linea("MEMORANDO N° 144-2026-MPC/GPS/SGPVL", 0.15, x0=0.35),
                   _linea("REF : MEMORANDO N° 2809-2026-MPC/OGAF/OLG", 0.3)])
    doc = _doc(p1, p2)
    segs = [Segmento("memorando", "Memorando", 1, 1, 0.9, titulo=p1.lines[0].text),
            Segmento("memorando", "Memorando", 2, 2, 0.9, titulo=p2.lines[0].text)]
    fs, _ = fichas.fichas(doc, segs)
    assert fs[0]["numero"] == "2809-2026-MPC/OGAF/OLG"
    assert fs[0]["numero_fuente"] == "citado en la hoja 2"
    assert fs[1]["numero"] == "144-2026-MPC/GPS/SGPVL"


def _pdf_con_sello(ruta):
    d = pymupdf.open()
    pg = d.new_page(width=595, height=842)
    pg.insert_text((60, 100), "INFORME N 15-2026-MPC", fontsize=14)
    azul = (0.1, 0.2, 0.8)
    pg.draw_rect(pymupdf.Rect(380, 40, 560, 110), color=azul, width=2)
    for i, t in enumerate(("MUNICIPALIDAD PROVINCIAL", "OFICINA DE LOGISTICA", "Folio N 18")):
        pg.insert_text((390, 60 + 18 * i), t, fontsize=11, color=azul)
    # una firma: trazo fino y extendido
    pts = [pymupdf.Point(200 + 4 * k, 650 + 25 * np.sin(k / 3.0)) for k in range(60)]
    pg.draw_polyline(pts, color=azul, width=1.2)
    d.save(ruta)
    d.close()


def test_regiones_de_tinta_de_color_sello_y_firma(tmp_path):
    from ocr import sellos
    ruta = str(tmp_path / "s.pdf")
    _pdf_con_sello(ruta)
    with pymupdf.open(ruta) as d:
        regs = sellos.regiones(d[0])
        solo = sellos.imagen_solo_color(d[0], 150)
    formas = sorted(r["forma"] for r in regs)
    assert "sello" in formas and "trazo" in formas
    sello = next(r for r in regs if r["forma"] == "sello")
    assert sello["color"] == "azul" and sello["bbox"][0] > 0.6 and sello["bbox"][3] < 0.16
    # la imagen de solo color no trae el texto negro del título
    h, w = solo.shape
    assert solo[int(0.1 * h):int(0.13 * h), int(0.1 * w):int(0.4 * w)].min() > 200


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract no instalado")
def test_relectura_de_numero_de_titulo(tmp_path):
    from ocr import relectura
    ruta = str(tmp_path / "p.pdf")
    d = pymupdf.open()
    pg = d.new_page(width=595, height=842)
    pg.insert_text((150, 100), "PEDIDO DE SERVICIO N", fontsize=13)
    pg.insert_text((330, 100), "000966", fontsize=13)
    d.save(ruta)
    d.close()
    # lo que leyó el OCR: 000986, con confianza baja
    y0, y1 = (100 - 11) / 842, (100 + 3) / 842
    ws = [OCRWord(t, 0.97, (x0 / 595, y0, x1 / 595, y1), 1)
          for t, x0, x1 in (("PEDIDO", 150, 205), ("DE", 210, 228), ("SERVICIO", 233, 300), ("N", 305, 315))]
    ws.append(OCRWord("000986", 0.8, (330 / 595, y0, 378 / 595, y1), 1))
    ln = OCRLine("PEDIDO DE SERVICIO N 000986", 0.9, (150 / 595, y0, 378 / 595, y1), 1, ws)
    doc = _doc(_hoja(1, [ln]))
    seg = Segmento("pedido_servicio", "Pedido de servicio", 1, 1, 0.9, titulo=ln.text)
    cambios = relectura.releer_numeros(doc, [seg], ruta)
    assert cambios == [{"pagina": 1, "antes": "000986", "despues": "000966"}]
    titulo, num = fichas.titulo_de(seg, doc, Counter())
    assert num == "000966" and titulo == "PEDIDO DE SERVICIO N° 000966"
