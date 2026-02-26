import os
import logging
from flask import Flask
from dotenv import load_dotenv

# Intentar cargar WeasyPrint (Silencia el error si no tienes GTK instalado)
try:
    from weasyprint import HTML
except (ImportError, OSError) as e:
    logging.warning(f"WeasyPrint no se pudo importar. La generación de PDF estará deshabilitada. Error: {e}")
    HTML = None

# Importaciones de extensiones y modelos
from .extensions import db, login_manager, mail
from .models import Empleado

load_dotenv()

def create_app():
    """Application Factory Function"""
    app = Flask(__name__)

    # --- CONFIGURACIÓN ---
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY', os.urandom(24)),
        SQLALCHEMY_DATABASE_URI=f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER='static/uploads',
        ALLOWED_EXTENSIONS={'pdf', 'png', 'jpg', 'jpeg'},
        MAIL_SERVER=os.getenv('MAIL_SERVER', 'smtp.googlemail.com'),
        MAIL_PORT=int(os.getenv('MAIL_PORT', 587)),
        MAIL_USE_TLS=os.getenv('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't'],
        MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
        MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=('Portal GH', os.getenv('MAIL_USERNAME'))
    )

    # Crear carpeta de uploads si no existe
    upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    if not os.path.exists(upload_path):
        os.makedirs(upload_path, exist_ok=True)

    # --- INICIALIZAR EXTENSIONES ---
    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        # Usamos db.session.get que es la forma moderna en SQLAlchemy 2.0+
        return db.session.get(Empleado, user_id)

    with app.app_context():
        # --- REGISTRO DE BLUEPRINTS ---
        
        # Importación local para evitar importaciones circulares
        from .auth import auth_bp
        from .routes import admin_bp, main_bp
        
        # Registrar Blueprints
        app.register_blueprint(auth_bp)
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.register_blueprint(main_bp)

        # Crear tablas si no existen (solo para desarrollo)
        # db.create_all() 

    return app

def allowed_file(filename, app):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']