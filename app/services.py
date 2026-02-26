from .models import Eps, FondoPensiones, Area, PerfilOcupacional, Profesion, NivelEducativo

def get_catalogos_comunes():
    """Retorna diccionarios para llenar selects en formularios"""
    return {
        'lista_eps': Eps.query.all(),
        'lista_fondos': FondoPensiones.query.all(),
        'lista_perfiles': PerfilOcupacional.query.all(),
        'lista_profesiones': Profesion.query.all(),
        'lista_niveles': NivelEducativo.query.all()
    }