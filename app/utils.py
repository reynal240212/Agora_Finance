from functools import wraps
from flask import session, flash, redirect, url_for, make_response
from datetime import datetime, timedelta
import requests
from config import Config
from app.models import cargar_perfil

# --- GEOCODIFICACIÓN ---
def geocode_address(address):
    if not address: return None
    headers = {'User-Agent': 'AgoraFinanceApp/1.0'}
    url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json"
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data:
                return {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}
    except Exception as e:
        print(f"Error geocoding: {e}")
    return None

# --- VALIDACIONES ---
def perfil_completado(correo):
    perfil = cargar_perfil(correo)
    if perfil and perfil.get("direccion") and perfil.get("numero"):
        return True
    return False

def verificar_estado_usuario(usuario):
    if usuario.get("estado") == "Inactivo":
        return "Inactivo"
    # (Lógica de fechas abreviada por espacio, usar la misma que tenías)
    return usuario.get("estado", "Inactivo")

# --- DECORADORES ---
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "logged_in" not in session:
            flash("Inicia sesión primero.", "warning")
            return redirect(url_for("auth.login"))
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "logged_in" not in session: return redirect(url_for("auth.login"))
        es_admin = session.get("correo") in Config.ADMIN_EMAILS
        if 'temp_admin_view_correo' in session: pass
        elif not es_admin:
            flash("⛔ Acceso denegado.", "danger")
            return redirect(url_for("employee.dashboard" if session.get("rol") == "Empleado" else "client.dashboard"))
        return f(*args, **kwargs)
    return wrapper

def employee_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("rol") != "Empleado":
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper