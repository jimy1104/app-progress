# -*- coding: utf-8 -*-
"""Excel de resultados (openpyxl): encabezado con la Municipalidad y la fecha de
consulta, una fila por riesgo con su marco legal y medida de control, y hojas
de documentos detectados, base legal y deslinde."""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

PETROL = "0D5C63"; TINTA = "12243F"; GRIS = "F3F5F8"
ROJO_BG, ROJO_TX = "FBECEB", "BF352C"
AMB_BG, AMB_TX = "FDF4DA", "A9730F"
_S = Side(style="thin", color="D9E0E9"); BORDE = Border(left=_S, right=_S, top=_S, bottom=_S)
WRAP = Alignment(wrap_text=True, vertical="top")

def _encabezado(ws, ncols, titulo, res):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(1, 1, "MUNICIPALIDAD PROVINCIAL DEL CALLAO")
    c.font = Font(bold=True, size=14, color="FFFFFF"); c.fill = PatternFill("solid", fgColor=PETROL)
    c.alignment = Alignment(horizontal="center", vertical="center"); ws.row_dimensions[1].height = 26
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    c = ws.cell(2, 1, "Oficina de Logística · Gestión de Riesgo — ISO Calidad · Antisoborno (OLG)")
    c.font = Font(bold=True, color=PETROL); c.alignment = Alignment(horizontal="center")
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=ncols)
    ctx = res.get("contexto", {})
    info = (f"{titulo}   ·   Fecha de la consulta: {res.get('fecha','')}   ·   Usuario: {res.get('usuario','')}"
            f"   ·   Subproceso: {res.get('subproceso','')}   ·   Expediente: {res.get('archivo','')}"
            + (f"   ·   OS N° {ctx.get('os')}" if ctx.get("os") else ""))
    o = res.get("ocr") or {}
    if o:
        info += (f"\nLectura OCR: {res.get('provider','')} · modelo {o.get('modelo','')} · "
                 f"{o.get('relecturas',0)} página(s) releídas en alta resolución"
                 + (f" · quedan bajo el {int(o.get('umbral',0.9)*100)}%: págs. "
                    + ", ".join(str(x) for x in (o.get('paginas_bajo_umbral') or [])[:20])
                    if o.get("paginas_bajo_umbral") else " · todas sobre el umbral"))
    c = ws.cell(3, 1, info); c.font = Font(italic=True, color="555555", size=9); c.alignment = WRAP
    ws.row_dimensions[3].height = 30

def _tabla(ws, fila, headers, widths):
    for j, (h, w) in enumerate(zip(headers, widths), 1):
        c = ws.cell(fila, j, h)
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor=TINTA)
        c.alignment = Alignment(wrap_text=True, vertical="center"); c.border = BORDE
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(fila + 1, 1)

