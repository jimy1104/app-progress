# -*- coding: utf-8 -*-
"""Preparación de la imagen de cada hoja ANTES del OCR (sirve a Azure y a Tesseract).

Los expedientes llegan como JPEG a ~96 DPI, con sellos azules encima del texto,
firmas, y el texto del REVERSO transparentándose en gris (se ve en las hojas
«en blanco» y en la mitad inferior de muchas hojas). Realzar el contraste a lo
bruto empeora las cosas: amplifica esa transparencia y el OCR la lee como basura.

Aquí se hace lo contrario, en este orden:
  1. Se dibuja la hoja a 300 DPI (el OCR necesita letras de 20+ píxeles de alto).
  2. APLANAR EL FONDO: se estima el papel (cierre morfológico grande) y se divide
     la hoja entre él. Sombras, bordes grises y papel amarillento quedan blancos.
  3. SUPRIMIR TRANSPARENCIA: lo que queda gris claro (el reverso) pasa a blanco;
     la tinta negra de verdad se conserva y se oscurece.
  4. (variante) SIN SELLOS: la tinta de color saturado (sellos azules, firmas,
     vistos buenos) se borra para leer el texto impreso que tapaba.
  5. ENDEREZAR: el ángulo se estima por perfiles de proyección (robusto con tablas
     y sellos) y se devuelve para regresar las coordenadas a la hoja original.

Además: detección de hoja en blanco por la TINTA real (no por el texto que el
OCR creyó ver) y lectura local de códigos QR (las facturas electrónicas traen
RUC|tipo|serie|número|IGV|total|fecha en su QR).
"""
from __future__ import annotations
import math
import numpy as np
import pymupdf

try:
    import cv2
    _CV2 = True
except Exception:          # sin OpenCV se usa una versión más simple con numpy
    _CV2 = False

DPI_OCR = 300
# tinta mínima para que una hoja cuente como escrita: media línea de texto a 300 DPI.
# Un reverso transparentado queda por debajo de 0.0001 una vez limpio.
UMBRAL_BLANCA = 0.0004


# ------------------------------------------------------------------ render --
def dpi_origen(page) -> float:
    """Resolución real del escaneo: la de la imagen más grande de la hoja.
    Se calcula por área para que la rotación de la imagen no la falsee."""
    mejor, area_pt = 0.0, 0.0
    try:
        for im in page.get_images(full=True):
            w, h = im[2], im[3]
            for r in page.get_image_rects(im[0]):
                a = abs(r.width * r.height)
                if a > area_pt and a > 0.25 * abs(page.rect.width * page.rect.height):
                    area_pt = a
                    mejor = math.sqrt(w * h / (a / 72.0 / 72.0))
    except Exception:
        pass
    return round(mejor, 1)


def render(page, dpi=DPI_OCR, color=False) -> np.ndarray:
    """Dibuja la hoja tal como se ve (respeta /Rotate). Gris (H,W) o RGB (H,W,3)."""
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB if color else pymupdf.csGRAY,
                          alpha=False)
    a = np.frombuffer(pix.samples, np.uint8)
    if color:
        return a.reshape(pix.height, pix.width, pix.n)[:, :, :3].copy()
    return a.reshape(pix.height, pix.width).copy()


