from sqlalchemy import func, case

from .extensions import db
from .models import (
    Eps,
    FondoPensiones,
    Area,
    PerfilOcupacional,
    Profesion,
    NivelEducativo,
    Empleado,
    Departamento,
    Rol,
    PagoNomina,
)


def get_catalogos_comunes():
    """Retorna diccionarios para llenar selects en formularios."""
    return {
        "lista_eps": Eps.query.all(),
        "lista_fondos": FondoPensiones.query.all(),
        "lista_perfiles": PerfilOcupacional.query.all(),
        "lista_profesiones": Profesion.query.all(),
        "lista_niveles": NivelEducativo.query.all(),
    }


def get_superadmin_stats():
    """
    Estadísticas globales para el panel de SuperAdmin.
    No usa aún la tabla de auditoría; se añadirá después.
    """

    # Empleados por área (solo áreas que tienen al menos un perfil/empleado)
    empleados_por_area = (
        db.session.query(Area.Area, func.count(Empleado.ID_Cedula))
        .join(PerfilOcupacional, PerfilOcupacional.Area == Area.Area)
        .join(
            Empleado,
            Empleado.ID_Perfil_Ocupacional
            == PerfilOcupacional.ID_Perfil_Ocupacional,
            isouter=True,
        )
        .group_by(Area.Area)
        .all()
    )

    # Empleados por departamento
    empleados_por_depto = (
        db.session.query(Departamento.Departamento, func.count(Empleado.ID_Cedula))
        .join(Area, Area.Departamento == Departamento.Departamento)
        .join(
            PerfilOcupacional,
            PerfilOcupacional.Area == Area.Area,
        )
        .join(
            Empleado,
            Empleado.ID_Perfil_Ocupacional
            == PerfilOcupacional.ID_Perfil_Ocupacional,
            isouter=True,
        )
        .group_by(Departamento.Departamento)
        .all()
    )

    # Empleados por rol
    empleados_por_rol = (
        db.session.query(Rol.nombre_rol, func.count(Empleado.ID_Cedula))
        .join(Empleado, Empleado.id_rol == Rol.id_rol)
        .group_by(Rol.nombre_rol)
        .all()
    )

    # Nómina total y promedio (sobre todos los registros de pago_nomina)
    nomina_total, nomina_promedio = db.session.query(
        func.coalesce(func.sum(PagoNomina.Neto_Pagar), 0),
        func.coalesce(func.avg(PagoNomina.Neto_Pagar), 0),
    ).one()

    # Usuarios activos vs inactivos
    activos, inactivos = db.session.query(
        func.sum(
            case((Empleado.Estado_Laboral == "Activo", 1), else_=0)
        ),
        func.sum(
            case((Empleado.Estado_Laboral != "Activo", 1), else_=0)
        ),
    ).one()

    return {
        "empleados_por_area": empleados_por_area,
        "empleados_por_depto": empleados_por_depto,
        "empleados_por_rol": empleados_por_rol,
        "nomina_total": float(nomina_total or 0),
        "nomina_promedio": float(nomina_promedio or 0),
        "activos": int(activos or 0),
        "inactivos": int(inactivos or 0),
        "cambios_recientes": [],  # se llenará cuando integremos AuditLog
    }