def construir(res, kb, ruta):
    wb = Workbook()
    # ---- Riesgos ----
    ws = wb.active; ws.title = "Riesgos"
    H = ["N°", "Estado", "Nivel (matriz)", "ID", "Riesgo (el hecho)", "Evidencia en el expediente",
         "Página", "Marco legal", "Control a implementar", "Ejecuta", "Supervisa", "Cómo verificar"]
    W = [5, 14, 12, 12, 48, 44, 14, 60, 60, 24, 24, 50]
    _encabezado(ws, len(H), "Resumen de verificación", res); _tabla(ws, 5, H, W)
    rs = sorted(res.get("riesgos", []), key=lambda r: (r["nivel"] != "rojo",
                {"MUY ALTO": 0, "ALTO": 1, "MEDIO": 2}.get(r.get("nivel_matriz"), 3)))
    for i, r in enumerate(rs, 1):
        rojo = r["nivel"] == "rojo"
        bl = "\n".join(f"• {b['dispositivo']}" + (f": {b['contenido']}" if b.get("contenido") else "")
                       for b in r.get("base_legal", []))
        evid = " ".join(x for x in (r.get("nota", ""), r.get("evidencia", "")) if x)
        ubic = r.get("ubicaciones") or []
        pags = ", ".join(str(u["pagina"]) for u in ubic[:8]) if ubic else "— (por ausencia)"
        fila = [i, "CONFIRMADO" if rojo else "POR REVISAR", r.get("nivel_matriz", ""), r["id"], r["hecho"],
                evid, pags, bl, r.get("control", ""), r.get("ejecuta", ""),
                r.get("supervisa", ""), r.get("como_verificar", "")]
        for j, v in enumerate(fila, 1):
            c = ws.cell(5 + i, j, v); c.alignment = WRAP; c.border = BORDE; c.font = Font(size=9)
        e = ws.cell(5 + i, 2)
        e.fill = PatternFill("solid", fgColor=ROJO_BG if rojo else AMB_BG)
        e.font = Font(bold=True, size=9, color=ROJO_TX if rojo else AMB_TX)
    ws.auto_filter.ref = f"A5:{get_column_letter(len(H))}{5 + len(rs)}"

    # ---- Documentos detectados ----
    ws2 = wb.create_sheet("Documentos")
    H2 = ["Documento", "Página inicial", "Página final", "Confianza OCR"]
    _encabezado(ws2, len(H2), "Documentos identificados en el expediente", res); _tabla(ws2, 5, H2, [44, 14, 14, 14])
    for i, s in enumerate(res.get("documentos", []), 1):
        for j, v in enumerate([s["etiqueta"], s["pagina_ini"], s["pagina_fin"], f"{s['confianza']:.0%}"], 1):
            c = ws2.cell(5 + i, j, v); c.border = BORDE
    ctx = res.get("contexto", {}); f0 = 7 + len(res.get("documentos", []))
    for k, (lab, val) in enumerate([("N° de orden", ctx.get("os")), ("RUC proveedor", ctx.get("ruc")),
                                    ("Monto leído (S/)", ctx.get("monto")), ("Objeto", ctx.get("objeto")),
                                    ("Órdenes previas del mismo objeto (año)", res.get("acumulado_previo", {}).get("ordenes")),
                                    ("Monto previo acumulado (S/)", res.get("acumulado_previo", {}).get("monto"))]):
        ws2.cell(f0 + k, 1, lab).font = Font(bold=True); ws2.cell(f0 + k, 2, val)

    # ---- Base legal ----
    ws3 = wb.create_sheet("Base legal")
    _encabezado(ws3, 2, "Base legal citada en la matriz", res); _tabla(ws3, 5, ["Dispositivo", "Contenido"], [48, 110])
    for i, b in enumerate(kb.get("base_legal", []), 1):
        for j, v in enumerate([b.get("dispositivo"), b.get("contenido")], 1):
            c = ws3.cell(5 + i, j, v); c.alignment = WRAP; c.border = BORDE

    # ---- Deslinde ----
    ws4 = wb.create_sheet("Deslinde")
    _encabezado(ws4, 1, "Deslinde de responsabilidades", res); ws4.column_dimensions["A"].width = 150
    aviso = ("Este resultado es asistido por un programa y puede contener errores de lectura (OCR) o de "
             "clasificación. Es responsabilidad de cada persona verificar cada hallazgo contra el expediente "
             "físico y los sistemas oficiales (SIGA-SIAF) antes de tomar decisiones.")
    c = ws4.cell(5, 1, aviso); c.font = Font(bold=True, color=ROJO_TX); c.alignment = WRAP
    for i, t in enumerate(kb.get("deslinde", []), 1):
        c = ws4.cell(6 + i, 1, t); c.alignment = WRAP
    wb.save(ruta); return ruta


