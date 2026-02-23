# app/uploads/controller.py
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path, PurePosixPath
import mimetypes, os
from app.security.auth import require_user
from app.core.logger import logger

router = APIRouter(prefix="/upload", tags=["upload"])

BASE_DIR = (Path(__file__).resolve().parents[2] / "upload").resolve()

def _sanitize_rel(relpath: str) -> str:

    if not relpath:
        return ""
    s = relpath.replace("\\", "/").lstrip("/")     # "\upload\..." → "upload/..."
    s_low = s.lower()
    if s_low.startswith("upload/"):
        s = s[7:]                                   # quita 'upload/'
    elif s_low.startswith("app/upload/"):
        s = s[11:]                                  # si te llegara así, también lo limpia
    return str(PurePosixPath(s))                    # colapsa //, ., ..

def _safe_join(relpath: str) -> Path:
    sanitized = _sanitize_rel(relpath)
    if sanitized in ("", ".", "/"):
        raise HTTPException(status_code=404, detail="Not found")
    candidate = (BASE_DIR / sanitized).resolve()
    # bloqueo traversal
    if not str(candidate).startswith(str(BASE_DIR)):
        raise HTTPException(status_code=404, detail="Not found")
    return candidate

# Diagnóstico opcional
@router.get("/_diag/resolve")
def diag_resolve(relpath: str = Query(...), user=Depends(require_user)):
    p = _safe_join(relpath)
    exists = p.exists()
    is_file = p.is_file() if exists else False
    size = p.stat().st_size if is_file else None
    mime, _ = mimetypes.guess_type(str(p))
    return {
        "input_relpath": relpath,
        "normalized_rel": _sanitize_rel(relpath),
        "BASE_DIR": str(BASE_DIR),
        "resolved_path": str(p),
        "exists": exists,
        "is_file": is_file,
        "size": size,
        "guessed_mime": mime,
    }

@router.head("/{relpath:path}")
def head_upload(relpath: str, user=Depends(require_user)):
    p = _safe_join(relpath)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    mime, _ = mimetypes.guess_type(str(p))
    return JSONResponse(
        content=None,
        headers={
            "Content-Type": mime or "application/octet-stream",
            "Cache-Control": "private, max-age=0, no-store",
            "Content-Disposition": "inline",
            "Access-Control-Expose-Headers": "Content-Disposition, Content-Type",
        },
    )

@router.get("/{relpath:path}")
def get_upload(relpath: str, request: Request, user=Depends(require_user)):
    p = _safe_join(relpath)
    if not p.exists() or not p.is_file():
        logger.info(f"[UPLOAD] 404 rel={relpath} -> {p}")
        raise HTTPException(status_code=404, detail="Not found")
    mime, _ = mimetypes.guess_type(str(p))
    logger.info(f"[UPLOAD] 200 rel={relpath} -> {p.name} mime={mime}")
    return FileResponse(
        path=str(p),
        media_type=mime or "application/octet-stream",
        headers={
            "Cache-Control": "private, max-age=0, no-store",
            "Content-Disposition": "inline",
            "Access-Control-Expose-Headers": "Content-Disposition, Content-Type",
        },
    )
