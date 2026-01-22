from flask import Blueprint, render_template
# IMPORTANTE: Agregar esta importación
from werkzeug.security import generate_password_hash

public_bp = Blueprint('public', __name__)

@public_bp.route("/")
def index(): return render_template("index.html")

@public_bp.route("/contacto")
def contacto(): return render_template("contacto.html")

@public_bp.route('/sobre-nosotros')
def sobre_nosotros(): return render_template('sobrenosotros.html')

@public_bp.route('/tipos-de-prestamo')
def tipos_prestamo(): return render_template('tipos_prestamo.html')

# --- RUTA TEMPORAL PARA GENERAR HASH ---
@public_bp.route("/create_hash/<password>")
def create_hash(password):
    # Esto generará el código encriptado para que lo copies
    return generate_password_hash(password)