# app/security/auth.py
from fastapi import Depends, HTTPException, status, Request
from typing import Optional, Dict, Any, Tuple
import jwt  # PyJWT

from app.core.config import settings

class AuthUser(Dict[str, Any]):
    """Pequeño contenedor para datos del usuario autenticado."""

def _fail_401(detail="Unauthorized"):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

def _parse_bearer(auth_header: Optional[str]) -> Optional[str]:
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]

def _extract_uid(payload: Dict[str, Any]) -> Optional[str]:
    """
    Acepta múltiples claves de id de usuario según tu ecosistema:
    - sub
    - user_id
    - id_usuario   <-- necesario para tu token actual
    """
    for key in ("sub", "user_id", "id_usuario"):
        if payload.get(key) is not None:
            return str(payload[key])
    return None

def _validate_jwt(token: str) -> AuthUser:
    alg = getattr(settings, "jwt_alg", "HS256")
    secret = getattr(settings, "jwt_secret", None)
    if not secret:
        _fail_401("Server JWT secret not configured")

    try:
        # PyJWT valida exp por defecto (si existe).
        payload = jwt.decode(token, secret, algorithms=[alg], options={"verify_aud": False})
    except jwt.ExpiredSignatureError:
        _fail_401("Token expired")
    except jwt.InvalidTokenError as e:
        _fail_401(f"Invalid token: {e}")

    uid = _extract_uid(payload)
    if not uid:
        _fail_401("Invalid token payload: missing user id (sub/user_id/id_usuario)")

    # role opcional (si no llega, 'user'); si tu token tuviera permisos, puedes derivar aquí
    role = str(payload.get("role", "user"))
    return AuthUser({"sub": uid, "role": role, "claims": payload})

def _get_api_keys_list() -> Tuple[str, ...]:
    """
    Lee lista de API keys desde settings.api_keys_list (preferido) o settings.api_keys (string separada por comas).
    """
    if hasattr(settings, "api_keys_list") and settings.api_keys_list:
        return tuple(settings.api_keys_list)
    raw = getattr(settings, "api_keys", "")
    if isinstance(raw, str) and raw.strip():
        return tuple(x.strip() for x in raw.split(",") if x.strip())
    return tuple()

def _validate_api_key(api_key: str) -> AuthUser:
    keys = _get_api_keys_list()
    if api_key and api_key in keys:
        # Por política: API key con rol admin (ajústalo si quieres)
        return AuthUser({"sub": "api-key", "role": "admin", "claims": {"auth": "api_key"}})
    _fail_401("Invalid API key")

async def require_user(request: Request) -> AuthUser:
    # 1) API Key por cabecera (si se envía)
    api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if api_key:
        return _validate_api_key(api_key.strip())

    # 2) Bearer JWT
    # Acepta Authorization en cualquier casing (Starlette ya normaliza, pero por si acaso)
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    bearer = _parse_bearer(auth_header)
    if bearer:
        return _validate_jwt(bearer)

    _fail_401("Missing credentials")

async def require_admin(user: AuthUser = Depends(require_user)) -> AuthUser:
    role = str(user.get("role", "user")).lower()
    if role != "admin":
        _fail_401("Admin required")
    return user
