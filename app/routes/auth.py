from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from app.models import supabase # Usamos supabase directo para buscar eficiente
from app.utils import verificar_estado_usuario
from config import Config

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "").strip()
        
        # 1. BUSCAR USUARIO EN SUPABASE (Tabla 'usuarios', no login.json)
        try:
            response = supabase.table("usuarios").select("*").eq("correo", correo).execute()
            user = response.data[0] if response.data else None
        except Exception as e:
            print(f"Error BD: {e}")
            flash("Error de conexión con la base de datos.", "danger")
            return render_template("login.html")

        # 2. VERIFICAR CONTRASEÑA
        # Nota: En la BD la columna se llama 'password' o 'password_hash' según tu script SQL.
        # Intentamos obtener ambas por si acaso.
        hash_guardado = user.get("password") or user.get("password_hash") if user else ""
        
        if not user or not check_password_hash(hash_guardado, password):
            flash("Credenciales incorrectas.", "danger")
            return render_template("login.html")
        
        # 3. VERIFICAR ESTADO
        if verificar_estado_usuario(user) == "Inactivo":
            flash("Tu cuenta se encuentra inactiva.", "danger")
            return render_template("login.html")

        # 4. CREAR SESIÓN
        session.clear()
        session["logged_in"] = True
        session["correo"] = user["correo"]
        session["nombre"] = user.get("nombre", "Usuario")
        session["rol"] = user.get("rol", "Cliente")
        
        # 5. REDIRECCIONAR
        if user["correo"] in Config.ADMIN_EMAILS:
            return redirect(url_for("admin.administracion"))
        elif session["rol"] == "Empleado":
            return redirect(url_for("employee.dashboard")) 
        else:
            return redirect(url_for("client.dashboard"))

    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))