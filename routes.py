from flask import Blueprint, render_template, abort, request, redirect, url_for, flash, make_response, jsonify
from flask_login import login_required, current_user
from functools import wraps
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from sqlalchemy import extract, func, and_, or_

# 1. CORRECCIÓN DE IMPORTACIONES
# Importamos desde las rutas absolutas del paquete 'app'
from extensions import db
from models import (Empleado, Rol, TipoDocumento, PerfilOcupacional, 
                        Area, Departamento, Eps, FondoPensiones, Hijos)

try:
    from weasyprint import HTML
except (ImportError, OSError):
    HTML = None

admin_bp = Blueprint('admin', __name__)
main_bp = Blueprint('main', __name__)

# Decorador de seguridad
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificamos el rol a través de la relación
        if not current_user.rol_rel or current_user.rol_rel.nombre_rol not in ['ADMIN', 'RRHH']:
            abort(403) 
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.rol_rel and current_user.rol_rel.nombre_rol in ['ADMIN', 'RRHH']:
        return redirect(url_for('admin.dashboard'))

    emp = current_user
    mes_actual_num = datetime.now().month

    # Lógica de cumpleañeros
    cumpleaneros_hijos = []
    cumpleaneros_hijos_query = Hijos.query.filter(
        Hijos.ID_Cedula == emp.ID_Cedula, 
        extract('month', Hijos.Fecha_Nacimiento) == mes_actual_num
    ).all()
    
    for h in cumpleaneros_hijos_query:
        cumpleaneros_hijos.append({"nombre": h.Apellidos_Nombre, "dia": h.Fecha_Nacimiento.day})

    cumpleaneros_empleados = Empleado.query.filter(
        extract('month', Empleado.Fecha_Nacimiento) == mes_actual_num,
        Empleado.Estado_Laboral == 'Activo'
    ).all()

    # Lógica de aniversarios
    aniversarios = Empleado.query.filter(
        extract('month', Empleado.Fecha_Ingreso) == mes_actual_num,
        extract('year', Empleado.Fecha_Ingreso) != datetime.now().year,
        Empleado.Estado_Laboral == 'Activo'
    ).all()

    for aniv in aniversarios:
        aniv.anos_en_empresa = datetime.now().year - aniv.Fecha_Ingreso.year

    # Datos para la vista
    info_laboral = {
        'perfil': emp.perfil_rel.Perfil_Ocupacional if emp.perfil_rel else 'N/A',
        'area': emp.perfil_rel.area_rel.Area if emp.perfil_rel and emp.perfil_rel.area_rel else 'N/A',
        'departamento': emp.perfil_rel.area_rel.Departamento if emp.perfil_rel and emp.perfil_rel.area_rel else 'N/A'
    }

    foto_url = url_for('static', filename=f'uploads/{emp.Imagen_Perfil}') if emp.Imagen_Perfil else "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"

    return render_template('dashboard.html', 
                           empleado=emp, 
                           cumpleaneros_hijos=cumpleaneros_hijos,
                           cumpleaneros_empleados=cumpleaneros_empleados,
                           aniversarios=aniversarios,
                           info_laboral=info_laboral,
                           lista_eps=Eps.query.all(),
                           lista_fondos=FondoPensiones.query.all(),
                           lista_perfiles=PerfilOcupacional.query.all(),
                           foto_url=foto_url)

