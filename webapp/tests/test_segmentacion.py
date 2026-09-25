"""Prueba de segmentación sobre el expediente OS 7425 (usa la caché de OCR).
Ejecuta:  TESSDATA_PREFIX=/tmp/tessdata pytest tests/ -q
o directamente:  python tests/test_segmentacion.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import os_engine
from ocr.base import OCRDocument

CACHE = os.path.join(os.path.dirname(__file__), "..", "salida_demo", "ocr_cache.json")

def test_tipos_esperados():
    doc = OCRDocument.from_json(CACHE)
    tipos = {s.tipo for s in os_engine.segmentar(doc)}
    for esperado in ("orden_servicio", "tdr", "pedido_servicio",
                     "comprobante_pago", "conformidad"):
        assert esperado in tipos, f"no se detectó {esperado}"

if __name__ == "__main__":
    if os.path.exists(CACHE):
        test_tipos_esperados(); print("OK: se detectaron todos los tipos esperados")
    else:
        print("Corre primero run_local_demo.py para generar la caché de OCR")
