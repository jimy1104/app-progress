"""Corte del PDF por documento. Usa PyMuPDF para extraer rangos de páginas a
PDFs separados (conservando el escaneo original, sin re-renderizar)."""
from __future__ import annotations
import os, pymupdf
from typing import List
from os_engine import Segmento


def cortar(pdf_path: str, segmentos: List[Segmento], tipos: List[str],
           out_dir: str) -> List[dict]:
    """Corta sólo los 'tipos' pedidos (claves de ANCLAS). Devuelve metadatos."""
    os.makedirs(out_dir, exist_ok=True)
    src = pymupdf.open(pdf_path)
    salidas = []
    for i, seg in enumerate(s for s in segmentos if s.tipo in tipos):
        out = pymupdf.open()
        out.insert_pdf(src, from_page=seg.pagina_ini - 1, to_page=seg.pagina_fin - 1)
        nombre = f"{i+1:02d}_{seg.tipo}_p{seg.pagina_ini}-{seg.pagina_fin}.pdf"
        ruta = os.path.join(out_dir, nombre)
        out.save(ruta); out.close()
        salidas.append({"tipo": seg.tipo, "etiqueta": seg.etiqueta,
                        "pagina_ini": seg.pagina_ini, "pagina_fin": seg.pagina_fin,
                        "archivo": ruta})
    src.close()
    return salidas
