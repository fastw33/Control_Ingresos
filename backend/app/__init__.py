# app/__init__.py
# Registrar modelos (side-effect imports)
from app.personal.model import Personal
from app.vectores.model import PersonalVectores

# (Opcional) Exponer routers si los tienes
from app.personal.controller import router as personal_router
from app.vectores.controller import router as vectores_router

__all__ = [
    "Personal",
    "PersonalVectores",
    "personal_router",
    "vectores_router",
]
