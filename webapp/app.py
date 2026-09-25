# -*- coding: utf-8 -*-
"""Gestión de Riesgo — ISO Calidad · Antisoborno (OLG) · aplicación web.

Azure App Service (Linux) · Startup Command:
    gunicorn --bind=0.0.0.0 --timeout 600 --workers 1 --threads 8 app:app

Llaves y claves se configuran en 'Application settings' (nunca en el código):
  AZURE_DI_ENDPOINT, AZURE_DI_KEY, AZURE_BLOB_CONN, AZURE_BLOB_CONTAINER,
  ADMIN_MASTER_CODE (contraseña maestra del administrador), SECRET_KEY (opcional).
"""
import os, io, json, tempfile, functools
from datetime import datetime
from flask import Flask, request, jsonify, send_file, Response, abort
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import store, jobs

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024       # 300 MB por subida
SER = URLSafeTimedSerializer(store.secret_key(), salt="gr-olg-sesion")
SESION_H = 12

FAMILIAS = {"CM": "Contratos Menores de Bienes y Servicios",
            "LS": "Contratación de Locadores de Servicios"}

def familias_permitidas(user):
    if user["rol"] == "admin": return ["CM", "LS"]
    a = (user.get("area") or "").lower()
    if "locador" in a: return ["LS"]
    if "menor" in a: return ["CM"]
    return ["CM", "LS"]

# ---------------- sesión ----------------
def _token(user): return SER.dumps(user)

def usuario_actual():
    t = request.headers.get("Authorization", "").removeprefix("Bearer ").strip() or request.args.get("t", "")
    if not t: return None
    try: return SER.loads(t, max_age=SESION_H * 3600)
    except (BadSignature, SignatureExpired): return None

def requiere(rol=None):
    def deco(f):
        @functools.wraps(f)
        def w(*a, **k):
            u = usuario_actual()
            if not u: return jsonify({"error": "Sesión expirada. Vuelve a ingresar."}), 401
            if rol and u["rol"] != rol: return jsonify({"error": "Solo para administradores."}), 403
            return f(u, *a, **k)
        return w
    return deco

def _job_propio(u, jid):
    m = jobs.meta(jid)
    if not m: abort(404)
    if u["rol"] != "admin" and m.get("usuario_id") != u["id"]: abort(403)
    return m

# ---------------- páginas ----------------
@app.get("/health")
def health(): return Response("ok", mimetype="text/plain")

@app.get("/")
def home():
    with open(os.path.join(BASE, "index.html"), encoding="utf-8") as f: html = f.read()
    html = html.replace("</head>", "<script>window.GR_SERVER=true;</script></head>", 1)
    i = html.rfind("</body>")                      # la etiqueta REAL (la última)
    html = html[:i] + '<script src="/gr_server.js"></script>' + html[i:]
    return Response(html, mimetype="text/html", headers={"Cache-Control": "no-store"})

@app.get("/gr_server.js")
def gr_server_js():
    return send_file(os.path.join(BASE, "gr_server.js"), mimetype="application/javascript", max_age=0)

@app.get("/api/config")
def config_check():
    import config
    return jsonify({"azure_di_endpoint_set": bool(config.AZURE_DI_ENDPOINT),
                    "azure_di_key_set": bool(config.AZURE_DI_KEY),
                    "blob_conn_set": bool(os.getenv("AZURE_BLOB_CONN")),
                    "admin_master_set": bool(os.getenv("ADMIN_MASTER_CODE")),
                    "modo_pruebas_ocr": bool(os.getenv("OCR_FAKE_CACHE")),
                    "modelo": config.AZURE_DI_MODELO, "data_dir": store.DATA_DIR,
                    "ocr": jobs.estado_ocr()})

# ---------------- login ----------------
@app.post("/api/login")
def login():
    d = request.get_json(force=True, silent=True) or {}
    if d.get("rol") == "admin":
        u, err = store.admin_login(d.get("usuario"), d.get("password"), d.get("master"))
    else:
        u, err = store.worker_login(d.get("nombre"), d.get("password"))
    if err:
        store.log(d.get("usuario") or d.get("nombre") or "?", "", "Intento de ingreso fallido", "", err)
        return jsonify({"error": err}), 401
    store.log(u["nombre"], u.get("area", ""), "Ingresó al sistema" + (" (cuenta creada)" if u.get("nuevo") else ""))
    u.pop("nuevo", None)
    return jsonify({"token": _token(u), "usuario": u, "familias": familias_permitidas(u)})

