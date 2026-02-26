from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import extract

from .extensions import db
from .models import Empleado, Hijos, Eps, FondoPensiones, PerfilOcupacional, PagoNomina
from .security.permissions import role_required

try:
    from weasyprint import HTML
except (ImportError, OSError):
    HTML = None

empleado_bp = Blueprint('empleado', __name__, url_prefix='/empleado')

def _calcular_nomina(salario_base):
    salario = float(salario_base) if salario_base else 0.0
    salud = salario * 0.04
    pension = salario * 0.04
    neto = salario - (salud + pension)
    aux_transporte = 0.0  # simplificado
    total_devengado = salario + aux_transporte
    total_deducido = salud + pension
    return {
        'salario': salario, 'salud': salud, 'pension': pension, 'neto': neto,
        'aux_transporte': aux_transporte, 'total_devengado': total_devengado, 'total_deducido': total_deducido
    }

def _normalizar_fecha(fecha):
    if not fecha:
        return None
    if isinstance(fecha, datetime):
        return fecha.date()
    if isinstance(fecha, str):
        try:
            return datetime.strptime(fecha, "%Y-%m-%d").date()
        except ValueError:
            return None
    return fecha

@empleado_bp.route('/dashboard')
@login_required
@role_required("EMPLEADO")
def dashboard():
    emp = current_user
    mes_actual_num = datetime.now().month

    cumpleaneros_hijos = []
    for h in Hijos.query.filter(
        Hijos.ID_Cedula == emp.ID_Cedula,
        extract('month', Hijos.Fecha_Nacimiento) == mes_actual_num
    ).all():
        cumpleaneros_hijos.append({"nombre": h.Apellidos_Nombre, "dia": h.Fecha_Nacimiento.day})

    cumpleaneros_empleados = Empleado.query.filter(
        extract('month', Empleado.Fecha_Nacimiento) == mes_actual_num,
        Empleado.Estado_Laboral == 'Activo'
    ).all()

    aniversarios = Empleado.query.filter(
        extract('month', Empleado.Fecha_Ingreso) == mes_actual_num,
        extract('year', Empleado.Fecha_Ingreso) != datetime.now().year,
        Empleado.Estado_Laboral == 'Activo'
    ).all()
    for aniv in aniversarios:
        aniv.anos_en_empresa = datetime.now().year - aniv.Fecha_Ingreso.year

    info_laboral = {
        'perfil': emp.perfil_rel.Perfil_Ocupacional if emp.perfil_rel else 'N/A',
        'area': emp.perfil_rel.area_rel.Area if emp.perfil_rel and emp.perfil_rel.area_rel else 'N/A',
        'departamento': emp.perfil_rel.area_rel.Departamento if emp.perfil_rel and emp.perfil_rel.area_rel else 'N/A'
    }

    foto_url = url_for('static', filename=f'uploads/{emp.Imagen_Perfil}') if emp.Imagen_Perfil else "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"

    return render_template('empleado/dashboard.html',
                           empleado=emp,
                           cumpleaneros_hijos=cumpleaneros_hijos,
                           cumpleaneros_empleados=cumpleaneros_empleados,
                           aniversarios=aniversarios,
                           info_laboral=info_laboral,
                           lista_eps=Eps.query.all(),
                           lista_fondos=FondoPensiones.query.all(),
                           lista_perfiles=PerfilOcupacional.query.all(),
                           foto_url=foto_url)


