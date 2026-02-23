from fastapi import FastAPI, HTTPException, APIRouter, Depends
from fastapi.exceptions import RequestValidationError

from app.core.db import Base, engine
import app.models  # noqa: F401  ← importa todos los modelos

# ─── Routers existentes ──────────────────────────────────────────────
from app.personal.controller import router as personal_router
from app.vectores.controller import router as vectores_router
from app.marcacion.controller import router as marcacion_router
from app.solicitud.controller import router as solicitudes_router
from app.uploads.controller import router as upload_router  # ✅ nuevo router seguro

# ─── Seguridad / Logging / Rate limit ────────────────────────────────
from app.core.logger import setup_std_logging, request_logger_middleware, logger
from app.core.errors import (
    http_exception_handler,
    validation_exception_handler,
    ratelimit_exception_handler,
    generic_exception_handler,
)
from app.security.cors import setup_cors
from app.security.security_headers import SecurityHeadersMiddleware
from app.security.rate_limit import mount_rate_limit
from slowapi.errors import RateLimitExceeded

# 👮 Auth
from app.security.auth import require_user

# --------------------------------------------------------------------------
# App base
# --------------------------------------------------------------------------
app = FastAPI(title="Control Ingresos API")

# 1️⃣ Logging
setup_std_logging()
app.middleware("http")(request_logger_middleware)

# 2️⃣ Seguridad
setup_cors(app)
app.add_middleware(SecurityHeadersMiddleware)
mount_rate_limit(app)

# 3️⃣ Handlers globales
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(RateLimitExceeded, ratelimit_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# --------------------------------------------------------------------------
# Smoke check (módulos + DB)
# --------------------------------------------------------------------------
import importlib
import traceback
from typing import Optional, Tuple
from sqlalchemy import text

MODULES_TO_CHECK = [
    "app.core.db",
    "app.models",
    "app.core.logger",
    "app.core.errors",
    "app.security.cors",
    "app.security.security_headers",
    "app.security.rate_limit",
    "app.personal.controller",
    "app.vectores.controller",
    "app.marcacion.controller",
    "app.solicitud.controller",
    "app.uploads.controller",
]

def _import_ok(name: str) -> Tuple[bool, Optional[str]]:
    try:
        importlib.import_module(name)
        return True, None
    except Exception as e:
        return False, "".join(traceback.format_exception_only(type(e), e)).strip()

def _db_ok() -> Tuple[bool, Optional[str]]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        return False, f"DB error: {e}"

@app.on_event("startup")
def startup_smoke_check() -> None:
    logger.info("▶️ Startup smoke check: módulos y base de datos")
    all_ok = True

    for m in MODULES_TO_CHECK:
        ok, err = _import_ok(m)
        if ok:
            logger.info(f"✅ import {m}")
        else:
            logger.error(f"❌ import {m}: {err}")
            all_ok = False

    ok_db, err_db = _db_ok()
    if ok_db:
        logger.info("✅ DB ping OK (SELECT 1)")
    else:
        logger.error(f"❌ DB ping FAIL: {err_db}")
        all_ok = False

    if all_ok:
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Tablas verificadas/creadas (SQLAlchemy)")
        except Exception as e:
            logger.error(f"❌ Error creando/verificando tablas: {e}")
            all_ok = False

    if not all_ok:
        raise RuntimeError("Startup smoke check falló; revisa los logs anteriores.")

# --------------------------------------------------------------------------
# Endpoint de diagnóstico
# --------------------------------------------------------------------------
diag_router = APIRouter(prefix="/diag", tags=["diagnostics"])

@diag_router.get("/smoke")
def smoke_endpoint():
    results = []
    all_ok = True
    for m in MODULES_TO_CHECK:
        ok, err = _import_ok(m)
        results.append({"module": m, "ok": ok, "error": err})
        all_ok &= ok
    ok_db, err_db = _db_ok()
    return {
        "ok": all_ok and ok_db,
        "db_ok": ok_db,
        "db_error": err_db,
        "results": results,
    }

app.include_router(diag_router)

# --------------------------------------------------------------------------
# Health y rutas protegidas
# --------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"ok": True}

# 🔐 Todos estos requieren credenciales válidas
app.include_router(personal_router,    prefix="/app", dependencies=[Depends(require_user)])
app.include_router(vectores_router,    prefix="/app", dependencies=[Depends(require_user)])
app.include_router(marcacion_router,   prefix="/app", dependencies=[Depends(require_user)])
app.include_router(solicitudes_router, prefix="/app", dependencies=[Depends(require_user)])
app.include_router(upload_router)  # ✅ ruta segura para archivos /upload/**
