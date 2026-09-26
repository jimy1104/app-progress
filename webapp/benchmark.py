# -*- coding: utf-8 -*-
"""Banco de medición: ¿qué tan buena es la LECTURA y qué tan buenos son los CORTES?

Se compara contra una «verdad de campo» hecha por personas (o verificada con IA
de visión), un JSON al lado de cada PDF:

    expediente.pdf
    expediente.verdad.json   {
        "documentos": [{"tipo": "orden_servicio", "pagina_ini": 1, "pagina_fin": 5}, ...],
        "blancas": [2, 4],                                  (opcional)
        "campos": {"1": ["ORDEN DE SERVICIO", "0010559"]},  (opcional: textos que DEBEN leerse)
        "transcripciones": {"12": "texto completo de la hoja"}  (opcional)
    }

Uso:
    python benchmark.py carpeta_con_pdfs/            # OCR con el motor configurado
    python benchmark.py carpeta/ --cache              # reutiliza <pdf>.ocr.json si existe
    python benchmark.py carpeta/ --ocr-json x.json    # usa un OCR ya hecho (un solo PDF)

Métricas:
  CORTES   exactos   documentos cuyo rango de páginas coincide EXACTO
           páginas   % de hojas asignadas al documento correcto
  LECTURA  campos    % de textos clave leídos tal cual (N° de orden, RUC, montos, fechas…)
           palabras  % de las palabras de la transcripción que el OCR leyó exactas
           segura    % de palabras que el sistema da por seguras (lo que ve el usuario)
"""
from __future__ import annotations
import os, sys, json, glob, re, time, unicodedata, argparse
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _n(t):
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).upper()
    t = re.sub(r"[^A-Z0-9/.,:()\-° ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _tokens(t):
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).upper()
    return [x for x in re.split(r"[^A-Z0-9]+", t) if x]


def _compacto(t):
    return re.sub(r"[^A-Z0-9]", "", _n(t))


# ------------------------------------------------------------------ cortes --
def medir_cortes(segs, verdad, n_paginas):
    docs = verdad.get("documentos", [])
    exactos, detalle = 0, []
    for d in docs:
        a, b = d["pagina_ini"], d["pagina_fin"]
        cands = [s for s in segs if s.tipo == d["tipo"]]
        mejor = max(cands, key=lambda s: len(set(range(s.pagina_ini, s.pagina_fin + 1)) & set(range(a, b + 1))),
                    default=None)
        ok = bool(mejor and (mejor.pagina_ini, mejor.pagina_fin) == (a, b))
        exactos += ok
        detalle.append({"tipo": d["tipo"], "verdad": [a, b],
                        "detectado": [mejor.pagina_ini, mejor.pagina_fin] if mejor else None, "ok": ok})
    # exactitud por página (solo sobre las páginas que la verdad asigna a un documento)
    asign_v = {p: i for i, d in enumerate(docs) for p in range(d["pagina_ini"], d["pagina_fin"] + 1)}
    asign_d = {}
    for i, d in enumerate(docs):
        for s in segs:
            if s.tipo == d["tipo"] and s.pagina_ini <= d["pagina_fin"] and s.pagina_fin >= d["pagina_ini"]:
                for p in range(s.pagina_ini, s.pagina_fin + 1):
                    asign_d.setdefault(p, i)
    # hojas que el sistema metió en un documento que no les corresponde
    tipos_verdad = {d["tipo"] for d in docs}
    intrusas = sum(1 for s in segs if s.tipo in tipos_verdad for p in range(s.pagina_ini, s.pagina_fin + 1)
                   if p not in asign_v)
    bien = sum(1 for p, i in asign_v.items() if asign_d.get(p) == i)
    return {"exactos": exactos, "total": len(docs),
            "pct_exactos": round(exactos / len(docs), 4) if docs else None,
            "pct_paginas": round(bien / len(asign_v), 4) if asign_v else None,
            "paginas_intrusas": intrusas, "detalle": detalle}


