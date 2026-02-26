from flask import Blueprint, render_template, abort, request, redirect, url_for, flash, make_response, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date
from sqlalchemy import extract, func

from .extensions import db
from .models import (
    Empleado, Rol, TipoDocumento, PerfilOcupacional,
    Area, Departamento, Eps, FondoPensiones, Hijos, PagoNomina
)
from .security.permissions import role_required

try:
    from weasyprint import HTML
except (ImportError, OSError):
    HTML = None

admin_bp = Blueprint('admin', __name__)
main_bp = Blueprint('main', __name__)


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
    """
    Asegura que trabajamos con objetos date.
    En la base pueden venir como date o como string 'YYYY-MM-DD'.
    """
    if not fecha:
        return None
    if isinstance(fecha, date):
        return fecha
    if isinstance(fecha, str):
        try:
            return datetime.strptime(fecha, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


# ---------- MAIN (empleados) ----------

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    # SUPERADMIN, ADMIN y RRHH se envían al dashboard administrativo
    if current_user.rol_rel and current_user.rol_rel.nombre_rol in ['SUPERADMIN', 'ADMIN', 'RRHH']:
        return redirect(url_for('admin.dashboard'))

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


@main_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
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
        return redirect(url_for('main.perfil'))
    return render_template('perfil.html', empleado=emp)


@main_bp.route('/nomina')
@login_required
def nomina():
    emp = current_user
    datos = _calcular_nomina(emp.Salario_Base)
    historial = PagoNomina.query.filter_by(ID_Cedula=emp.ID_Cedula).order_by(PagoNomina.Fecha_Pago.desc()).limit(12).all()
    return render_template('nomina.html', emp=emp, historial=historial, **datos)


@main_bp.route('/calendario')
@login_required
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
    return render_template('calendario.html', eventos=eventos)


@main_bp.route('/subir_foto_perfil', methods=['POST'])
@login_required
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
    return redirect(url_for('main.dashboard'))


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


@main_bp.route('/generar_nomina', methods=['POST'])
@login_required
def generar_nomina():
    emp = current_user
    datos = _calcular_nomina(emp.Salario_Base)
    hoy = datetime.now().date()
    mes_nom = hoy.strftime('%B')
    ano = hoy.year
    pago = PagoNomina(
        ID_Cedula=emp.ID_Cedula,
        Fecha_Pago=hoy,
        Mes=mes_nom, Ano=ano,
        Salario_Base=datos['salario'],
        Aux_Transporte=datos['aux_transporte'],
        Deducciones_Salud=datos['salud'],
        Deducciones_Pension=datos['pension'],
        Total_Devengado=datos['total_devengado'],
        Total_Deducido=datos['total_deducido'],
        Neto_Pagar=datos['neto'],
        Estado='Pagado'
    )
    db.session.add(pago)
    db.session.commit()
    flash('Pago del mes registrado correctamente.', 'success')
    return redirect(url_for('main.nomina'))


# ---------- ADMIN ----------

@admin_bp.route('/dashboard')
@login_required
@role_required("ADMIN", "RRHH")
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

    return render_template('admin/dashboard.html',
                          total=total_empleados, activos=activos, empleados=empleados,
                          roles=roles, tipos_doc=tipos_doc, perfiles=perfiles,
                          departamentos=departamentos, areas=areas,
                          lista_eps=lista_eps, lista_fondos=lista_fondos,
                          cumpleaneros=cumpleaneros, aniversarios=aniversarios, eventos=eventos)


@admin_bp.route('/cargos')
@login_required
@role_required("ADMIN", "RRHH")
def gestionar_cargos():
    cargos_con_conteo = db.session.query(
        PerfilOcupacional, func.count(Empleado.ID_Cedula)
    ).outerjoin(Empleado, PerfilOcupacional.ID_Perfil_Ocupacional == Empleado.ID_Perfil_Ocupacional)\
     .group_by(PerfilOcupacional.ID_Perfil_Ocupacional).all()
    areas = Area.query.order_by(Area.Area).all()
    return render_template('admin/cargos.html', cargos_data=cargos_con_conteo, areas=areas)


@admin_bp.route('/areas')
@login_required
@role_required("ADMIN", "RRHH")
def gestionar_areas():
    areas = Area.query.order_by(Area.Area).all()
    departamentos = Departamento.query.all()
    return render_template('admin/areas.html', areas=areas, departamentos=departamentos)


@admin_bp.route('/area/crear', methods=['POST'])
@login_required
@role_required("ADMIN", "RRHH")
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
    return redirect(url_for('admin.gestionar_areas'))


@admin_bp.route('/eventos')
@login_required
@role_required("ADMIN", "RRHH")
def gestionar_eventos():
    return render_template('admin/eventos.html')


@admin_bp.route('/empleado/editar', methods=['POST'])
@login_required
@role_required("ADMIN", "RRHH")
def editar_empleado():
    try:
        cedula = request.form.get('cedula')
        emp = db.session.get(Empleado, cedula)
        if not emp:
            flash('Empleado no encontrado.', 'danger')
            return redirect(url_for('admin.dashboard'))
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
    return redirect(url_for('admin.dashboard'))



@admin_bp.route("/empleado/<cedula>")
@login_required
@role_required("ADMIN", "RRHH")
def empleado_detalle(cedula):
    # Buscamos al empleado por su Cédula (tu Primary Key)
    emp = db.session.get(Empleado, cedula)
    if not emp:
        flash('Empleado no encontrado.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    # Obtenemos los últimos 6 meses de pagos reales de la tabla PagoNomina
    historial_pagos = (
        PagoNomina.query.filter_by(ID_Cedula=cedula)
        .order_by(PagoNomina.Fecha_Pago.desc())
        .limit(6)
        .all()
    )
    
    # Calculamos la proyección de la nómina actual usando tu función existente
    datos_actuales = _calcular_nomina(emp.Salario_Base)
    
    return render_template(
        "admin/empleados_detalle.html", # Asegúrate de que el nombre coincida con tu carpeta templates/admin/
        empleado=emp,
        historial_pagos=historial_pagos,
        datos_actuales=datos_actuales
    )

@admin_bp.route('/cargo/crear', methods=['POST'])
@login_required
@role_required("ADMIN", "RRHH")
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
    return redirect(url_for('admin.gestionar_cargos'))


@admin_bp.route('/empleado/crear', methods=['POST'])
@login_required
@role_required("ADMIN", "RRHH")
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
@role_required("ADMIN", "RRHH")
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
