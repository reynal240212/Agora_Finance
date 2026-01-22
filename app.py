import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
import requests
from supabase import create_client, Client

# --- CONFIGURACIÓN DE RUTAS DINÁMICAS (Para Vercel) ---
base_dir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(base_dir, 'app', 'templates')
static_dir = os.path.join(base_dir, 'app', 'static')

app = Flask(__name__, 
            template_folder=template_dir, 
            static_folder=static_dir)

app.secret_key = os.environ.get("SECRET_KEY", "067861b84dfa59352ff40b9943cf048ca7a401e5a6c21348")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# --- CONFIGURACIÓN DE SUPABASE ---
SUPABASE_URL = "https://clpypbkkjwaixbexdepd.supabase.co"
# Es mejor usar os.environ para la KEY, pero mantengo la tuya para que funcione ya mismo
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNscHlwYmtrandhaXhiZXhkZXBkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQxNzk0MjMsImV4cCI6MjA3OTc1NTQyM30.-RgEv47KXtPqFjeL1UI5Ocmj0HOzHCGaxl3SJGF-8fE")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONSTANTES ---
ADMIN_EMAILS = ("admin@gmail.com", "santiago@gmail.com", "diego@gmail.com")
LIMITE_EMPLEADO = 5000000
LIMITE_INDEPENDIENTE = 1500000
TASA_INTERES_MENSUAL = 0.025 

# --- FUNCIONES DE APOYO ---
def geocode_address(address):
    if not address: return None
    headers = {'User-Agent': 'AgoraFinanceApp/1.0'}
    url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json"
    try:
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data: return {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}
    except: pass
    return None