@app.get("/api/me")
@requiere()
def me(u): return jsonify({"usuario": u, "familias": familias_permitidas(u)})

# ---------------- trabajos ----------------
@app.post("/api/jobs")
@requiere()
def crear_job(u):
    f = request.files.get("file")
    if not f or not f.filename: return jsonify({"error": "Selecciona el PDF o ZIP del expediente."}), 400
    fam = (request.form.get("familia") or "").upper()
    if fam not in familias_permitidas(u):
        return jsonify({"error": "Tu cuenta no tiene permiso para ese subproceso."}), 403
    cortar = [c for c in request.form.getlist("cortar") if c in ("tdr", "requerimiento", "pago", "os")]
    try:
        jid = jobs.crear(u, f, fam, FAMILIAS[fam], cortar)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"id": jid, "meta": jobs.meta(jid)})

@app.get("/api/jobs")
@requiere()
def listar_jobs(u): return jsonify({"jobs": jobs.listar(u)})

# ---------------- varios expedientes de una vez ----------------
@app.post("/api/lotes")
@requiere()
def crear_lote(u):
    f = request.files.get("file")
    if not f or not f.filename: return jsonify({"error": "Selecciona el ZIP con los expedientes."}), 400
    fam = (request.form.get("familia") or "").upper()
    if fam not in familias_permitidas(u):
        return jsonify({"error": "Tu cuenta no tiene permiso para ese subproceso."}), 403
    cortar = [c for c in request.form.getlist("cortar") if c in ("tdr", "requerimiento", "pago", "os")]
    try:
        lid = jobs.crear_lote(u, f, fam, FAMILIAS[fam], cortar)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"lote": lid, "estado": jobs.lote_estado(lid)})

def _lote_propio(u, lid):
    m = jobs.lote_estado(lid)
    if not m: abort(404)
    if u["rol"] != "admin" and m.get("usuario_id") != u["id"]: abort(403)
    return m

@app.get("/api/lotes/<lid>")
@requiere()
def ver_lote(u, lid): return jsonify(_lote_propio(u, lid))

@app.get("/api/lotes/<lid>/excel")
@requiere()
def excel_lote(u, lid):
    m = _lote_propio(u, lid)
    resultados = [r for r in (jobs.resultado(h["id"]) for h in m["hijos"]) if r]
    if not resultados: abort(404)
    import excel_kb
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False); tmp.close()
    excel_kb.construir_lote(resultados, jobs.kb(), tmp.name)
    store.log(u["nombre"], u.get("area", ""), "Descargó Excel del lote", m.get("archivo", ""),
              f"{len(resultados)} expedientes")
    return send_file(tmp.name, as_attachment=True,
                     download_name="Verificacion_lote_%s.xlsx" % m["creado"][:10])

@app.get("/api/jobs/<jid>")
@requiere()
def ver_job(u, jid):
    m = _job_propio(u, jid)
    out = {"meta": m}
    if m.get("estado") == "listo": out["resultado"] = jobs.resultado(jid)
    return jsonify(out)

@app.delete("/api/jobs/<jid>")
@requiere()
def borrar_job(u, jid):
    m = _job_propio(u, jid)
    jobs.borrar(jid)
    store.log(u["nombre"], u.get("area", ""), "Limpió la consulta", m.get("archivo", ""))
    return jsonify({"ok": True})

@app.get("/api/jobs/<jid>/excel")
@requiere()
def excel(u, jid):
    _job_propio(u, jid)
    res = jobs.resultado(jid)
    if not res: abort(404)
    import excel_kb
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False); tmp.close()
    excel_kb.construir(res, jobs.kb(), tmp.name)
    osn = res.get("contexto", {}).get("os") or "expediente"
    nombre = f"Verificacion_OS{osn}_{res['fecha'][:10]}.xlsx"
    store.log(u["nombre"], u.get("area", ""), "Descargó Excel", res.get("archivo", ""))
    return send_file(tmp.name, as_attachment=True, download_name=nombre)

