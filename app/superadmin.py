from flask import Blueprint, render_template
from flask_login import login_required

from .security.permissions import role_required
from .services import get_superadmin_stats


superadmin_bp = Blueprint("superadmin", __name__, url_prefix="/superadmin")


@superadmin_bp.route("/dashboard")
@login_required
@role_required("SUPERADMIN")
def dashboard():
    """
    Panel principal de SuperAdmin con estadísticas globales.
    """
    stats = get_superadmin_stats()
    return render_template("superadmin/dashboard.html", stats=stats)