@main_bp.route('/descargar_nomina_pdf')
@login_required
def descargar_nomina_pdf():
    if HTML is None:
        flash("Error: Componentes de sistema (GTK) faltantes para PDF.", "danger")
        return redirect(url_for('main.dashboard'))
    
    emp = current_user
    datos_nomina = _calcular_nomina(emp.Salario_Base)
    html = render_template('nomina_pdf.html', emp=emp, **datos_nomina)
    
    pdf = HTML(string=html).write_pdf()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=nomina_{emp.ID_Cedula}.pdf'
    return response

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    # Usamos db.session.query o Model.query indistintamente
    empleados = Empleado.query.all()
    total_empleados = len(empleados)
    activos = sum(1 for e in empleados if e.Estado_Laboral == 'Activo')
    
    # Datos para los selectores en los modales
    roles = Rol.query.all()
    tipos_doc = TipoDocumento.query.all()
    perfiles = PerfilOcupacional.query.all()
    departamentos = Departamento.query.all()
    areas = Area.query.all()
    lista_eps = Eps.query.all()
    lista_fondos = FondoPensiones.query.all()

    hoy = datetime.now()
    mes_actual = hoy.month
    ano_actual = hoy.year

    # 1. Cumpleaños del Mes
    cumpleaneros = Empleado.query.filter(
        extract('month', Empleado.Fecha_Nacimiento) == mes_actual,
        Empleado.Estado_Laboral == 'Activo'
    ).all()

    # 2. Aniversarios del Mes
    aniversarios_query = Empleado.query.filter(
        extract('month', Empleado.Fecha_Ingreso) == mes_actual,
        Empleado.Estado_Laboral == 'Activo'
    ).all()
    
    aniversarios = []
    for emp in aniversarios_query:
        anos = ano_actual - emp.Fecha_Ingreso.year
        if anos > 0:
            emp.anos_cumplidos = anos 
            aniversarios.append(emp)

    # 3. Eventos para el Calendario
    eventos = []
    todos_activos = Empleado.query.filter_by(Estado_Laboral='Activo').all()
    
    for emp in todos_activos:
        if emp.Fecha_Nacimiento:
            try:
                f_cumple = emp.Fecha_Nacimiento.replace(year=ano_actual)
                eventos.append({
                    'title': f"🎂 {emp.Nombre_Completo}",
                    'start': f_cumple.strftime('%Y-%m-%d'),
                    'backgroundColor': '#ffc107',
                    'borderColor': '#ffc107',
                    'allDay': True
                })
            except ValueError: pass 
        
        if emp.Fecha_Ingreso:
            try:
                f_aniv = emp.Fecha_Ingreso.replace(year=ano_actual)
                anos_antiguedad = ano_actual - emp.Fecha_Ingreso.year
                if anos_antiguedad > 0:
                    eventos.append({
                        'title': f"🎖️ {anos_antiguedad} Años - {emp.Nombre_Completo}",
                        'start': f_aniv.strftime('%Y-%m-%d'),
                        'backgroundColor': '#198754',
                        'borderColor': '#198754',
                        'allDay': True
                    })
            except ValueError: pass
    
    return render_template('admin/dashboard.html', 
                            total=total_empleados, 
                            activos=activos,
                            empleados=empleados,
                            roles=roles,
                            tipos_doc=tipos_doc,
                            perfiles=perfiles,
                            departamentos=departamentos,
                            areas=areas,
                            lista_eps=lista_eps,
                            lista_fondos=lista_fondos,
                            cumpleaneros=cumpleaneros,
                            aniversarios=aniversarios,
                            eventos=eventos)

@admin_bp.route('/cargos')
@login_required
@admin_required
def gestionar_cargos():
    cargos_con_conteo = db.session.query(
        PerfilOcupacional, func.count(Empleado.ID_Cedula)
    ).outerjoin(Empleado, PerfilOcupacional.ID_Perfil_Ocupacional == Empleado.ID_Perfil_Ocupacional)\
     .group_by(PerfilOcupacional.ID_Perfil_Ocupacional)\
     .all()

    areas = Area.query.order_by(Area.Area).all()
    return render_template('admin/cargos.html', cargos_data=cargos_con_conteo, areas=areas)

@admin_bp.route('/empleado/crear', methods=['POST'])
@login_required
@admin_required
def crear_empleado():
    try:
        cedula = request.form.get('cedula')
        if db.session.get(Empleado, cedula):
            flash('Error: Ya existe un empleado con esa cédula.', 'danger')
            return redirect(url_for('admin.dashboard'))

        nuevo_emp = Empleado(
            ID_Cedula=cedula,
            Nombre_Completo=request.form.get('nombre'),
            Correo_Electronico=request.form.get('email'),
            Contrasena=generate_password_hash(request.form.get('password')),
            id_rol=request.form.get('rol'),
            id_tipodocuemnto=request.form.get('tipo_doc'),
            ID_Perfil_Ocupacional=request.form.get('perfil'),
            Fecha_Ingreso=datetime.strptime(request.form.get('fecha_ingreso'), '%Y-%m-%d').date(),
            Salario_Base=request.form.get('salario', 0),
            EPS_Actual=request.form.get('eps'),
            Fondo_Actual=request.form.get('fondo'),
            Estado_Laboral='Activo'
        )
        db.session.add(nuevo_emp)
        db.session.commit()
        flash('Empleado creado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear empleado: {str(e)}', 'danger')
    
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/reporte/empleados_activos_pdf')
@login_required
@admin_required
def generar_reporte_activos():
    if HTML is None:
        flash("Error: WeasyPrint no disponible. Revise la instalación de GTK.", "danger")
        return redirect(url_for('admin.dashboard'))

    empleados = Empleado.query.filter_by(Estado_Laboral='Activo').all()
    fecha_generacion = datetime.now().strftime('%d/%m/%Y %H:%M')

    html = render_template('admin/reporte_activos.html', empleados=empleados, fecha=fecha_generacion)
    pdf = HTML(string=html).write_pdf()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=reporte_personal_activo.pdf'
    return response

def _calcular_nomina(salario_base):
    salario = float(salario_base) if salario_base else 0.0
    salud = salario * 0.04
    pension = salario * 0.04
    # Simplificado para el ejemplo
    return {'salario': salario, 'salud': salud, 'pension': pension, 'neto': salario - (salud + pension)}

# ... (El resto de rutas siguen el mismo patrón de usar db.session)