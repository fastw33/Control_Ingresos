# backend/passenger_wsgi.py
import os, sys

# Rutas para que se pueda importar "app"
ROOT = os.path.dirname(__file__)
APP_DIR = os.path.join(ROOT, "app")
for p in (ROOT, APP_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

# .env opcional
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except Exception:
    pass

# Importa tu FastAPI app
from app.main import app as fastapi_app

# Adaptador ASGI->WSGI
# Preferimos asgiref si lo trae, si no, usamos a2wsgi
Adapter = None
try:
    # Algunos builds exponen "AsgiToWsgi"
    from asgiref.wsgi import AsgiToWsgi as Adapter  # type: ignore
except Exception:
    try:
        # Otros builds antiguos: "ASGItoWSGI"
        from asgiref.wsgi import ASGItoWSGI as Adapter  # type: ignore
    except Exception:
        # El camino seguro y mantenido:
        from a2wsgi import ASGItoWSGI as Adapter  # type: ignore

# Objeto WSGI que espera Passenger
application = Adapter(fastapi_app)
