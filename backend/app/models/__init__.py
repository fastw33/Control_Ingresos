# app/models/__init__.py
# Importa y expone todos los modelos para que SQLAlchemy los registre
from app.personal.model import Personal
from app.vectores.model import PersonalVectores
from app.marcacion.model import Marcacion
from app.solicitud.model import SolicitudPermiso

__all__ = [
    "Personal",
    "PersonalVectores",
    "Marcacion",
    "SolicitudPermiso",
]
