# -*- coding: utf-8 -*-
"""Fusión de varias lecturas de la MISMA hoja, palabra por palabra (tipo ROVER).

Cada hoja floja se lee más de una vez (el escaneo original, la imagen limpia y la
imagen sin sellos). En vez de quedarse con «la mejor página», aquí se alinean las
palabras de todas las lecturas por su posición y se vota:

  · Si dos o más lecturas INDEPENDIENTES coinciden en una palabra, esa palabra
    queda verificada (votos >= 2) y su confianza sube.
  · Si discrepan, gana la de mayor confianza acumulada, pero la confianza final
    BAJA en proporción al desacuerdo (se marca como dudosa: es honesto).
  · Las palabras que una lectura vio y la otra no (p. ej. texto bajo un sello que
    solo aparece en la variante sin sellos) se agregan si no chocan con nada.

Las coordenadas de todas las lecturas están en fracciones 0..1 de la misma hoja,
por eso se pueden comparar directamente.
"""
from __future__ import annotations
import unicodedata
from typing import List
from .base import OCRWord, OCRLine, OCRPage


# ------------------------------------------------------------ geometría ----
def _area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _inter(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def iou(a, b):
    i = _inter(a, b)
    u = _area(a) + _area(b) - i
    return i / u if u > 0 else 0.0


def cubre(a, b):
    """Fracción de 'a' tapada por 'b'."""
    aa = _area(a)
    return _inter(a, b) / aa if aa > 0 else 0.0


def _clave(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).upper()
    return t.strip(" .,;:'\"«»()[]|")


# ----------------------------------------------------------- confianza -----
def conf_pagina(p: OCRPage) -> float:
    cs = [w.conf for l in p.lines for w in l.words] or [l.conf for l in p.lines]
    return sum(cs) / len(cs) if cs else 0.0


def n_palabras(p: OCRPage) -> int:
    return sum(len(l.words) or len(l.text.split()) for l in p.lines)


def puntaje(p: OCRPage) -> float:
    """Confianza ponderada por cuánto se leyó: 430 palabras al 77% es mejor
    lectura que 279 al 47%."""
    return conf_pagina(p) * (1 + 0.5 * min(n_palabras(p), 600) / 600)


# --------------------------------------------------------------- índice ----
class _Rejilla:
    """Índice espacial simple para buscar palabras cercanas sin O(n²)."""
    def __init__(self, palabras, n=24):
        self.n, self.celdas = n, {}
        for i, w in enumerate(palabras):
            for c in self._celdas(w.bbox):
                self.celdas.setdefault(c, []).append(i)

    def _celdas(self, b):
        n = self.n
        x0, x1 = int(max(0, min(n - 1, b[0] * n))), int(max(0, min(n - 1, b[2] * n)))
        y0, y1 = int(max(0, min(n - 1, b[1] * n))), int(max(0, min(n - 1, b[3] * n)))
        return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]

    def cerca(self, b):
        vistos = set()
        for c in self._celdas(b):
            for i in self.celdas.get(c, ()):
                if i not in vistos:
                    vistos.add(i)
                    yield i


# ---------------------------------------------------------------- fusión ---
def _votar(grupo: List[OCRWord]) -> OCRWord:
    """grupo: una palabra por lectura, todas en el mismo sitio."""
    if len(grupo) == 1:
        return grupo[0]
    pesos = {}
    for w in grupo:
        pesos.setdefault(_clave(w.text), []).append(w)
    ganador_k = max(pesos, key=lambda k: (sum(x.conf for x in pesos[k]), len(pesos[k])))
    ganadores = sorted(pesos[ganador_k], key=lambda x: -x.conf)
    total = sum(x.conf for x in grupo) or 1.0
    a_favor = sum(x.conf for x in ganadores)
    c = ganadores[0].conf
    if len(ganadores) >= 2:
        # lecturas no del todo independientes (mismo motor): se suma con prudencia
        c = c + (1.0 - c) * 0.5 * ganadores[1].conf
    en_contra = total - a_favor
    if en_contra > 0:
        c = c * (1.0 - 0.5 * en_contra / total)
    w0 = ganadores[0]
    return OCRWord(text=w0.text, conf=round(min(0.995, c), 4), bbox=w0.bbox, page=w0.page,
                   votos=sum(max(1, x.votos) for x in ganadores))


