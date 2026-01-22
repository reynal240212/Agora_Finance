from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from app.models import supabase, cargar_perfil, guardar_registro, cargar_datos
from app.utils import login_required, employee_required, geocode_address
from config import Config
import random
from datetime import datetime

employee_bp = Blueprint('employee', __name__)

@employee_bp.route("/empleado/dashboard")
@login_required
def dashboard():
    # 1. Seguridad básica
    if session.get("rol") != "Empleado" and session.get("correo") not in Config.ADMIN_EMAILS:
        return redirect(url_for("auth.login"))

    es_admin = session.get('temp_admin_view_correo') is not None or session.get("correo") in Config.ADMIN_EMAILS
    
    # --- ELIMINADO: Ya no redirige a perfil_inicial si faltan datos ---

    email = session['correo']
    mi_perfil = cargar_perfil(email)
    
    # Obtener mi ID para filtrar por cobrador_asignado_id
    mi_id = mi_perfil.get('id') if mi_perfil else None
    
    # Coordenadas por defecto (Medellín) si el empleado no tiene dirección
    home = {"lat": 6.2442, "lon": -75.5812}
    
    if mi_perfil:
        if mi_perfil.get("latitud") and mi_perfil.get("longitud"):
            home = {"lat": mi_perfil["latitud"], "lon": mi_perfil["longitud"]}
        elif mi_perfil.get("direccion"):
            geo = geocode_address(mi_perfil["direccion"])
            if geo: home = geo

    # Cargar datos
    all_clients = cargar_datos("usuarios") 
    
    # Mapa para nombres de cobradores (para admin view)
    mapa_cobradores = {u['id']: f"{u['nombre']} {u['apellidos']}" for u in all_clients if u.get('rol') == 'Empleado'}

    clients_raw = []
    if es_admin:
        # Admin ve todo
        clients_raw = [u for u in all_clients if u.get("rol") == "Cliente"]
    else:
        # Empleado ve solo donde cobrador_asignado_id sea su ID
        if mi_id:
            clients_raw = [u for u in all_clients if u.get("cobrador_asignado_id") == mi_id]
    
    clients_processed = []
    for c in clients_raw:
        lat, lon = 0, 0
        if c.get("latitud") and c.get("longitud"): 
            lat, lon = c["latitud"], c["longitud"]
        elif c.get("direccion"):
            geo = geocode_address(c["direccion"])
            if geo: lat, lon = geo["lat"], geo["lon"]
            else: 
                lat = home["lat"] + random.uniform(-0.02, 0.02)
                lon = home["lon"] + random.uniform(-0.02, 0.02)
        else:
            lat = home["lat"] + random.uniform(-0.02, 0.02)
            lon = home["lon"] + random.uniform(-0.02, 0.02)

        # Nombre del cobrador
        cobrador_id = c.get("cobrador_asignado_id")
        nombre_cobrador = mapa_cobradores.get(cobrador_id, "Sin Asignar")

        clients_processed.append({
            "nombre": c.get("nombre", "N/A"), 
            "apellidos": c.get("apellidos", ""),
            "telefono": c.get("telefono") or c.get("numero", "N/A"), 
            "direccion": c.get("direccion", "Sin dir"),
            "correo": c.get("correo"),
            "lat": lat, "lon": lon,
            "cobrador": nombre_cobrador
        })

    return render_template("dashboard_empleado.html", employee_home=home, clients=clients_processed, admin_view=es_admin)

@employee_bp.route("/registrar_pago", methods=["POST"])
@login_required
def registrar_pago():
    data = request.json
    correo_cliente = data.get('correo')
    monto = data.get('monto')
    obs = data.get('observaciones')
    
    if not correo_cliente or not monto: return jsonify({"success": False, "message": "Datos incompletos"})
    try: monto = int(monto)
    except: return jsonify({"success": False, "message": "Monto inválido"})

    # 1. Buscar préstamo activo
    res = supabase.table("prestamos").select("*").eq("usuario_correo", correo_cliente).eq("estado", "Activo").execute()
    activo = res.data[0] if res.data else None
    
    if not activo: return jsonify({"success": False, "message": "Cliente sin préstamo activo."})
    
    # Buscar IDs
    cliente_id = activo.get('cliente_id')
    perfil_cobrador = cargar_perfil(session['correo'])
    cobrador_id = perfil_cobrador.get('id') if perfil_cobrador else None

    # 2. Registrar
    nuevo_pago = {
        "prestamo_id": activo["id"],
        "cliente_id": cliente_id,
        "cobrador_id": cobrador_id,
        "monto": monto,
        "fecha_pago": datetime.now().isoformat(),
        "observaciones": obs,
        "metodo_pago": "Efectivo"
    }
    
    try:
        guardar_registro("pagos", nuevo_pago)
        return jsonify({"success": True})
    except Exception as e:
        print(e)
        return jsonify({"success": False, "message": "Error DB"})