def a_gris(rgb: np.ndarray) -> np.ndarray:
    if rgb.ndim == 2:
        return rgb
    r, g, b = (rgb[:, :, i].astype(np.uint32) for i in range(3))
    return ((r * 299 + g * 587 + b * 114) // 1000).astype(np.uint8)


# ----------------------------------------------------------------- limpieza --
def _cierre(gris: np.ndarray, k: int) -> np.ndarray:
    if _CV2:
        ker = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
        return cv2.morphologyEx(gris, cv2.MORPH_CLOSE, ker)
    # respaldo sin OpenCV: máximo por bloques (aproximado) y suavizado
    h, w = gris.shape
    bh, bw = max(1, h // 32), max(1, w // 32)
    small = gris[: h - h % bh or h, : w - w % bw or w]
    sh, sw = small.shape[0] // bh, small.shape[1] // bw
    bloques = small[: sh * bh, : sw * bw].reshape(sh, bh, sw, bw).max(axis=(1, 3))
    return np.kron(bloques, np.ones((bh, bw), np.uint8))[:h, :w] if bloques.size else gris


def aplanar_fondo(gris: np.ndarray) -> np.ndarray:
    """Divide la hoja entre su fondo estimado: el papel queda en 255."""
    h, w = gris.shape
    k = max(15, int(min(h, w) / 40) | 1)          # ~2 mm a 300 DPI: más grande que un trazo
    fondo = _cierre(gris, k)
    if _CV2:
        fondo = cv2.GaussianBlur(fondo, (0, 0), k / 2)
    fondo = np.maximum(fondo.astype(np.float32), 1.0)
    out = gris.astype(np.float32) / fondo * 255.0
    return np.clip(out, 0, 255).astype(np.uint8)


def nivel_tinta(plano: np.ndarray):
    """(tinta, papel): niveles típicos del texto y del papel ya aplanado."""
    muestra = plano[::3, ::3].ravel()
    oscuro = muestra[muestra < 170]
    tinta = float(np.percentile(oscuro, 20)) if oscuro.size > 200 else 60.0
    return tinta, 255.0


def suprimir_transparencia(plano: np.ndarray, corte: float | None = None) -> np.ndarray:
    """Lo gris claro (texto del reverso, manchas de fotocopia) pasa a blanco y la
    tinta real se estira hacia negro. 'corte' es el gris a partir del cual todo
    se considera papel; por defecto se deduce de la propia hoja."""
    tinta, _ = nivel_tinta(plano)
    if corte is None:
        # el reverso transparentado queda típicamente entre 190 y 235 tras aplanar;
        # el texto verdadero bajo 150. Se corta a medio camino, nunca por debajo de 175.
        corte = max(175.0, min(215.0, tinta + 0.62 * (255.0 - tinta)))
    a = plano.astype(np.float32)
    out = (a - tinta) * 255.0 / max(1.0, corte - tinta)
    out = np.clip(out, 0, 255)
    # curva suave: conserva los bordes de las letras (antialias), sin halos
    out = 255.0 * (out / 255.0) ** 1.35
    return out.astype(np.uint8)


def quitar_color(rgb: np.ndarray, sat_min: int = 70) -> np.ndarray:
    """Gris sin la tinta de color: sellos azules/violetas/rojos y firmas en lapicero.
    La tinta negra/gris (poca saturación) se conserva intacta."""
    if rgb.ndim == 2:
        return rgb
    if _CV2:
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        s, v = hsv[:, :, 1], hsv[:, :, 2]
    else:
        mx = rgb.max(axis=2).astype(np.int16); mn = rgb.min(axis=2).astype(np.int16)
        v = mx.astype(np.uint8)
        s = np.where(mx > 0, (mx - mn) * 255 // np.maximum(mx, 1), 0).astype(np.uint8)
    gris = a_gris(rgb)
    color = (s >= sat_min) & (v >= 60)
    if _CV2:
        color = cv2.dilate(color.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    out = gris.copy()
    out[color] = 255
    return out


def hay_color(rgb: np.ndarray, sat_min: int = 70) -> float:
    """Fracción de la hoja con tinta de color (sellos, firmas)."""
    if rgb.ndim == 2:
        return 0.0
    if _CV2:
        s = cv2.cvtColor(rgb[::4, ::4], cv2.COLOR_RGB2HSV)[:, :, 1]
    else:
        m = rgb[::4, ::4]; mx = m.max(axis=2).astype(np.int16); mn = m.min(axis=2).astype(np.int16)
        s = np.where(mx > 0, (mx - mn) * 255 // np.maximum(mx, 1), 0)
    return float((s >= sat_min).mean())


# --------------------------------------------------------------- enderezado --
def angulo_inclinacion(gris: np.ndarray, rango=3.0, paso=0.1) -> float:
    """Ángulo (grados) que maximiza la nitidez del perfil horizontal de tinta.
    Robusto frente a sellos, logos y líneas de tabla (a diferencia de minAreaRect)."""
    if not _CV2:
        return 0.0
    h, w = gris.shape
    esc = 900.0 / max(h, w)
    peq = cv2.resize(gris, (max(1, int(w * esc)), max(1, int(h * esc))), interpolation=cv2.INTER_AREA)
    tinta = (peq < 140).astype(np.float32)
    if tinta.mean() < 0.002:
        return 0.0
    c = (peq.shape[1] / 2, peq.shape[0] / 2)
    mejor, ang_mejor = -1.0, 0.0
    for a in np.arange(-rango, rango + 1e-6, paso):
        M = cv2.getRotationMatrix2D(c, a, 1.0)
        rot = cv2.warpAffine(tinta, M, (peq.shape[1], peq.shape[0]), flags=cv2.INTER_NEAREST)
        perfil = rot.sum(axis=1)
        v = float(np.var(perfil))
        if v > mejor:
            mejor, ang_mejor = v, float(a)
    return 0.0 if abs(ang_mejor) < 0.15 else ang_mejor


def rotar(gris: np.ndarray, angulo: float):
    """Rota la imagen; devuelve (imagen, matriz_inversa 2x3) para regresar
    coordenadas de la imagen enderezada a la hoja original."""
    if not _CV2 or not angulo:
        return gris, None
    h, w = gris.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angulo, 1.0)
    out = cv2.warpAffine(gris, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)
    return out, cv2.invertAffineTransform(M)


def des_rotar_bbox(bbox, inv, ancho, alto):
    """bbox en fracciones de la imagen enderezada -> fracciones de la hoja original."""
    if inv is None:
        return bbox
    x0, y0, x1, y1 = bbox[0] * ancho, bbox[1] * alto, bbox[2] * ancho, bbox[3] * alto
    pts = np.array([[x0, y0, 1], [x1, y0, 1], [x0, y1, 1], [x1, y1, 1]], np.float64)
    q = pts @ inv.T
    return (max(0.0, q[:, 0].min() / ancho), max(0.0, q[:, 1].min() / alto),
            min(1.0, q[:, 0].max() / ancho), min(1.0, q[:, 1].max() / alto))


def girar90(img: np.ndarray, grados: int) -> np.ndarray:
    """Gira la imagen 90/180/270 grados en sentido horario (hojas escaneadas de costado)."""
    k = (grados // 90) % 4
    return np.ascontiguousarray(np.rot90(img, -k)) if k else img


def des_girar90_bbox(bbox, grados: int):
    """bbox (fracciones) medido en la imagen girada 'grados' horario -> hoja original."""
    x0, y0, x1, y1 = bbox
    k = (grados // 90) % 4
    if k == 1:      # horario 90: (x', y') = (1 - y, x)  ->  x = y', y = 1 - x'
        return (y0, 1 - x1, y1, 1 - x0)
    if k == 2:
        return (1 - x1, 1 - y1, 1 - x0, 1 - y0)
    if k == 3:      # horario 270: (x', y') = (y, 1 - x) ->  x = 1 - y', y = x'
        return (1 - y1, x0, 1 - y0, x1)
    return bbox


# ------------------------------------------------------------ hoja en blanco --
def tinta_util(limpia: np.ndarray, dpi: float = DPI_OCR) -> float:
    """Fracción de la hoja (sin márgenes) cubierta por tinta verdadera, contando
    solo manchas del tamaño de una letra o más (no polvo ni puntitos). Los
    tamaños mínimos se escalan con la resolución de la imagen."""
    esc = dpi / 300.0
    h, w = limpia.shape
    m = limpia[int(h * 0.03): int(h * 0.97), int(w * 0.03): int(w * 0.97)]
    neg = (m < 110).astype(np.uint8)
    if not _CV2:
        return float(neg.mean())
    n, _, stats, _ = cv2.connectedComponentsWithStats(neg, connectivity=8)
    if n <= 1:
        return 0.0
    areas = stats[1:, cv2.CC_STAT_AREA]
    alto = stats[1:, cv2.CC_STAT_HEIGHT]
    utiles = areas[(areas >= max(4, 25 * esc * esc)) & (alto >= max(3, 8 * esc))]
    return float(utiles.sum()) / float(m.size)


def es_blanca(limpia: np.ndarray, umbral: float = None, dpi: float = DPI_OCR) -> bool:
    umbral = UMBRAL_BLANCA if umbral is None else umbral
    return tinta_util(limpia, dpi) < umbral


# ----------------------------------------------------------------- códigos ---
def leer_qr(rgb_o_gris: np.ndarray) -> list:
    """Textos de los códigos QR de la hoja (vacío si no hay o no hay OpenCV)."""
    if not _CV2:
        return []
    img = rgb_o_gris if rgb_o_gris.ndim == 2 else a_gris(rgb_o_gris)
    try:
        det = cv2.QRCodeDetector()
        ok, textos, _, _ = det.detectAndDecodeMulti(img)
        if ok:
            return [t for t in textos if t]
    except Exception:
        pass
    return []


# ------------------------------------------------------------------ salida ---
def a_png(img: np.ndarray) -> bytes:
    if _CV2:
        ok, buf = cv2.imencode(".png", img)
        if ok:
            return buf.tobytes()
    cs = pymupdf.csGRAY if img.ndim == 2 else pymupdf.csRGB
    h, w = img.shape[:2]
    return pymupdf.Pixmap(cs, w, h, np.ascontiguousarray(img).tobytes(), 0).tobytes("png")


def a_jpg(img: np.ndarray, calidad: int = 92) -> bytes:
    if _CV2:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, calidad])
        if ok:
            return buf.tobytes()
    return a_png(img)


# -------------------------------------------------------------- variantes ----
def dpi_seguro(page, dpi=DPI_OCR, max_mpx=36.0) -> int:
    """Baja la resolución en hojas enormes (planos A1/A0) para no agotar la memoria:
    una hoja A4 a 300 DPI son ~8,7 megapíxeles; un A1 serían ~70."""
    area_in2 = abs(page.rect.width * page.rect.height) / (72.0 * 72.0) or 1.0
    tope = (max_mpx * 1e6 / area_in2) ** 0.5
    return int(max(72, min(dpi, tope)))


def preparar_ligero(page, dpi=150) -> dict:
    """Lo mínimo para toda hoja: ¿tiene tinta de verdad? (a 150 DPI, 4 veces más
    barato). La preparación completa a 300 DPI solo se hace en las hojas que se
    van a releer."""
    dpi = dpi_seguro(page, dpi)
    rgb = render(page, dpi, color=True)
    limpia = suprimir_transparencia(aplanar_fondo(a_gris(rgb)))
    tinta = tinta_util(limpia, dpi)
    return {"en_blanco": tinta < UMBRAL_BLANCA, "tinta": round(tinta, 5),
            "color": round(hay_color(rgb), 4), "dpi_origen": dpi_origen(page)}


def preparar(page, dpi=DPI_OCR, enderezar=True, giro=0, qr=False):
    """Todo lo que el OCR necesita de una hoja, calculado una sola vez.

    Devuelve dict con:
      limpia     gris aplanado y sin transparencias (lectura principal)
      sin_sellos igual, pero sin tinta de color (None si la hoja no tiene color)
      inv        matriz para des-rotar coordenadas (None si no se enderezó)
      angulo, en_blanco, tinta, color, dpi_origen, dpi, qr (solo si qr=True)
    """
    dpi = dpi_seguro(page, dpi)
    rgb = render(page, dpi, color=True)
    if giro:                                     # hoja escaneada de costado / de cabeza
        rgb = girar90(rgb, giro)
    gris = a_gris(rgb)
    limpia = suprimir_transparencia(aplanar_fondo(gris))
    frac_color = hay_color(rgb)
    sin_sellos = None
    if frac_color > 0.002:
        sin_sellos = suprimir_transparencia(aplanar_fondo(quitar_color(rgb)))
    ang = angulo_inclinacion(limpia) if enderezar else 0.0
    inv = None
    if ang:
        limpia, inv = rotar(limpia, ang)
        if sin_sellos is not None:
            sin_sellos, _ = rotar(sin_sellos, ang)
    tinta = tinta_util(limpia, dpi)
    return {"limpia": limpia, "sin_sellos": sin_sellos, "inv": inv, "angulo": ang,
            "en_blanco": tinta < UMBRAL_BLANCA, "tinta": round(tinta, 5), "color": round(frac_color, 4),
            "dpi_origen": dpi_origen(page), "dpi": dpi,
            "qr": leer_qr(gris) if (qr and tinta >= UMBRAL_BLANCA) else []}
