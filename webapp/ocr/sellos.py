# -*- coding: utf-8 -*-
"""SELLOS y FIRMAS: la tinta de color de cada hoja.

En los expedientes los sellos (folio, recepción, proveído, visto bueno, post-firma
con nombre y cargo) y las firmas van en tinta azul, violeta o roja, ENCIMA del
texto impreso negro. Leídos junto con el resto de la hoja salen como basura
(«ROS EL A TOR RRES VILCA»). Aquí:

  1. Se separa la tinta de color (saturación alta) del resto.
  2. Se agrupa en REGIONES (un sello, una firma) y se mide su forma: un sello es
     compacto y lleno de letras; una firma es un trazo fino y extendido.
  3. Se arma una imagen con SOLO esa tinta, en negro sobre blanco, para que el OCR
     (Azure o Tesseract) la lea sin el texto impreso ni el fondo encima.

La clasificación por su texto (folio, recepción, proveído, V°B°, post-firma) está
en fichas.py, que cruza lo leído con las personas del expediente.
"""
from __future__ import annotations
import numpy as np
from . import imagen

try:
    import cv2
    _CV2 = True
except Exception:
    _CV2 = False

SAT_MIN = 60           # saturación mínima de la tinta de color (0..255)
AREA_MIN = 0.0012      # fracción de la hoja: menos que esto es una mancha suelta


def mascara_color(rgb: np.ndarray) -> np.ndarray:
    """True donde hay tinta de color (azul, violeta, roja), no gris ni negra."""
    if _CV2:
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        s, v = hsv[:, :, 1], hsv[:, :, 2]
    else:
        mx = rgb.max(axis=2).astype(np.int16)
        mn = rgb.min(axis=2).astype(np.int16)
        v = mx
        s = np.where(mx > 0, (mx - mn) * 255 // np.maximum(mx, 1), 0)
    return (s >= SAT_MIN) & (v >= 40) & (v <= 250)


def regiones(page, dpi: int = 100) -> list:
    """Regiones de tinta de color de la hoja (como se ve), con su forma:
    [{bbox, area, relleno, forma: 'sello'|'trazo', color}] en fracciones 0..1."""
    if not _CV2:
        return []
    rgb = imagen.render(page, imagen.dpi_seguro(page, dpi), color=True)
    m = mascara_color(rgb).astype(np.uint8)
    if m.mean() < 0.0005:
        return []
    h, w = m.shape
    k = max(3, int(round(dpi / 25.4 * 2.5)))            # ~2,5 mm: une las letras de un sello
    unida = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(unida, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < AREA_MIN * h * w:
            continue
        caja = m[y:y + bh, x:x + bw]
        relleno = float(caja.mean())
        extendida = max(bw / w, bh / h)
        # una firma es un trazo: poca tinta en una caja grande
        forma = "trazo" if (relleno < 0.07 and extendida > 0.06) else "sello"
        px = rgb[y:y + bh, x:x + bw][caja.astype(bool)]
        r, g, b = (px.mean(axis=0) if len(px) else (0, 0, 0))
        color = "rojo" if r > b + 25 and r > g else ("violeta" if r > g + 15 and b > g else "azul")
        out.append({"bbox": [round(x / w, 4), round(y / h, 4), round((x + bw) / w, 4), round((y + bh) / h, 4)],
                    "area": round(float(area) / (h * w), 5), "relleno": round(relleno, 3),
                    "forma": forma, "color": color})
    out.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))
    return out


def imagen_solo_color(page, dpi: int = 300, giro: int = 0) -> np.ndarray:
    """La hoja con SOLO la tinta de color, en negro sobre blanco (para leer sellos)."""
    rgb = imagen.render(page, imagen.dpi_seguro(page, dpi), color=True)
    if giro:
        rgb = imagen.girar90(rgb, giro)
    m = mascara_color(rgb)
    if _CV2:
        m = cv2.dilate(m.astype(np.uint8), np.ones((2, 2), np.uint8)).astype(bool)
    out = np.full(m.shape, 255, np.uint8)
    gris = imagen.a_gris(rgb)
    # la tinta de color suele ser clara (azul pálido): se lleva a negro, conservando el borde
    out[m] = np.clip((gris[m].astype(np.int16) - 60) // 2, 0, 90).astype(np.uint8)
    return out
