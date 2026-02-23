# app/core/errors.py
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from slowapi.errors import RateLimitExceeded  # si usas SlowAPI
from app.core.logger import logger

def problem(detail: str, status_code: int, trace_id: str, code: str):
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "detail": detail,
                "trace_id": trace_id,
            }
        },
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    trace_id = getattr(request.state, "trace_id", "-")
    # No uses exception() para 4xx normales, solo info/warn
    lvl = "warning" if 400 <= exc.status_code < 500 else "error"
    log = getattr(logger, lvl)
    log(f"[{trace_id}] HTTPException {exc.status_code} on {request.url.path}: {exc.detail}")
    return problem(exc.detail, exc.status_code, trace_id, "HTTP_ERROR")

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    trace_id = getattr(request.state, "trace_id", "-")
    logger.warning(f"[{trace_id}] ValidationError on {request.url.path}: {exc.errors()}")
    return problem("Datos inválidos en la solicitud", 422, trace_id, "VALIDATION_ERROR")

async def ratelimit_exception_handler(request: Request, exc: RateLimitExceeded):
    trace_id = getattr(request.state, "trace_id", "-")
    logger.warning(f"[{trace_id}] Rate limit exceeded on {request.url.path}")
    return problem("Demasiadas peticiones", 429, trace_id, "RATE_LIMIT")

async def generic_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", "-")
    logger.exception(f"[{trace_id}] Unhandled exception on {request.url.path}: {exc}")
    return problem("Error interno del servidor", 500, trace_id, "INTERNAL_ERROR")
