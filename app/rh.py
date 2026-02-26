from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required
from sqlalchemy import func, extract
from datetime import datetime

from .extensions import db
from .models import (
    Empleado, Rol, TipoDocumento, PerfilOcupacional,
    Area, Departamento, Eps, FondoPensiones, PagoNomina
)
from .security.permissions import role_required

try:
    from weasyprint import HTML
except (ImportError, OSError):
    HTML = None

rh_bp = Blueprint('rh', __name__, url_prefix='/rh')


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

@rh_bp.route('/dashboard')
@login_required
@role_required("RRHH")
def dashboard():
    empleados = Empleado.query.all()
    total_empleados = len(empleados)
    activos = sum(1 for e in empleados if e.Estado_Laboral == 'Activo')

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

    cumpleaneros = Empleado.query.filter(
        extract('month', Empleado.Fecha_Nacimiento) == mes_actual,
        Empleado.Estado_Laboral == 'Activo'
    ).all()

    aniversarios_query = Empleado.query.filter(
        extract('month', Empleado.Fecha_Ingreso) == mes_actual,
        Empleado.Estado_Laboral == 'Activo'
    ).all()
    aniversarios = []
    for emp in aniversarios_query:
        fecha_ing = _normalizar_fecha(emp.Fecha_Ingreso)
        if not fecha_ing:
            continue
        anos = ano_actual - fecha_ing.year
        if anos > 0:
            emp.anos_cumplidos = anos
            aniversarios.append(emp)

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
                    'backgroundColor': '#ffc107', 'borderColor': '#ffc107', 'allDay': True
                })
            except ValueError:
                pass
        if emp.Fecha_Ingreso:
            try:
                fecha_ing = _normalizar_fecha(emp.Fecha_Ingreso)
                if not fecha_ing:
                    raise ValueError
                f_aniv = fecha_ing.replace(year=ano_actual)
                anos_antiguedad = ano_actual - fecha_ing.year
                if anos_antiguedad > 0:
                    eventos.append({
                        'title': f"🎖️ {anos_antiguedad} Años - {emp.Nombre_Completo}",
                        'start': f_aniv.strftime('%Y-%m-%d'),
                        'backgroundColor': '#198754', 'borderColor': '#198754', 'allDay': True
                    })
            except ValueError:
                pass

    return render_template('rh/dashboard.html',
                          total=total_empleados, activos=activos, empleados=empleados,
                          roles=roles, tipos_doc=tipos_doc, perfiles=perfiles,
                          departamentos=departamentos, areas=areas,
                          lista_eps=lista_eps, lista_fondos=lista_fondos,
                          cumpleaneros=cumpleaneros, aniversarios=aniversarios, eventos=eventos)


@rh_bp.route('/cargos')
@login_required
@role_required("RRHH")
def gestionar_cargos():
    cargos_con_conteo = db.session.query(
        PerfilOcupacional, func.count(Empleado.ID_Cedula)
    ).outerjoin(Empleado, PerfilOcupacional.ID_Perfil_Ocupacional == Empleado.ID_Perfil_Ocupacional)\
     .group_by(PerfilOcupacional.ID_Perfil_Ocupacional).all()
    areas = Area.query.order_by(Area.Area).all()
    return render_template('rh/cargos.html', cargos_data=cargos_con_conteo, areas=areas)


@rh_bp.route('/areas')
@login_required
@role_required("RRHH")
def gestionar_areas():
    areas = Area.query.order_by(Area.Area).all()
    departamentos = Departamento.query.all()
    return render_template('rh/areas.html', areas=areas, departamentos=departamentos)


