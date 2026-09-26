# -*- coding: utf-8 -*-
"""Datos persistentes pequeños (no expedientes): usuarios, bitácora y acumulado.

Se guardan en DATA_DIR. En Azure App Service Linux, /home es persistente, así que
por defecto se usa /home/data. Las contraseñas se guardan con hash PBKDF2 (nunca
en texto plano), por eso la contraseña generada solo se muestra al crearla."""
import os, json, secrets, hashlib, hmac, threading, time, re, unicodedata, uuid
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR") or ("/home/data" if os.path.isdir("/home/site") else os.path.join(BASE, "data"))
os.makedirs(DATA_DIR, exist_ok=True)
PE = timezone(timedelta(hours=-5))          # hora de Lima
_lock = threading.RLock()

def ahora():
    return datetime.now(PE).strftime("%Y-%m-%d %H:%M:%S")

def _p(n): return os.path.join(DATA_DIR, n)

def _load(n, default):
    try:
        with open(_p(n), encoding="utf-8") as f: return json.load(f)
    except Exception:
        return default

def _save(n, obj):
    tmp = _p(n) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _p(n))

def _norm(t):
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.lower()).strip()

# ---------------- secreto para firmar sesiones ----------------
def secret_key():
    k = os.getenv("SECRET_KEY")
    if k: return k
    with _lock:
        if not os.path.exists(_p("secret.key")):
            with open(_p("secret.key"), "w") as f: f.write(secrets.token_hex(32))
        return open(_p("secret.key")).read().strip()

# ---------------- contraseñas ----------------
def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
    return f"{salt}${h}"

def check_pw(pw, stored):
    try:
        salt = stored.split("$", 1)[0]
        return hmac.compare_digest(hash_pw(pw, salt), stored)
    except Exception:
        return False

_ALF_L = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz"
_ALF_D = "23456789"
def gen_password(n=8):
    while True:
        pw = "".join(secrets.choice(_ALF_L + _ALF_D) for _ in range(n))
        if any(c in _ALF_D for c in pw) and any(c in _ALF_L for c in pw):
            return pw

# ---------------- usuarios ----------------
def _users():
    return _load("usuarios.json", {"admins": [], "workers": []})

def admin_login(usuario, pw, master):
    """La contraseña maestra (variable ADMIN_MASTER_CODE en Azure) habilita el acceso.
    Si el usuario administrador no existe, se crea en ese momento con la
    contraseña que escribió; si existe, se valida."""
    real = os.getenv("ADMIN_MASTER_CODE", "")
    if not real:
        return None, "Falta configurar ADMIN_MASTER_CODE en Azure (Application settings)."
    if not hmac.compare_digest(master or "", real):
        return None, "Contraseña maestra incorrecta."
    usuario = (usuario or "").strip()
    if len(usuario) < 3 or len(pw or "") < 6:
        return None, "Usuario (mín. 3) y contraseña (mín. 6 caracteres) son obligatorios."
    with _lock:
        u = _users()
        for a in u["admins"]:
            if _norm(a["usuario"]) == _norm(usuario):
                if check_pw(pw, a["pw"]):
                    return {"id": a["id"], "nombre": a["usuario"], "rol": "admin", "area": "Todas"}, None
                return None, "Contraseña del administrador incorrecta."
        a = {"id": "adm-" + uuid.uuid4().hex[:8], "usuario": usuario, "pw": hash_pw(pw), "creado": ahora()}
        u["admins"].append(a); _save("usuarios.json", u)
        return {"id": a["id"], "nombre": usuario, "rol": "admin", "area": "Todas", "nuevo": True}, None

def worker_login(nombre, pw):
    with _lock:
        for w in _users()["workers"]:
            if w.get("activo", True) and _norm(w["nombre"]) == _norm(nombre) and check_pw(pw or "", w["pw"]):
                return {"id": w["id"], "nombre": w["nombre"], "rol": "trabajador", "area": w["area"]}, None
    return None, "Nombre o contraseña incorrectos."

