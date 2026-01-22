from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
# Importamos las funciones de base de datos
from app.models import cargar_datos, guardar_registro, cargar_perfil, supabase
# Importamos las utilidades (incluyendo geocode_address)
from app.utils import login_required, perfil_completado, geocode_address
from config import Config 

client_bp = Blueprint('client', __name__)

@client_bp.route("/dashboard")
@login_required
def dashboard():
    # 1. Seguridad
    if session.get("correo") in Config.ADMIN_EMAILS: 
        return redirect(url_for("admin.administracion"))
    if session.get("rol") == "Empleado": 
        return redirect(url_for("employee.dashboard"))
    
    # 2. Validar Perfil
    correo = session.get("correo")
    if not perfil_completado(correo):
        return redirect(url_for('client.perfil_inicial'))

    # 3. Cargar Datos
    perfil = cargar_perfil(correo)
    
    # Cargar préstamos del usuario desde Supabase
    resp_prestamos = supabase.table("prestamos").select("*").eq("usuario_correo", correo).execute()
    mis_prestamos = resp_prestamos.data
    
    # Filtrar
    activo = next((p for p in mis_prestamos if p.get("estado") == "Activo"), None)
    historial = [p for p in mis_prestamos if p.get("estado") == "Pagado"]
    
    # Límites
    limite = Config.LIMITE_EMPLEADO if perfil.get("situacion_laboral") == "si" else Config.LIMITE_INDEPENDIENTE

    datos = {
        "fecha_actual": datetime.now().strftime("%d %b, %Y"),
        "prestamo_activo": None, 
        "historial_prestamos": historial,
        "proximos_pagos": [], 
        "limite_credito": limite
    }
        
    # 4. Lógica Préstamo Activo
    if activo:
        # Cargar pagos asociados a este préstamo
        resp_pagos = supabase.table("pagos").select("*").eq("prestamo_id", activo["id"]).execute()
        pagos_hechos = resp_pagos.data
        
        total_pagado = sum(float(p.get("monto", 0)) for p in pagos_hechos)
        valor_cuota = float(activo["valor_cuota"])
        cantidad_cuotas_total = activo.get("cantidad_cuotas")
        
        if valor_cuota > 0:
            cuotas_cubiertas = int(total_pagado // valor_cuota)
        else:
            cuotas_cubiertas = 0
            
        total_deuda = cantidad_cuotas_total * valor_cuota
        saldo_pendiente = total_deuda - total_pagado

        activo["progreso"] = round((cuotas_cubiertas / cantidad_cuotas_total) * 100) if cantidad_cuotas_total > 0 else 0
        activo["saldo_pendiente"] = saldo_pendiente
        activo["cuotas_pagadas"] = cuotas_cubiertas
        activo["cantidad_cuotas"] = cantidad_cuotas_total
        
        datos["prestamo_activo"] = activo

        # Proyección pagos
        try: 
            fecha_str = activo.get("fecha_aprobacion") or activo.get("fecha_solicitud")
            # Limpieza de formato ISO para evitar errores de zona horaria
            if fecha_str:
                fecha_base = datetime.fromisoformat(fecha_str.replace('Z', '+00:00')).replace(tzinfo=None)
            else:
                fecha_base = datetime.now()
        except: 
            fecha_base = datetime.now()
        
        frec = activo.get("frecuencia", "mensual")
        c = cuotas_cubiertas + 1
        
        for _ in range(3):
            if c > cantidad_cuotas_total: break
            
            if frec == 'diario': vence = fecha_base + timedelta(days=c)
            elif frec == 'semanal': vence = fecha_base + timedelta(weeks=c)
            elif frec == 'quincenal': vence = fecha_base + timedelta(days=c*15)
            else: vence = fecha_base + relativedelta(months=c)
            
            valor_a_mostrar = valor_cuota
            if c == (cuotas_cubiertas + 1):
                residuo_pago = total_pagado % valor_cuota
                valor_a_mostrar = valor_cuota - residuo_pago

            datos["proximos_pagos"].append({
                "numero_cuota": c, 
                "fecha_vencimiento": vence.strftime("%d %b, %Y"), 
                "valor": valor_a_mostrar
            })
            c += 1
            
    return render_template("dashboard.html", **datos)

@client_bp.route("/perfil-inicial")
@login_required
def perfil_inicial():
    return render_template("perfil_inicial.html")

@client_bp.route("/guardar_perfil", methods=["POST"])
@login_required
def guardar_perfil():
    correo = session['correo']
    datos_nuevos = request.form.to_dict()
    # Usar formato ISO para Supabase (PostgreSQL)
    datos_nuevos['fecha_registro'] = datetime.now().isoformat()

    # Geocodificación
    if datos_nuevos.get("direccion"):
        geo = geocode_address(datos_nuevos["direccion"])
        if geo: 
            datos_nuevos["latitud"] = geo["lat"]  # Ajustado a nombre columna BD
            datos_nuevos["longitud"] = geo["lon"]

    # Verificar si el usuario existe
    perfil = cargar_perfil(correo)
    
    try:
        if perfil:
            # Actualizar
            supabase.table("usuarios").update(datos_nuevos).eq("correo", correo).execute()
            flash("Perfil actualizado correctamente.", "success")
        else:
            # Crear (Raro si ya está logueado, pero por si acaso)
            datos_nuevos['correo'] = correo
            guardar_registro("usuarios", datos_nuevos)
    except Exception as e:
        print(f"Error al guardar perfil: {e}")
        flash("Error al guardar los datos.", "danger")

    # Actualizar nombre en sesión
    session['nombre'] = datos_nuevos.get('nombre', session.get('nombre'))
    
    if session.get("rol") == "Empleado":
        return redirect(url_for("employee.dashboard"))
    else:
        return redirect(url_for("client.dashboard"))

@client_bp.route("/ver-perfil")
@login_required
def ver_perfil():
    p = cargar_perfil(session['correo'])
    if not p:
        flash("No se encontraron datos del perfil.", "warning")
        return redirect(url_for('client.dashboard'))
    return render_template("ver_perfil.html", perfil=p)

@client_bp.route("/solicitar-prestamo", methods=["POST"])
@login_required
def solicitar_prestamo():
    correo = session.get("correo")
    
    # Verificar si ya tiene préstamo activo en BD
    # Se usa .or_ para chequear ambos estados
    res = supabase.table("prestamos").select("*").eq("usuario_correo", correo).or_("estado.eq.Activo,estado.eq.Pendiente").execute()
    
    if res.data and len(res.data) > 0:
        flash("Ya tienes un préstamo activo o pendiente.", "warning")
        return redirect(url_for('client.dashboard'))

    try:
        monto = int(request.form.get('monto_solicitado', 0))
        cuotas = int(request.form.get('cuotas', 0))
        frec = request.form.get('frecuencia', 'mensual')
    except:
        flash("Datos inválidos. Ingresa números correctos.", "danger")
        return redirect(url_for('client.dashboard'))

    perfil = cargar_perfil(correo)
    situacion = perfil.get("situacion_laboral", "no") if perfil else "no"
    limite = Config.LIMITE_EMPLEADO if situacion == "si" else Config.LIMITE_INDEPENDIENTE
    
    if monto > limite or monto <= 0:
        flash(f"Monto no permitido. Tu límite es ${limite:,.0f}", "danger")
        return redirect(url_for('client.dashboard'))

    # Cálculo financiero
    factor = 1
    if frec == 'diario': factor = 1/30
    elif frec == 'semanal': factor = 1/4
    elif frec == 'quincenal': factor = 1/2
    
    interes = monto * Config.TASA_INTERES_MENSUAL * (cuotas * factor if factor < 1 else cuotas)
    total = monto + interes
    valor_cuota = round(total / cuotas)
    
    # Buscar ID del cliente para la relación en BD
    usuario_data = supabase.table("usuarios").select("id").eq("correo", correo).execute()
    cliente_id = usuario_data.data[0]['id'] if usuario_data.data else None

    if not cliente_id:
        flash("Error de usuario no encontrado.", "danger")
        return redirect(url_for('auth.login'))

    nuevo_prestamo = {
        "cliente_id": cliente_id, # Relación FK
        "usuario_correo": correo, # Redundancia útil
        "monto_solicitado": monto,
        "cantidad_cuotas": cuotas,
        "frecuencia": frec,
        "tasa_interes": Config.TASA_INTERES_MENSUAL,
        "valor_cuota": valor_cuota,
        "saldo_pendiente": total,
        "estado": "Pendiente",
        "fecha_solicitud": datetime.now().isoformat()
    }
    
    try:
        guardar_registro("prestamos", nuevo_prestamo)
        flash("Solicitud enviada exitosamente.", "success")
    except Exception as e:
        print(f"Error solicitud: {e}")
        flash("Error al enviar la solicitud a la base de datos.", "danger")
        
    return redirect(url_for('client.dashboard'))