@app.get("/api/jobs/<jid>/pagina/<int:n>.png")
@requiere()
def pagina_png(u, jid, n):
    _job_propio(u, jid)
    res = jobs.resultado(jid) or {}
    dim = (res.get("paginas_dim") or {}).get(str(n)) or (res.get("paginas_dim") or {}).get(n)
    return Response(jobs.pagina_png(jid, n, dim_ocr=dim), mimetype="image/png",
                    headers={"Cache-Control": "private, max-age=600"})

@app.get("/api/jobs/<jid>/pagina/<int:n>.pdf")
@requiere()
def pagina_pdf(u, jid, n):
    m = _job_propio(u, jid)
    return send_file(io.BytesIO(jobs.pagina_pdf(jid, n)), mimetype="application/pdf",
                     as_attachment=True, download_name=f"pagina_{n}_{os.path.splitext(m['archivo'])[0]}.pdf")

@app.get("/api/jobs/<jid>/expediente.pdf")
@requiere()
def expediente(u, jid):
    _job_propio(u, jid)
    return send_file(jobs.pdf_path(jid), mimetype="application/pdf")

@app.get("/api/jobs/<jid>/corte/<int:i>")
@requiere()
def corte(u, jid, i):
    _job_propio(u, jid)
    res = jobs.resultado(jid) or {}
    cs = [c for c in res.get("cortes", []) if c["i"] == i]
    if not cs: abort(404)
    return send_file(os.path.join(jobs._dir(jid), "cortes", cs[0]["archivo"]),
                     as_attachment=True, download_name=cs[0]["archivo"])

# ---------------- administración ----------------
@app.get("/api/admin/usuarios")
@requiere("admin")
def usuarios(u): return jsonify({"usuarios": store.list_workers()})

@app.post("/api/admin/usuarios")
@requiere("admin")
def crear_usuario(u):
    d = request.get_json(force=True, silent=True) or {}
    w, pw, err = store.create_worker(d.get("nombre"), d.get("area"))
    if err: return jsonify({"error": err}), 400
    store.log(u["nombre"], "Admin", "Creó usuario", "", f"{w['nombre']} · {w['area']}")
    return jsonify({"usuario": w, "password": pw})

@app.post("/api/admin/usuarios/<uid>/reset")
@requiere("admin")
def reset_usuario(u, uid):
    pw = store.reset_worker(uid)
    if not pw: abort(404)
    store.log(u["nombre"], "Admin", "Regeneró contraseña", "", uid)
    return jsonify({"password": pw})

@app.delete("/api/admin/usuarios/<uid>")
@requiere("admin")
def borrar_usuario(u, uid):
    ok = store.delete_worker(uid)
    store.log(u["nombre"], "Admin", "Eliminó usuario", "", uid)
    return jsonify({"ok": ok})

@app.post("/api/admin/limpiar")
@requiere("admin")
def limpiar_antiguas(u):
    n = jobs.limpiar_antiguos(horas=float((request.get_json(silent=True) or {}).get("horas", 24)))
    store.log(u["nombre"], "Admin", "Limpió copias antiguas", "", f"{n} eliminadas (más de 24 h)")
    return jsonify({"eliminadas": n})

@app.get("/api/admin/respaldo")
@requiere("admin")
def descargar_respaldo(u):
    store.log(u["nombre"], "Admin", "Descargó respaldo")
    nombre = "respaldo_gestion_riesgo_%s.zip" % datetime.now().strftime("%Y-%m-%d")
    return send_file(io.BytesIO(store.respaldo_bytes()), mimetype="application/zip",
                     as_attachment=True, download_name=nombre)

@app.post("/api/admin/restaurar")
@requiere("admin")
def subir_respaldo(u):
    f = request.files.get("archivo")
    if not f:
        return jsonify({"error": "No llegó ningún archivo."}), 400
    try:
        repuestos = store.restaurar_zip(f.read())
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    store.log(u["nombre"], "Admin", "Restauró respaldo", "", ", ".join(repuestos))
    return jsonify({"restaurados": repuestos})

@app.get("/api/admin/actividad")
@requiere("admin")
def actividad(u): return jsonify({"actividad": store.actividad(300)})

@app.errorhandler(413)
def muy_grande(e): return jsonify({"error": "El archivo supera los 300 MB."}), 413

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
