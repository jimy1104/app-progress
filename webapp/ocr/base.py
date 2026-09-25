"""Modelo normalizado de OCR — el CONTRATO entre los proveedores de OCR
(Azure Document Intelligence en producción, Tesseract en pruebas) y el resto
del motor (segmentador, motor de riesgo).

Todo proveedor devuelve un OCRDocument con la MISMA estructura, de modo que
os_engine.py y risk_engine.py no saben ni les importa qué OCR se usó.

Las coordenadas (bbox) se guardan SIEMPRE como fracciones 0..1 del ancho/alto
de la página, para que el resaltado 'Ubicar en el documento' funcione igual
sin importar el proveedor ni la resolución del escaneo.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json, unicodedata, re


@dataclass
class OCRWord:
    text: str
    conf: float                       # 0..1
    bbox: tuple                       # (x0,y0,x1,y1) en fracciones 0..1
    page: int                         # 1-based
    votos: int = 1                    # cuántas lecturas independientes coinciden en esta palabra


@dataclass
class OCRLine:
    text: str
    conf: float
    bbox: tuple
    page: int
    words: List[OCRWord] = field(default_factory=list)
    role: str = ""                    # title / sectionHeading / pageHeader / pageFooter / pageNumber (Azure)
    manuscrita: bool = False          # Azure la marcó como escrita a mano (firmas, visto bueno, folios)


@dataclass
class OCRPage:
    number: int                       # 1-based
    width_pt: float                   # ancho de página en puntos PDF
    height_pt: float
    rotation: int                     # /Rotate del PDF (0/90/180/270)
    lines: List[OCRLine] = field(default_factory=list)
    meta: dict = field(default_factory=dict)   # en_blanco, tinta, dpi_origen, fuente, codigos (QR), lecturas

    @property
    def text(self) -> str:
        return "\n".join(l.text for l in self.lines)

    def girar(self, grados: int) -> "OCRPage":
        """Lleva las coordenadas al marco DERECHO del texto cuando la hoja se escaneó de
        costado o de cabeza (giro horario de la imagen). Así el orden de lectura y la
        «cabecera» (parte de arriba) valen igual que en una hoja normal. El giro queda
        en meta['giro'] para dibujar la hoja y escribir el PDF buscable."""
        k = (grados // 90) % 4
        if not k:
            return self

        def f(b):
            x0, y0, x1, y1 = b
            if k == 1:
                return (1 - y1, x0, 1 - y0, x1)
            if k == 2:
                return (1 - x1, 1 - y1, 1 - x0, 1 - y0)
            return (y0, 1 - x1, y1, 1 - x0)
        for ln in self.lines:
            ln.bbox = f(ln.bbox)
            for w in ln.words:
                w.bbox = f(w.bbox)
        if k in (1, 3):
            self.width_pt, self.height_pt = self.height_pt, self.width_pt
        self.lines.sort(key=lambda l: (round(l.bbox[1], 3), l.bbox[0]))
        self.meta = dict(self.meta or {})
        self.meta["giro"] = (self.meta.get("giro", 0) + 90 * k) % 360
        return self

    def text_zona(self, top: float = 0.0, bottom: float = 1.0) -> str:
        """Texto de las líneas cuyo centro vertical cae en [top, bottom]
        (fracciones). Útil para leer sólo el encabezado de una hoja."""
        out = []
        for l in self.lines:
            yc = (l.bbox[1] + l.bbox[3]) / 2
            if top <= yc <= bottom:
                out.append(l.text)
        return "\n".join(out)


@dataclass
class OCRDocument:
    provider: str
    source_path: str
    pages: List[OCRPage] = field(default_factory=list)
    meta: dict = field(default_factory=dict)      # detalle del OCR (relecturas, confianza por página)

    @property
    def n_pages(self) -> int:
        return len(self.pages)

    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)

    # ---- persistencia (caché para no re-OCRear en cada corrida) ----
    def to_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False)

    @classmethod
    def from_json(cls, path: str) -> "OCRDocument":
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return cls.from_dict(d)

    @classmethod
    def from_dict(cls, d: dict) -> "OCRDocument":
        pages = []
        for p in d["pages"]:
            lines = [OCRLine(text=l["text"], conf=l["conf"], bbox=tuple(l["bbox"]),
                             page=l["page"],
                             words=[OCRWord(text=w["text"], conf=w["conf"],
                                            bbox=tuple(w["bbox"]), page=w["page"],
                                            votos=w.get("votos", 1))
                                    for w in l["words"]],
                             role=l.get("role", ""), manuscrita=l.get("manuscrita", False))
                     for l in p["lines"]]
            pages.append(OCRPage(number=p["number"], width_pt=p["width_pt"],
                                 height_pt=p["height_pt"], rotation=p["rotation"],
                                 lines=lines, meta=p.get("meta", {})))
        return cls(provider=d["provider"], source_path=d["source_path"], pages=pages,
                   meta=d.get("meta", {}))


class OCRProvider:
    """Interfaz. analyze(pdf) -> OCRDocument."""
    name = "base"
    def analyze(self, pdf_path: str) -> OCRDocument:
        raise NotImplementedError


# ---- utilidades de normalización de texto (compartidas) ----
def normaliza(txt: str) -> str:
    """Minúsculas -> sin tildes -> sólo alfanumérico+espacios -> espacios colapsados.
    Hace robusta la comparación de anclas frente al ruido del OCR."""
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.upper()
    txt = re.sub(r"[^A-Z0-9 ]+", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()
