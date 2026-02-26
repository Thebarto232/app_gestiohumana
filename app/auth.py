import logging
from flask import Blueprint, render_template, request, flash, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from datetime import datetime

from .models import Empleado
from .extensions import db, mail

auth_bp = Blueprint('auth', __name__)
s = None

@auth_bp.record_once
def on_load(state):
    global s
    s = URLSafeTimedSerializer(state.app.secret_key)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_by_role(current_user)

    if request.method == 'POST':
        cedula = request.form.get('cedula')
        password = request.form.get('password')
        user = db.session.get(Empleado, cedula)

        if user and user.Estado_Laboral != 'Activo':
            flash("Su usuario se encuentra inactivo. Acceso denegado.", "warning")
            return render_template('login.html')

        if user and user.Contrasena and check_password_hash(user.Contrasena, password):
            login_user(user)
            return redirect_by_role(user)
        else:
            flash("Credenciales inválidas", "danger")
    return render_template('login.html')

def redirect_by_role(user):
    if user.rol_rel:
        role = user.rol_rel.nombre_rol
        if role == 'SUPERADMIN':
            return redirect(url_for('superadmin.dashboard'))
        elif role == 'RRHH':
            return redirect(url_for('rh.dashboard'))
        elif role == 'EMPLEADO':
            return redirect(url_for('empleado.dashboard'))
    # Fallback por si el empleado no tiene rol o el rol no es ninguno de los anteriores
    return redirect(url_for('empleado.dashboard'))


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        cedula = request.form.get('cedula')
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        password = request.form.get('password')
        fecha_nac = request.form.get('fecha_nacimiento')

        user_exists = db.session.get(Empleado, cedula)
        if user_exists:
            flash('La cédula ya está registrada. Por favor, inicia sesión.', 'warning')
            return redirect(url_for('auth.login'))

        hashed_password = generate_password_hash(password)
        # Por defecto, el auto-registro asigna el rol de Empleado (id=2)
        new_user = Empleado(
            ID_Cedula=cedula,
            Nombre_Completo=nombre,
            Correo_Electronico=email,
            Contrasena=hashed_password,
            id_rol=2, # Asumiendo que 2 es el ID para 'EMPLEADO'
            Fecha_Ingreso=datetime.now().date(),
            Fecha_Nacimiento=datetime.strptime(fecha_nac, '%Y-%m-%d').date() if fecha_nac else None
        )
        db.session.add(new_user)
        db.session.commit()
        flash('¡Registro exitoso! Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/request-password-reset', methods=['GET', 'POST'])
def request_password_reset():
    if request.method == 'POST':
        email = request.form.get('email')
        user = Empleado.query.filter_by(Correo_Electronico=email).first()
        if user:
            token = s.dumps(email, salt='password-reset-salt')
            reset_url = url_for('auth.reset_with_token', token=token, _external=True)
            msg = Message('Restablecimiento de Contraseña - Portal GH', recipients=[email])
            msg.body = f"Para restablecer tu contraseña, visita el siguiente enlace: {reset_url}"
            try:
                mail.send(msg)
                flash('Se ha enviado un correo con instrucciones.', 'info')
            except Exception as e:
                logging.error(f"Error al enviar correo de reseteo: {e}")
                flash('No se pudo enviar el correo. Contacta al administrador.', 'danger')
        else:
            flash('Si ese correo está en nuestro sistema, recibirás un enlace.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('request_password_reset.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_with_token(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=1800)
    except (SignatureExpired, BadTimeSignature):
        flash('El enlace es inválido o ha expirado.', 'danger')
        return redirect(url_for('auth.request_password_reset'))

    if request.method == 'POST':
        password = request.form.get('password')
        user = Empleado.query.filter_by(Correo_Electronico=email).first()
        if user:
            user.Contrasena = generate_password_hash(password)
            db.session.commit()
            flash('Contraseña actualizada. Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('reset_password_template.html', token=token)
