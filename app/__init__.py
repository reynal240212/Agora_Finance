from flask import Flask
from flask_apscheduler import APScheduler
from config import Config

scheduler = APScheduler()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    scheduler.init_app(app)
    scheduler.start()

    # Registrar Blueprints (Rutas)
    from app.routes.public import public_bp
    from app.routes.auth import auth_bp
    from app.routes.client import client_bp
    from app.routes.employee import employee_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(admin_bp)

    return app