def fusionar(lecturas: List[OCRPage], iou_min: float = 0.35) -> OCRPage:
    """Fusiona lecturas de una misma hoja. Conserva la estructura de renglones de
    la mejor lectura (y sus roles de Azure) y la enriquece con las demás."""
    lecturas = [l for l in lecturas if l is not None]
    if not lecturas:
        raise ValueError("sin lecturas")
    if len(lecturas) == 1:
        return lecturas[0]
    base = max(lecturas, key=puntaje)
    otras = [l for l in lecturas if l is not base]

    palabras_otras = []
    for o in otras:
        ws = [w for ln in o.lines for w in ln.words]
        palabras_otras.append((ws, _Rejilla(ws), [False] * len(ws)))

    lineas = []
    for ln in base.lines:
        nuevas = []
        for w in ln.words:
            grupo = [w]
            for ws, rej, usados in palabras_otras:
                mejor, mi = 0.0, -1
                for i in rej.cerca(w.bbox):
                    if usados[i]:
                        continue
                    v = iou(w.bbox, ws[i].bbox)
                    if v > mejor:
                        mejor, mi = v, i
                if mi >= 0 and mejor >= iou_min:
                    usados[mi] = True
                    grupo.append(ws[mi])
                elif mi >= 0:
                    # la otra lectura partió/juntó la palabra distinto: no se vota,
                    # pero tampoco se agregará luego como palabra «nueva»
                    for i in rej.cerca(w.bbox):
                        if not usados[i] and cubre(ws[i].bbox, w.bbox) > 0.5:
                            usados[i] = True
            nuevas.append(_votar(grupo))
        lineas.append(_linea(nuevas, ln.page, role=ln.role, manuscrita=ln.manuscrita,
                             bbox=ln.bbox, texto=None if ln.words else ln.text, conf=ln.conf))

    # palabras que solo vieron las otras lecturas (texto tapado por sellos, etc.)
    ocupadas = [w for ln in lineas for w in ln.words]
    rej_base = _Rejilla(ocupadas) if ocupadas else None
    extra = []
    for ws, _, usados in palabras_otras:
        for i, w in enumerate(ws):
            if usados[i] or w.conf < 0.5 or not w.text.strip():
                continue
            choca = False
            if rej_base:
                for j in rej_base.cerca(w.bbox):
                    if cubre(w.bbox, ocupadas[j].bbox) > 0.3 or cubre(ocupadas[j].bbox, w.bbox) > 0.3:
                        choca = True
                        break
            if not choca and not any(cubre(w.bbox, e.bbox) > 0.3 for e in extra):
                extra.append(w)
    if extra:
        lineas = _acomodar(lineas, extra)

    lineas.sort(key=lambda l: (round(l.bbox[1], 3), l.bbox[0]))
    pg = OCRPage(number=base.number, width_pt=base.width_pt, height_pt=base.height_pt,
                 rotation=base.rotation, lines=lineas, meta=dict(base.meta))
    _copiar_roles(pg, lecturas)
    return pg


def _linea(ws, page, role="", manuscrita=False, bbox=None, texto=None, conf=None):
    ws = sorted(ws, key=lambda w: w.bbox[0])
    if ws:
        bbox = (min(w.bbox[0] for w in ws), min(w.bbox[1] for w in ws),
                max(w.bbox[2] for w in ws), max(w.bbox[3] for w in ws))
        texto = " ".join(w.text for w in ws)
        conf = sum(w.conf for w in ws) / len(ws)
    return OCRLine(text=texto or "", conf=round(conf or 0.0, 4), bbox=tuple(bbox or (0, 0, 0, 0)),
                   page=page, words=ws, role=role, manuscrita=manuscrita)


def _acomodar(lineas, extra):
    """Mete cada palabra extra en el renglón con el que comparte altura; si no hay,
    arma renglones nuevos con las que quedan a la misma altura."""
    sueltas = []
    for w in extra:
        h = max(1e-6, w.bbox[3] - w.bbox[1])
        mejor, ml = 0.0, None
        for ln in lineas:
            ov = max(0.0, min(w.bbox[3], ln.bbox[3]) - max(w.bbox[1], ln.bbox[1])) / h
            cerca_x = ln.bbox[0] - 0.08 <= w.bbox[0] <= ln.bbox[2] + 0.08
            if ov > mejor and cerca_x:
                mejor, ml = ov, ln
        if ml is not None and mejor >= 0.6:
            ml.words.append(w)
        else:
            sueltas.append(w)
    out = []
    for ln in lineas:
        out.append(_linea(ln.words, ln.page, ln.role, ln.manuscrita, ln.bbox,
                          None if ln.words else ln.text, ln.conf))
    sueltas.sort(key=lambda w: ((w.bbox[1] + w.bbox[3]) / 2, w.bbox[0]))
    grupo = []
    for w in sueltas:
        yc = (w.bbox[1] + w.bbox[3]) / 2
        if grupo:
            g = grupo[-1]
            gyc = (g.bbox[1] + g.bbox[3]) / 2
            if abs(yc - gyc) <= 0.5 * max(1e-6, g.bbox[3] - g.bbox[1]):
                grupo.append(w)
                continue
            out.append(_linea(grupo, grupo[0].page))
        grupo = [w]
    if grupo:
        out.append(_linea(grupo, grupo[0].page))
    return out


def _copiar_roles(pg: OCRPage, lecturas):
    """Los roles de Azure (title, sectionHeading…) vienen de la lectura del PDF
    original; si la base fue otra variante, se heredan por posición."""
    con_rol = [ln for l in lecturas for ln in l.lines if ln.role or ln.manuscrita]
    if not con_rol:
        return
    for ln in pg.lines:
        if ln.role and ln.manuscrita:
            continue
        for r in con_rol:
            if iou(ln.bbox, r.bbox) >= 0.5 or (cubre(ln.bbox, r.bbox) >= 0.8):
                if not ln.role and r.role:
                    ln.role = r.role
                if r.manuscrita:
                    ln.manuscrita = True