def create_worker(nombre, area):
    nombre = (nombre or "").strip()
    if len(nombre) < 3: return None, None, "Escribe el nombre completo."
    with _lock:
        u = _users()
        if any(_norm(w["nombre"]) == _norm(nombre) for w in u["workers"]):
            return None, None, "Ya existe un usuario con ese nombre."
        pw = gen_password()
        w = {"id": "usr-" + uuid.uuid4().hex[:8], "nombre": nombre, "area": area or "",
             "pw": hash_pw(pw), "creado": ahora(), "activo": True}
        u["workers"].append(w); _save("usuarios.json", u)
        return _pub(w), pw, None

def reset_worker(uid):
    with _lock:
        u = _users()
        for w in u["workers"]:
            if w["id"] == uid:
                pw = gen_password(); w["pw"] = hash_pw(pw); _save("usuarios.json", u)
                return pw
    return None

def delete_worker(uid):
    with _lock:
        u = _users(); n = len(u["workers"])
        u["workers"] = [w for w in u["workers"] if w["id"] != uid]
        _save("usuarios.json", u); return len(u["workers"]) < n

def _pub(w): return {k: w[k] for k in ("id", "nombre", "area", "creado")}
def list_workers(): return [_pub(w) for w in _users()["workers"]]

# ---------------- bitácora ----------------
def log(usuario, area, accion, expediente="", detalle=""):
    rec = {"t": ahora(), "usuario": usuario, "area": area, "accion": accion,
           "expediente": expediente, "detalle": detalle}
    with _lock, open(_p("actividad.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def actividad(n=200):
    try:
        with open(_p("actividad.jsonl"), encoding="utf-8") as f: lines = f.readlines()[-n:]
        return [json.loads(l) for l in reversed(lines)]
    except Exception:
        return []

# ---------------- acumulado (fraccionamiento) ----------------
def acumulado_previo(clave, anio, excluir_os):
    """Montos de OTRAS órdenes del mismo objeto en el mismo año."""
    acc = _load("acumulado.json", {})
    return [r["monto"] for osn, r in acc.get(str(anio), {}).items()
            if r.get("clave") == clave and osn != str(excluir_os) and r.get("monto")]

def acumulado_guardar(anio, osn, clave, rec):
    if not (anio and osn and clave): return
    with _lock:
        acc = _load("acumulado.json", {})
        acc.setdefault(str(anio), {})[str(osn)] = dict(rec, clave=clave, t=ahora())
        _save("acumulado.json", acc)


# ---------------- respaldo (para no quedar amarrado a ningún servidor) ----------------
ARCHIVOS_RESPALDO = ("usuarios.json", "acumulado.json", "actividad.jsonl")

def respaldo_bytes():
    """Arma un ZIP con TODO lo que no se puede volver a generar: cuentas,
    acumulado de fraccionamiento y bitácora de actividad. No lleva expedientes."""
    import zipfile, io as _io
    buf = _io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ARCHIVOS_RESPALDO:
            if os.path.exists(_p(n)):
                z.write(_p(n), n)
        z.writestr("RESPALDO.txt",
                   "Respaldo de Gestión de Riesgo (OLG)\n"
                   "Fecha: %s\n\n"
                   "Contiene: cuentas de usuario (contraseñas cifradas), acumulado de\n"
                   "fraccionamiento y bitácora de actividad.\n"
                   "Para restaurarlo: Administrador → Ajustes → Restaurar respaldo,\n"
                   "o copie estos archivos a la carpeta 'data' de la aplicación.\n"
                   % ahora())
    return buf.getvalue()

def restaurar_zip(data):
    """Restaura un respaldo. Devuelve la lista de archivos repuestos."""
    import zipfile, io as _io
    repuestos = []
    with _lock, zipfile.ZipFile(_io.BytesIO(data)) as z:
        for n in ARCHIVOS_RESPALDO:
            if n in z.namelist():
                contenido = z.read(n)
                if n.endswith(".json"):
                    json.loads(contenido.decode("utf-8"))      # valida antes de pisar
                if os.path.exists(_p(n)):
                    os.replace(_p(n), _p(n + ".anterior"))
                with open(_p(n), "wb") as f:
                    f.write(contenido)
                repuestos.append(n)
    if not repuestos:
        raise ValueError("Ese ZIP no es un respaldo de esta aplicación.")
    return repuestos