@empleado_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
@role_required("EMPLEADO")
def perfil():
    emp = current_user
    if request.method == 'POST':
        try:
            if request.form.get('fecha_nacimiento'):
                emp.Fecha_Nacimiento = datetime.strptime(request.form.get('fecha_nacimiento'), '%Y-%m-%d').date()
            emp.Celular = request.form.get('celular') or None
            emp.Telefono = request.form.get('telefono') or None
            emp.Correo_Electronico = request.form.get('email') or None
            emp.Contacto_Emergencia = request.form.get('contacto_emergencia') or None
            db.session.commit()
            flash('Perfil actualizado correctamente.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'danger')
        return redirect(url_for('empleado.perfil'))
    return render_template('empleado/perfil.html', empleado=emp)


@empleado_bp.route('/nomina')
@login_required
@role_required("EMPLEADO")
def nomina():
    emp = current_user
    datos = _calcular_nomina(emp.Salario_Base)
    historial = PagoNomina.query.filter_by(ID_Cedula=emp.ID_Cedula).order_by(PagoNomina.Fecha_Pago.desc()).limit(12).all()
    return render_template('empleado/nomina.html', emp=emp, historial=historial, **datos)


@empleado_bp.route('/calendario')
@login_required
@role_required("EMPLEADO")
def calendario():
    ano_actual = datetime.now().year
    eventos = []
    todos_activos = Empleado.query.filter_by(Estado_Laboral='Activo').all()
    for emp in todos_activos:
        if emp.Fecha_Nacimiento:
            try:
                fecha_nac = _normalizar_fecha(emp.Fecha_Nacimiento)
                if not fecha_nac:
                    raise ValueError
                f_cumple = fecha_nac.replace(year=ano_actual)
                eventos.append({
                    'title': f"🎂 {emp.Nombre_Completo}",
                    'start': f_cumple.strftime('%Y-%m-%d'),
                    'backgroundColor': '#ffc107', 'borderColor': '#ffc107', 'allDay': True,
                    'extendedProps': {
                        'tipo': 'cumpleanos',
                        'nombre_completo': emp.Nombre_Completo,
                        'cargo': emp.perfil_rel.Perfil_Ocupacional if emp.perfil_rel else 'N/A',
                        'area': emp.perfil_rel.area_rel.Area if emp.perfil_rel and emp.perfil_rel.area_rel else 'N/A',
                        'departamento': emp.perfil_rel.area_rel.Departamento if emp.perfil_rel and emp.perfil_rel.area_rel else 'N/A',
                        'email': emp.Correo_Electronico or ''
                    }
                })
            except ValueError:
                pass
        if emp.Fecha_Ingreso:
            try:
                fecha_ing = _normalizar_fecha(emp.Fecha_Ingreso)
                if not fecha_ing:
                    raise ValueError
                f_aniv = fecha_ing.replace(year=ano_actual)
                anos_antiguedad = ano_actual - emp.Fecha_Ingreso.year
                if anos_antiguedad > 0:
                    eventos.append({
                        'title': f"🎖️ {anos_antiguedad} Años - {emp.Nombre_Completo}",
                        'start': f_aniv.strftime('%Y-%m-%d'),
                        'backgroundColor': '#198754', 'borderColor': '#198754', 'allDay': True,
                        'extendedProps': {
                            'tipo': 'aniversario',
                            'nombre_completo': emp.Nombre_Completo,
                            'anos': anos_antiguedad,
                            'fecha_ingreso': emp.Fecha_Ingreso.strftime('%Y-%m-%d') if emp.Fecha_Ingreso else ''
                        }
                    })
            except ValueError:
                pass
    return render_template('empleado/calendario.html', eventos=eventos)


@empleado_bp.route('/subir_foto_perfil', methods=['POST'])
@login_required
@role_required("EMPLEADO")
def subir_foto_perfil():
    if 'foto' in request.files:
        f = request.files['foto']
        if f and f.filename and '.' in f.filename and f.filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}:
            filename = secure_filename(f"{current_user.ID_Cedula}_{f.filename}")
            import os
            upload_path = current_app.config['UPLOAD_FOLDER']
            path = os.path.join(upload_path, filename)
            f.save(path)
            current_user.Imagen_Perfil = filename
            db.session.commit()
            flash('Foto actualizada.', 'success')
        else:
            flash('Archivo no válido.', 'danger')
    return redirect(url_for('empleado.dashboard'))


@empleado_bp.route('/descargar_nomina_pdf')
@login_required
@role_required("EMPLEADO")
def descargar_nomina_pdf():
    if HTML is None:
        flash("Error: Componentes de sistema (GTK) faltantes para PDF.", "danger")
        return redirect(url_for('empleado.dashboard'))
    emp = current_user
    datos_nomina = _calcular_nomina(emp.Salario_Base)
    html = render_template('nomina_pdf.html', emp=emp, **datos_nomina)
    pdf = HTML(string=html).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=nomina_{emp.ID_Cedula}.pdf'
    return response
