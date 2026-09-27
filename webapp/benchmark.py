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
    Para medir las FICHAS (opcional): "titulo" en cada documento («INFORME N° 132-2026-…»),
    "fichas": {"7": {"de": "NOMBRE", "para": "NOMBRE", "fecha": "23/04/2026"}} y
    "firmantes": {"7": ["NOMBRE COMPLETO"]}, con la hoja inicial del documento como clave.

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
  FICHAS   títulos   documentos cuyo nombre completo (con su número) sale exacto
           campos    de / para / fecha correctos
           firmantes firmantes esperados que se identificaron por su nombre
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


def medir_fichas(doc, segs, verdad, pdf=None):
    """Títulos, campos de cabecera y firmantes contra la verdad (si la trae)."""
    docs = [d for d in verdad.get("documentos", []) if d.get("titulo")]
    if not docs and not verdad.get("fichas") and not verdad.get("firmantes"):
        return None
    import fichas
    regs = {}
    if pdf:
        try:
            import pymupdf
            from ocr import sellos, relectura
            relectura.releer_numeros(doc, segs, pdf)
            with pymupdf.open(pdf) as p:
                regs = {pg.number: sellos.regiones(p[pg.number - 1]) for pg in doc.pages
                        if not (pg.meta or {}).get("en_blanco") and (pg.meta or {}).get("color", 1) >= 0.002}
        except Exception:
            regs = {}
    fs, _ = fichas.fichas(doc, segs, regs)
    por_ini = {s.pagina_ini: f for s, f in zip(segs, fs)}
    clave = lambda t: frozenset(re.findall(r"[A-Z]{3,}", _n(t)))
    r = {"titulos_ok": 0, "titulos_total": len(docs), "campos_ok": 0, "campos_total": 0,
         "firmantes_ok": 0, "firmantes_total": 0, "fallos": []}
    for d in docs:
        got = (por_ini.get(d["pagina_ini"]) or {}).get("titulo", "")
        ok = _compacto(got).replace("N0", "N").startswith(_compacto(d["titulo"]).replace("N0", "N"))
        r["titulos_ok"] += ok
        if not ok:
            r["fallos"].append(f"título hoja {d['pagina_ini']}: «{got}» ≠ «{d['titulo']}»")
    for p, campos in verdad.get("fichas", {}).items():
        f = por_ini.get(int(p)) or {}
        for k, esp in campos.items():
            got = f.get(k)
            got = got.get("nombre", "") if isinstance(got, dict) else (got or "")
            r["campos_total"] += 1
            ok = _compacto(got) == _compacto(esp)
            r["campos_ok"] += ok
            if not ok:
                r["fallos"].append(f"{k} hoja {p}: «{got}» ≠ «{esp}»")
    for p, esperados in verdad.get("firmantes", {}).items():
        hay = {clave(x["nombre"]) for x in (por_ini.get(int(p)) or {}).get("firmantes", []) if x.get("nombre")}
        for e in esperados:
            r["firmantes_total"] += 1
            ok = clave(e) in hay
            r["firmantes_ok"] += ok
            if not ok:
                r["fallos"].append(f"firmante hoja {p}: falta {e}")
    return r


def evaluar(doc, verdad, pdf=None):
    import os_engine
    segs = os_engine.segmentar(doc)
    return {"cortes": medir_cortes(segs, verdad, doc.n_pages), "lectura": medir_lectura(doc, verdad),
            "fichas": medir_fichas(doc, segs, verdad, pdf),
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
    fi = r.get("fichas")
    if fi:
        print(f"  FICHAS   títulos {fi['titulos_ok']}/{fi['titulos_total']} · de/para/fecha "
              f"{fi['campos_ok']}/{fi['campos_total']} · firmantes {fi['firmantes_ok']}/{fi['firmantes_total']}")
        for x in fi["fallos"][:12]:
            print("           " + x)
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
        r = evaluar(doc, verdad, pdf)
        r["segundos_ocr"] = round(time.time() - t, 1)
        imprimir(os.path.basename(pdf), r)
        todos[os.path.basename(pdf)] = r
    if a.salida:
        json.dump(todos, open(a.salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
