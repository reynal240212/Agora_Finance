from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from datetime import datetime
from app.models import cargar_datos, guardar_registro, actualizar_registro, supabase
from app.utils import admin_required, verificar_estado_usuario
from config import Config

admin_bp = Blueprint('admin', __name__)

@admin_bp.route("/administracion")
@admin_required
def administracion():
    filtro = request.args.get("filtro")
    valor = request.args.get("valor")
    
    # 1. Cargar usuarios
    usuarios = cargar_datos("usuarios") or []
    
    # 2. Crear un "Diccionario" para traducir ID -> Correo/Nombre del empleado
    # Esto sirve para que la tabla HTML sepa quién es el cobrador
    mapa_empleados = {u['id']: u for u in usuarios if u.get('rol') == 'Empleado'}

    # 3. Procesar usuarios para el HTML
    for u in usuarios:
        u["estado_actual"] = u.get("estado", "Activo")
        u["expiracion_str"] = "Permanente"
        
        # TRUCO: Inyectamos el campo 'empleado_asignado_correo' que espera el HTML
        # basándonos en el ID de la base de datos
        cobrador_id = u.get("cobrador_asignado_id")
        if cobrador_id and cobrador_id in mapa_empleados:
            u["empleado_asignado_correo"] = mapa_empleados[cobrador_id]["correo"]
        else:
            u["empleado_asignado_correo"] = None

    # 4. Filtros de búsqueda
    mostrar = usuarios
    if filtro and valor:
        valor = valor.lower()
        mostrar = [u for u in usuarios if str(u.get(filtro, "")).lower().startswith(valor)]
            
    empleados = [u for u in usuarios if u.get("rol") == "Empleado"]
    
    return render_template("administracion.html", usuarios=mostrar, empleados=empleados)

@admin_bp.route("/agregar_usuario", methods=["POST"])
@admin_required
def agregar_usuario():
    correo = request.form["correo"].lower().strip()
    
    res = supabase.table("usuarios").select("id").eq("correo", correo).execute()
    if res.data:
        flash("El correo ya existe.", "danger")
        return redirect(url_for("admin.administracion"))
    
    rol = request.form.get("rol", "Cliente")
    
    new_user = {
        "rol": rol,
        "nombre": request.form["nombre"],
        "apellidos": request.form["apellidos"],
        "cedula": request.form["cedula"],
        "telefono": request.form["numero"],
        "correo": correo,
        "password": generate_password_hash(request.form["password"]),
        "direccion": request.form.get("direccion"),
        "estado": "Inactivo",
        "fecha_registro": datetime.now().isoformat()
    }

    # LÓGICA CORREGIDA: Convertir Correo -> ID
    if rol == "Cliente":
        emp_correo = request.form.get("empleado_asignado")
        if emp_correo:
            # Buscar el ID del empleado con ese correo
            res_emp = supabase.table("usuarios").select("id").eq("correo", emp_correo).execute()
            if res_emp.data:
                new_user["cobrador_asignado_id"] = res_emp.data[0]['id']

    try:
        guardar_registro("usuarios", new_user)
        flash("Usuario creado.", "success")
    except Exception as e:
        print(f"Error: {e}")
        flash("Error al guardar en base de datos.", "danger")

    return redirect(url_for("admin.administracion", filtro='mostrar_todo', valor=''))

@admin_bp.route("/editar_usuario/<int:id>", methods=["POST"])
@admin_required
def editar_usuario(id):
    updates = {
        "rol": request.form.get("rol"),
        "nombre": request.form["nombre"],
        "apellidos": request.form["apellidos"],
        "cedula": request.form["cedula"],
        "telefono": request.form["numero"],
        "correo": request.form["correo"].lower().strip(),
        "direccion": request.form.get("direccion")
    }
    
    # LÓGICA CORREGIDA: Convertir Correo -> ID
    if updates["rol"] == "Cliente":
        emp_correo = request.form.get("empleado_asignado")
        if emp_correo:
            res_emp = supabase.table("usuarios").select("id").eq("correo", emp_correo).execute()
            if res_emp.data:
                updates["cobrador_asignado_id"] = res_emp.data[0]['id']
        else:
            updates["cobrador_asignado_id"] = None # Desasignar

    pw = request.form.get("password")
    if pw and pw.strip():
        updates["password"] = generate_password_hash(pw)

    try:
        actualizar_registro("usuarios", id, updates)
        flash("Actualizado correctamente.", "success")
    except Exception as e:
        print(f"Error update: {e}")
        flash("Error al actualizar.", "danger")
            
    return redirect(url_for("admin.administracion", filtro='mostrar_todo', valor=''))