# --- DECORADORES ---
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "logged_in" not in session:
            flash("Por favor inicia sesión primero.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in") or session.get("rol") != "Administrador":
            flash("⛔ Acceso denegado. Se requieren permisos de administrador.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper

# --- RUTAS PÚBLICAS ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/contacto")
def contacto():
    return render_template("contacto.html")

@app.route('/sobre-nosotros')
def sobre_nosotros():
    return render_template('sobrenosotros.html')

@app.route('/tipos-de-prestamo')
def tipos_prestamo():
    return render_template('tipos_prestamo.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "").strip()
        try:
            res = supabase.table("usuarios").select("*").eq("correo", correo).execute()
            usuario = res.data[0] if res.data else None
            if not usuario or not check_password_hash(usuario.get("password_hash", ""), password):
                flash("Credenciales incorrectas.", "danger")
                return render_template("login.html")
            if usuario.get("estado") == "Inactivo":
                flash("Tu cuenta se encuentra inactiva.", "danger")
                return render_template("login.html")
            session.clear()
            session.permanent = True
            session["logged_in"] = True
            session["user_id"] = usuario["id"]
            session["correo"] = usuario["correo"]
            session["nombre"] = usuario.get("nombre", "Usuario")
            session["rol"] = usuario.get("rol", "Cliente")
            flash(f"¡Bienvenido, {session['nombre']}!", "success")
            if session["rol"] == "Administrador": return redirect(url_for("administracion"))
            elif session["rol"] == "Empleado": return redirect(url_for("dashboard_empleado"))
            else: return redirect(url_for("dashboard"))
        except Exception as e:
            flash("Error de conexión.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("login"))

# --- RUTAS DE CLIENTE ---
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session.get("user_id")
    res_u = supabase.table("usuarios").select("*").eq("id", user_id).execute()
    perfil = res_u.data[0] if res_u.data else None
    if not perfil or not perfil.get("direccion") or not perfil.get("telefono"):
        flash("Por favor completa tu perfil para continuar.", "info")
        return redirect(url_for('perfil_inicial'))
    res_p = supabase.table("prestamos").select("*").eq("cliente_id", user_id).execute()
    prestamos = res_p.data
    activo = next((p for p in prestamos if p.get("estado") == "Activo"), None)
    datos = {
        "fecha_actual": datetime.now().strftime("%d %b, %Y"),
        "prestamo_activo": activo,
        "limite_credito": LIMITE_EMPLEADO if perfil.get("situacion_laboral") == "Si" else LIMITE_INDEPENDIENTE
    }
    if activo:
        res_pagos = supabase.table("pagos").select("*").eq("prestamo_id", activo["id"]).execute()
        total_pagado = sum(float(p.get("monto", 0)) for p in res_pagos.data)
        total_deuda = activo["cantidad_cuotas"] * float(activo["valor_cuota"])
        activo["saldo_pendiente_calc"] = total_deuda - total_pagado
        activo["cuotas_pagadas"] = int(total_pagado // float(activo["valor_cuota"]))
        activo["progreso"] = round((total_pagado / total_deuda) * 100) if total_deuda > 0 else 0
    return render_template("dashboard.html", **datos)

# --- RUTAS DE EMPLEADO Y PAGOS ---
@app.route("/empleado/dashboard")
@login_required
def dashboard_empleado():
    if session.get("rol") not in ["Empleado", "Administrador"]:
        flash("Acceso restringido.", "danger")
        return redirect(url_for("index"))
    user_id = session.get("user_id")
    query = supabase.table("usuarios").select("*").eq("rol", "Cliente")
    if session.get("rol") == "Empleado":
        query = query.eq("cobrador_asignado_id", user_id)
    res = query.execute()
    return render_template("dashboard_empleado.html", clients=res.data, employee_home={"lat": 6.2442, "lon": -75.5812})

@app.route("/registrar_pago", methods=["POST"])
@login_required
def registrar_pago():
    data = request.json
    cliente_id = data.get('cliente_id')
    monto = float(data.get('monto', 0))
    res_p = supabase.table("prestamos").select("*").eq("cliente_id", cliente_id).eq("estado", "Activo").execute()
    activo = res_p.data[0] if res_p.data else None
    if not activo: return jsonify({"success": False, "message": "Sin préstamo activo"})
    nuevo_pago = {
        "prestamo_id": activo["id"],
        "cliente_id": cliente_id,
        "monto": monto,
        "cobrador_id": session['user_id'],
        "metodo_pago": data.get('metodo', 'Efectivo'),
        "observaciones": data.get('observaciones', '')
    }
    supabase.table("pagos").insert(nuevo_pago).execute()
    res_all_pagos = supabase.table("pagos").select("monto").eq("prestamo_id", activo["id"]).execute()
    total_pagado = sum(float(p["monto"]) for p in res_all_pagos.data)
    if total_pagado >= (float(activo["valor_cuota"]) * activo["cantidad_cuotas"]):
        supabase.table("prestamos").update({"estado": "Pagado"}).eq("id", activo["id"]).execute()
    return jsonify({"success": True})

# --- ADMINISTRACIÓN ---
@app.route("/administracion")
@admin_required
def administracion():
    res = supabase.table("usuarios").select("*").execute()
    usuarios = res.data
    empleados = [u for u in usuarios if u.get("rol") == "Empleado"]
    return render_template("administracion.html", usuarios=usuarios, empleados=empleados)

@app.route("/admin/gestion-prestamos")
@admin_required
def gestion_prestamos():
    res_p = supabase.table("prestamos").select("*, usuarios!prestamos_cliente_id_fkey(nombre, apellidos)").execute()
    res_e = supabase.table("usuarios").select("*").eq("rol", "Empleado").execute()
    return render_template("gestion_prestamos.html", prestamos=res_p.data, empleados=res_e.data)

@app.route("/perfil-inicial")
@login_required
def perfil_inicial():
    res = supabase.table("usuarios").select("*").eq("id", session['user_id']).execute()
    perfil = res.data[0] if res.data else {}
    return render_template("perfil_inicial.html", perfil=perfil)

@app.route("/guardar_perfil", methods=["POST"])
@login_required
def guardar_perfil():
    user_id = session['user_id']
    form_data = request.form.to_dict()
    update_data = {
        "direccion": form_data.get("direccion"),
        "telefono": form_data.get("telefono"),
        "cedula": form_data.get("cedula"),
        "situacion_laboral": form_data.get("situacion_laboral", "No"),
        "empresa_nombre": form_data.get("empresa_nombre"),
        "salario": float(form_data.get("salario", 0)) if form_data.get("salario") else 0
    }
    geo = geocode_address(update_data["direccion"])
    if geo: update_data["latitud"], update_data["longitud"] = geo["lat"], geo["lon"]
    try:
        supabase.table("usuarios").update(update_data).eq("id", user_id).execute()
        flash("Perfil actualizado correctamente.", "success")
    except:
        flash("Error al actualizar perfil.", "danger")
    return redirect(url_for("dashboard"))

# --- VERCEL EXPORT ---
app = app

if __name__ == "__main__":
    app.run(debug=True, port=5000)