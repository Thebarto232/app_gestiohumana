import os
import logging
from flask import Flask
from dotenv import load_dotenv

try:
    from weasyprint import HTML
except (ImportError, OSError) as e:
    logging.warning(f"WeasyPrint no se pudo importar. La generación de PDF estará deshabilitada. Error: {e}")
    HTML = None

from .extensions import db, login_manager, mail
from .models import Empleado

load_dotenv()

def create_app():
    """Application Factory Function"""
    # Plantillas y estáticos en la raíz del proyecto, no dentro de app/
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(root_dir, 'templates')
    static_dir = os.path.join(root_dir, 'static')
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY', os.urandom(24)),
        SQLALCHEMY_DATABASE_URI=f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=None,  # se define abajo con ruta absoluta
        ALLOWED_EXTENSIONS={'pdf', 'png', 'jpg', 'jpeg'},
        MAIL_SERVER=os.getenv('MAIL_SERVER', 'smtp.googlemail.com'),
        MAIL_PORT=int(os.getenv('MAIL_PORT', 587)),
        MAIL_USE_TLS=os.getenv('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't'],
        MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
        MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=('Portal GH', os.getenv('MAIL_USERNAME'))
    )

    # Carpeta de uploads (ruta absoluta) para que subir_foto_perfil guarde en static de la raíz
    upload_path = os.path.join(static_dir, 'uploads')
    if not os.path.exists(upload_path):
        os.makedirs(upload_path, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_path

    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Empleado, user_id)

    with app.app_context():
        from .auth import auth_bp
        from .routes import admin_bp, main_bp
        app.register_blueprint(auth_bp)
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.register_blueprint(main_bp)

    return app

def allowed_file(filename, app):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