@rh_bp.route('/area/crear', methods=['POST'])
@login_required
@role_required("RRHH")
def crear_area():
    try:
        nombre_area = request.form.get('area')
        depto = request.form.get('departamento')
        if nombre_area and depto:
            if Area.query.get(nombre_area):
                flash('Ya existe un área con ese nombre.', 'danger')
            else:
                area = Area(Area=nombre_area, Departamento=depto)
                db.session.add(area)
                db.session.commit()
                flash('Área creada correctamente.', 'success')
        else:
            flash('Datos incompletos.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('rh.gestionar_areas'))


@rh_bp.route('/eventos')
@login_required
@role_required("RRHH")
def gestionar_eventos():
    return render_template('rh/eventos.html')


@rh_bp.route('/empleado/editar', methods=['POST'])
@login_required
@role_required("RRHH")
def editar_empleado():
    try:
        cedula = request.form.get('cedula')
        emp = db.session.get(Empleado, cedula)
        if not emp:
            flash('Empleado no encontrado.', 'danger')
            return redirect(url_for('rh.dashboard'))
        emp.Nombre_Completo = request.form.get('nombre') or emp.Nombre_Completo
        emp.Correo_Electronico = request.form.get('email') or emp.Correo_Electronico
        emp.ID_Perfil_Ocupacional = request.form.get('perfil') or emp.ID_Perfil_Ocupacional
        if request.form.get('salario'):
            emp.Salario_Base = request.form.get('salario')
        emp.EPS_Actual = request.form.get('eps') or emp.EPS_Actual
        emp.Fondo_Actual = request.form.get('fondo') or emp.Fondo_Actual
        db.session.commit()
        flash('Empleado actualizado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('rh.dashboard'))



@rh_bp.route("/empleado/<cedula>")
@login_required
@role_required("RRHH")
def empleado_detalle(cedula):
    emp = db.session.get(Empleado, cedula)
    if not emp:
        flash('Empleado no encontrado.', 'danger')
        return redirect(url_for('rh.dashboard'))
    
    historial_pagos = (
        PagoNomina.query.filter_by(ID_Cedula=cedula)
        .order_by(PagoNomina.Fecha_Pago.desc())
        .limit(6)
        .all()
    )
    
    # Aquí necesitarías la función _calcular_nomina, la voy a traer de routes.py
    def _calcular_nomina(salario_base):
        salario = float(salario_base) if salario_base else 0.0
        salud = salario * 0.04
        pension = salario * 0.04
        neto = salario - (salud + pension)
        aux_transporte = 0.0
        total_devengado = salario + aux_transporte
        total_deducido = salud + pension
        return {
            'salario': salario, 'salud': salud, 'pension': pension, 'neto': neto,
            'aux_transporte': aux_transporte, 'total_devengado': total_devengado, 'total_deducido': total_deducido
        }

    datos_actuales = _calcular_nomina(emp.Salario_Base)
    
    return render_template(
        "rh/empleados_detalle.html",
        empleado=emp,
        historial_pagos=historial_pagos,
        datos_actuales=datos_actuales
    )

@rh_bp.route('/cargo/crear', methods=['POST'])
@login_required
@role_required("RRHH")
def crear_cargo():
    try:
        id_perfil = request.form.get('id_perfil')
        nombre = request.form.get('perfil_ocupacional')
        area = request.form.get('area')
        if id_perfil and nombre and area:
            if PerfilOcupacional.query.get(id_perfil):
                flash('Ya existe un cargo con ese ID.', 'danger')
            else:
                cargo = PerfilOcupacional(ID_Perfil_Ocupacional=id_perfil, Perfil_Ocupacional=nombre, Area=area)
                db.session.add(cargo)
                db.session.commit()
                flash('Cargo creado correctamente.', 'success')
        else:
            flash('Datos incompletos.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('rh.gestionar_cargos'))


@rh_bp.route('/empleado/crear', methods=['POST'])
@login_required
@role_required("RRHH")
def crear_empleado():
    from werkzeug.security import generate_password_hash
    try:
        cedula = request.form.get('cedula')
        if db.session.get(Empleado, cedula):
            flash('Error: Ya existe un empleado con esa cédula.', 'danger')
            return redirect(url_for('rh.dashboard'))

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
    return redirect(url_for('rh.dashboard'))


@rh_bp.route('/reporte/empleados_activos_pdf')
@login_required
@role_required("RRHH")
def generar_reporte_activos():
    if HTML is None:
        flash("Error: WeasyPrint no disponible. Revise la instalación de GTK.", "danger")
        return redirect(url_for('rh.dashboard'))
    empleados = Empleado.query.filter_by(Estado_Laboral='Activo').all()
    fecha_generacion = datetime.now().strftime('%d/%m/%Y %H:%M')
    html = render_template('rh/reporte_activos.html', empleados=empleados, fecha=fecha_generacion)
    pdf = HTML(string=html).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=reporte_personal_activo.pdf'
    return response
