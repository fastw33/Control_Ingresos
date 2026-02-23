# app/security/security_headers.py
from typing import Callable, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Agrega cabeceras de seguridad a TODAS las respuestas.

    Ajusta la CSP según los orígenes reales de tu front:
    - 'self' permite el mismo dominio.
    - Añade tus dominios de frontend/CDN si usas assets externos.
    """

    def __init__(self, app, *, csp: Optional[str] = None, enable_hsts: bool = True) -> None:
        super().__init__(app)
        self.csp = csp or (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "upgrade-insecure-requests"
        )
        self.enable_hsts = enable_hsts

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        # Seguridad de contenido y anti-XSS
        response.headers["Content-Security-Policy"] = self.csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # COOP/COEP/CORP para aislar contexto
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # HSTS solo si la request llega por HTTPS
        if self.enable_hsts and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

        # Desactivar APIs del navegador que no usas
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), accelerometer=(), "
            "magnetometer=(), gyroscope=(), payment=()"
        )

        return response
