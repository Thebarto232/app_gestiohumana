from functools import wraps
from flask import abort
from flask_login import current_user


# Mapa de permisos por rol.
# SUPERADMIN siempre tendrá todos los permisos, aunque no se liste aquí.
ROLE_PERMISSIONS = {
    "SUPERADMIN": {
        "dashboard_admin",
        "employee_manage",
        "org_manage",
        "payroll_view_all",
        "payroll_generate",
        "audit_view",
        "roles_manage",
    },
    "ADMIN": {
        "dashboard_admin",
        "employee_manage",
        "org_manage",
        "payroll_view_all",
        "payroll_generate",
    },
    "RRHH": {
        "dashboard_admin",
        "employee_manage",
        "org_manage",
        "payroll_view_all",
        "payroll_generate",
    },
    "EMPLEADO": {
        "dashboard_employee",
        "payroll_view_self",
        "profile_edit_self",
    },
}


def _current_role_name():
    """Obtiene el nombre del rol actual del usuario logueado."""
    rol_rel = getattr(current_user, "rol_rel", None)
    return getattr(rol_rel, "nombre_rol", None)


def has_permission(permission: str) -> bool:
    """Devuelve True si el usuario tiene el permiso indicado."""
    if not current_user.is_authenticated:
        return False

    role = _current_role_name()
    if role == "SUPERADMIN":
        # SUPERADMIN tiene todos los permisos.
        return True

    return permission in ROLE_PERMISSIONS.get(role, set())


def permission_required(permission: str):
    """Decorador para proteger una vista por permiso lógico."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or not has_permission(permission):
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def role_required(*roles):
    """
    Decorador para restringir acceso por roles.
    SUPERADMIN siempre pasa sin importar la lista de roles.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)

            role = _current_role_name()
            if role == "SUPERADMIN":
                return fn(*args, **kwargs)

            if role not in roles:
                abort(403)

            return fn(*args, **kwargs)

        return wrapper

    return decorator