# ----------------------------------------------------------------- lectura --
def medir_lectura(doc, verdad):
    from ocr.calidad import calidad_documento
    campos = verdad.get("campos", {})
    ok = tot = 0
    fallos = []
    for pag, lista in campos.items():
        pg = doc.pages[int(pag) - 1]
        txt = _n(" ".join(l.text for l in pg.lines))
        comp = _compacto(txt)
        for c in lista:
            tot += 1
            if _n(c) in txt or _compacto(c) in comp:
                ok += 1
            else:
                fallos.append(f"p{pag}: {c}")
    rec_tot = rec_ok = prec_tot = 0
    for pag, gt in verdad.get("transcripciones", {}).items():
        pg = doc.pages[int(pag) - 1]
        g = Counter(_tokens(gt)); o = Counter(_tokens(" ".join(l.text for l in pg.lines)))
        inter = sum((g & o).values())
        rec_ok += inter; rec_tot += sum(g.values()); prec_tot += sum(o.values())
    cal = calidad_documento(doc)
    blancas = set(verdad.get("blancas", []))
    det_blancas = set(cal["hojas_en_blanco"])
    return {"pct_campos": round(ok / tot, 4) if tot else None, "campos_ok": ok, "campos_total": tot,
            "fallos_campos": fallos,
            "pct_palabras": round(rec_ok / rec_tot, 4) if rec_tot else None,
            "precision_palabras": round(rec_ok / prec_tot, 4) if prec_tot else None,
            "lectura_pct": cal["lectura_pct"], "conf_texto": cal["conf_texto"], "conf_bruta": cal["conf_bruta"],
            "blancas_ok": (blancas == det_blancas) if blancas else None,
            "blancas_detectadas": sorted(det_blancas),
            "paginas_revisar": cal["paginas_revisar"]}


def evaluar(doc, verdad):
    import os_engine
    segs = os_engine.segmentar(doc)
    return {"cortes": medir_cortes(segs, verdad, doc.n_pages), "lectura": medir_lectura(doc, verdad),
            "segmentos": [(s.tipo, s.pagina_ini, s.pagina_fin) for s in segs]}


def imprimir(nombre, r):
    c, l = r["cortes"], r["lectura"]
    pct = lambda v: "—" if v is None else f"{v * 100:.1f}%"
    print(f"\n=== {nombre}")
    print(f"  CORTES   exactos {c['exactos']}/{c['total']} ({pct(c['pct_exactos'])}) · "
          f"páginas bien asignadas {pct(c['pct_paginas'])} · hojas intrusas {c['paginas_intrusas']}")
    for d in c["detalle"]:
        print(f"     {'✓' if d['ok'] else '✗'} {d['tipo']:<16} verdad {d['verdad']}  detectado {d['detectado']}")
    print(f"  LECTURA  campos clave {l['campos_ok']}/{l['campos_total']} ({pct(l['pct_campos'])}) · "
          f"palabras exactas {pct(l['pct_palabras'])} (precisión {pct(l['precision_palabras'])})")
    print(f"           segura {pct(l['lectura_pct'])} · conf. texto {pct(l['conf_texto'])} · "
          f"conf. bruta (métrica antigua) {pct(l['conf_bruta'])}")
    if l["blancas_ok"] is not None:
        print(f"           hojas en blanco {'✓' if l['blancas_ok'] else '✗'} {l['blancas_detectadas']}")
    if l["fallos_campos"]:
        print("           no leídos: " + " · ".join(l["fallos_campos"][:12]))
    print("  segmentos:", r["segmentos"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta")
    ap.add_argument("--cache", action="store_true", help="reutiliza <pdf>.ocr.json")
    ap.add_argument("--ocr-json", help="OCR ya hecho (para un solo PDF)")
    ap.add_argument("--salida", help="guarda el resultado en JSON")
    a = ap.parse_args()
    from ocr.base import OCRDocument
    pdfs = sorted(glob.glob(os.path.join(a.carpeta, "*.pdf"))) if os.path.isdir(a.carpeta) else [a.carpeta]
    todos = {}
    for pdf in pdfs:
        vpath = os.path.splitext(pdf)[0] + ".verdad.json"
        if not os.path.exists(vpath):
            continue
        verdad = json.load(open(vpath, encoding="utf-8"))
        cache = os.path.splitext(pdf)[0] + ".ocr.json"
        t = time.time()
        if a.ocr_json:
            doc = OCRDocument.from_json(a.ocr_json)
        elif a.cache and os.path.exists(cache):
            doc = OCRDocument.from_json(cache)
        else:
            import jobs
            doc = jobs.get_provider().analyze(pdf)
            doc.to_json(cache)
        r = evaluar(doc, verdad)
        r["segundos_ocr"] = round(time.time() - t, 1)
        imprimir(os.path.basename(pdf), r)
        todos[os.path.basename(pdf)] = r
    if a.salida:
        json.dump(todos, open(a.salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