@admin_bp.route("/activar_desactivar_usuario/<int:id>", methods=["POST"])
@admin_required
def activar_desactivar_usuario(id):
    act = request.form.get("accion")
    updates = {"estado": "Activo" if act == "activar" else "Inactivo"}
    
    actualizar_registro("usuarios", id, updates)
    return redirect(url_for("admin.administracion", filtro='mostrar_todo', valor=''))

@admin_bp.route("/admin/vista-empleados")
@admin_required
def vista_empleados():
    res = supabase.table("usuarios").select("*").eq("rol", "Empleado").limit(1).execute()
    emp = res.data[0] if res.data else None
    
    if not emp: 
        flash("No hay empleados.", "warning")
        return redirect(url_for('admin.administracion'))
    
    session['temp_admin_view_correo'] = session['correo']
    session['correo'] = emp['correo'] 
    session['rol'] = 'Empleado'
    return redirect(url_for('employee.dashboard'))

@admin_bp.route("/admin/gestion-prestamos")
@admin_required
def gestion_prestamos():
    prestamos = cargar_datos("prestamos") or []
    usuarios = cargar_datos("usuarios") or []
    pagos = cargar_datos("pagos") or []
    
    mapa_usuarios = {u['id']: u for u in usuarios} # Mapa por ID ahora
    
    for p in prestamos:
        # Usamos cliente_id para buscar (clave foranea)
        u = mapa_usuarios.get(p.get('cliente_id'))
        if u:
            p['nombre_cliente'] = f"{u.get('nombre','')} {u.get('apellidos','')}"
            p['usuario_correo'] = u.get('correo')
        else:
            p['nombre_cliente'] = "Desconocido"
        
        pagos_prestamo = [pg for pg in pagos if pg.get('prestamo_id') == p['id']]
        total_pagado = sum(float(pg.get("monto", 0) or 0) for pg in pagos_prestamo)
        
        valor_cuota = float(p.get("valor_cuota", 0) or 0)
        cantidad_cuotas = int(p.get("cantidad_cuotas", 0) or 0)
        p['saldo_pendiente'] = (cantidad_cuotas * valor_cuota) - total_pagado
        
    empleados = [u for u in usuarios if u.get("rol") == "Empleado"]
    return render_template("gestion_prestamos.html", prestamos=prestamos, empleados=empleados)

@admin_bp.route("/admin/procesar-prestamo/<int:pid>", methods=["POST"])
@admin_required
def procesar_prestamo(pid):
    estado = request.form.get("nuevo_estado")
    
    # Obtener préstamo
    res = supabase.table("prestamos").select("*").eq("id", pid).execute()
    if not res.data: return redirect(url_for('admin.gestion_prestamos'))
    prestamo = res.data[0]
    
    updates = {}

    if estado == "Activo":
        # Verificar si el cliente tiene cobrador asignado
        cliente_id = prestamo.get('cliente_id')
        res_user = supabase.table("usuarios").select("cobrador_asignado_id").eq("id", cliente_id).execute()
        
        if not res_user.data or not res_user.data[0].get('cobrador_asignado_id'):
            # Intentar asignar el seleccionado en el modal
            emp_correo = request.form.get("empleado_correo")
            if emp_correo:
                res_emp = supabase.table("usuarios").select("id").eq("correo", emp_correo).execute()
                if res_emp.data:
                    emp_id = res_emp.data[0]['id']
                    # Asignar al usuario
                    supabase.table("usuarios").update({"cobrador_asignado_id": emp_id}).eq("id", cliente_id).execute()
            else:
                flash("Error: El cliente no tiene cobrador. Selecciona uno.", "warning")
                return redirect(url_for('admin.gestion_prestamos'))

        updates["estado"] = "Activo"
        updates["fecha_aprobacion"] = datetime.now().isoformat()

    elif estado == "Rechazado":
        updates["estado"] = "Rechazado"
    
    actualizar_registro("prestamos", pid, updates)
    flash("Préstamo actualizado.", "success")
    return redirect(url_for('admin.gestion_prestamos'))

@admin_bp.route("/verificar_vencimientos")
@admin_required
def verificar_vencimientos():
    return redirect(url_for("admin.administracion"))