def construir_lote(resultados, kb, ruta):
    """Excel de un LOTE: una hoja «Resumen» con un renglón por expediente y, debajo,
    el detalle de todos los riesgos de todos los expedientes en una sola tabla."""
    wb = Workbook()
    base = dict(resultados[0]); base["archivo"] = "%d expedientes" % len(resultados)
    ws = wb.active; ws.title = "Resumen"
    H = ["N°", "Expediente", "OS N°", "Objeto", "Monto (S/)", "Páginas", "Documentos",
         "Confirmados", "Por revisar", "Lectura OCR"]
    W = [5, 34, 12, 46, 14, 10, 12, 13, 13, 13]
    _encabezado(ws, len(H), "Resumen del lote de expedientes", base); _tabla(ws, 5, H, W)
    for i, r in enumerate(resultados, 1):
        ctx = r.get("contexto", {})
        rojo = sum(1 for x in r.get("riesgos", []) if x["nivel"] == "rojo")
        amar = len(r.get("riesgos", [])) - rojo
        fila = [i, r.get("archivo", ""), ctx.get("os", ""), ctx.get("objeto", ""), ctx.get("monto", 0),
                r.get("paginas", 0), len(r.get("documentos", [])), rojo, amar,
                "%.0f%%" % (100 * r.get("conf_ocr", 0))]
        for j, v in enumerate(fila, 1):
            c = ws.cell(5 + i, j, v); c.alignment = WRAP; c.border = BORDE; c.font = Font(size=9)
        c = ws.cell(5 + i, 8)
        if rojo:
            c.fill = PatternFill("solid", fgColor=ROJO_BG); c.font = Font(bold=True, size=9, color=ROJO_TX)
    ws.auto_filter.ref = f"A5:{get_column_letter(len(H))}{5 + len(resultados)}"

    # ---- Detalle: todos los riesgos, con su expediente ----
    ws2 = wb.create_sheet("Riesgos")
    H2 = ["Expediente", "OS N°", "Estado", "Nivel (matriz)", "ID", "Riesgo (el hecho)",
          "Evidencia en el expediente", "Página", "Marco legal", "Control a implementar",
          "Ejecuta", "Supervisa", "Cómo verificar"]
    W2 = [26, 10, 13, 12, 12, 46, 42, 12, 56, 56, 22, 22, 46]
    _encabezado(ws2, len(H2), "Riesgos detectados en todos los expedientes del lote", base)
    _tabla(ws2, 5, H2, W2)
    f = 5
    for r in resultados:
        ctx = r.get("contexto", {})
        rs = sorted(r.get("riesgos", []), key=lambda x: (x["nivel"] != "rojo",
                    {"MUY ALTO": 0, "ALTO": 1, "MEDIO": 2}.get(x.get("nivel_matriz"), 3)))
        for x in rs:
            f += 1
            rojo = x["nivel"] == "rojo"
            bl = "\n".join("• " + b["dispositivo"] + (": " + b["contenido"] if b.get("contenido") else "")
                           for b in x.get("base_legal", []))
            evid = " ".join(v for v in (x.get("nota", ""), x.get("evidencia", "")) if v)
            ubic = x.get("ubicaciones") or []
            pags = ", ".join(str(u["pagina"]) for u in ubic[:8]) if ubic else "— (por ausencia)"
            fila = [r.get("archivo", ""), ctx.get("os", ""), "CONFIRMADO" if rojo else "POR REVISAR",
                    x.get("nivel_matriz", ""), x["id"], x["hecho"], evid, pags, bl,
                    x.get("control", ""), x.get("ejecuta", ""), x.get("supervisa", ""),
                    x.get("como_verificar", "")]
            for j, v in enumerate(fila, 1):
                c = ws2.cell(f, j, v); c.alignment = WRAP; c.border = BORDE; c.font = Font(size=9)
            c = ws2.cell(f, 3)
            c.fill = PatternFill("solid", fgColor=ROJO_BG if rojo else AMB_BG)
            c.font = Font(bold=True, size=9, color=ROJO_TX if rojo else AMB_TX)
    ws2.auto_filter.ref = f"A5:{get_column_letter(len(H2))}{f}"

    # ---- Base legal y deslinde (iguales que en el Excel individual) ----
    ws3 = wb.create_sheet("Base legal")
    _encabezado(ws3, 2, "Base legal citada en la matriz", base)
    _tabla(ws3, 5, ["Dispositivo", "Contenido"], [48, 110])
    for i, b in enumerate(kb.get("base_legal", []), 1):
        for j, v in enumerate([b.get("dispositivo"), b.get("contenido")], 1):
            c = ws3.cell(5 + i, j, v); c.alignment = WRAP; c.border = BORDE
    ws4 = wb.create_sheet("Deslinde")
    _encabezado(ws4, 1, "Deslinde de responsabilidades", base)
    ws4.column_dimensions["A"].width = 130
    for i, d in enumerate(kb.get("deslinde", []), 1):
        c = ws4.cell(5 + i, 1, ("• " + d) if isinstance(d, str) else ("• " + d.get("texto", "")))
        c.alignment = WRAP; c.font = Font(size=9)
    wb.save(ruta)
    return ruta
