# -*- coding: utf-8 -*-
"""Prueba de segmentación contra cortes hechos a mano (verdad de campo).

Expediente OS 10559 (44 págs). Cortes verificados por la Oficina:
    Orden de Servicio -> págs 1-5      TDR -> págs 9-14      Conformidad -> pág 35
Ejecutar:  python tests/test_segmentacion_real.py <expediente.pdf>
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pdftext_provider import PdfTextProvider
import os_engine

VERDAD = {"orden_servicio": (1, 5), "tdr": (9, 14), "conformidad": (35, 35)}

def main(pdf):
    doc = PdfTextProvider().analyze(pdf)
    segs = os_engine.segmentar(doc)
    print(f"--- Segmentos detectados ({len(segs)}) ---")
    for s in segs:
        print(f"  pág {s.pagina_ini:>2}-{s.pagina_fin:<2}  {s.etiqueta}")
    print("\n--- Contraste con los cortes de la Oficina ---")
    ok = True
    for tipo, (a, b) in VERDAD.items():
        cands = [s for s in segs if s.tipo == tipo]
        # el segmento que más se solapa con el rango correcto
        mejor = max(cands, key=lambda s: len(set(range(s.pagina_ini, s.pagina_fin + 1)) & set(range(a, b + 1))),
                    default=None)
        if not mejor:
            print(f"  ✗ {tipo}: NO detectado (debía ser {a}-{b})"); ok = False; continue
        exacto = (mejor.pagina_ini, mejor.pagina_fin) == (a, b)
        ok = ok and exacto
        print(f"  {'✓' if exacto else '✗'} {tipo}: detectado {mejor.pagina_ini}-{mejor.pagina_fin} · correcto {a}-{b}"
              + ("" if exacto else f"  (sobran/faltan {abs(mejor.pagina_fin-b)+abs(mejor.pagina_ini-a)} págs)"))
    print("\nRESULTADO:", "TODO CORRECTO" if ok else "hay diferencias")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "expediente.pdf"))
