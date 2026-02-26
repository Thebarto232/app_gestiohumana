from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail

# 1. Inicialización de las extensiones (sin la app aún)
db = SQLAlchemy()
mail = Mail()
login_manager = LoginManager()

# 2. Configuración de seguridad para LoginManager
# Esto asegura que si alguien intenta entrar a una ruta @login_required 
# sin estar logueado, Flask sepa a dónde mandarlo.
login_manager.login_view = 'auth.login'
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
login_manager.login_message_category = "info"