# app/security/rate_limit.py
from typing import Optional, List
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

# Limiter global
limiter = Limiter(key_func=get_remote_address, default_limits=[])

def rate_limit_exceeded_handler(request, exc):
    """Manejador personalizado para error 429"""
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT",
                "detail": "Demasiadas peticiones. Intente nuevamente más tarde.",
            }
        },
    )

def mount_rate_limit(app, default_limits: Optional[List[str]] = None) -> None:
    """
    Monta SlowAPI en la app y registra el handler 429.
    """
    if default_limits:
        limiter._default_limits = default_limits

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

# Alias opcional
init_rate_limit = mount_rate_limit

__all__ = ["limiter", "mount_rate_limit", "init_rate_limit"]
