# app/core/files.py
import hashlib
import os
import re
import uuid
from .config import settings

_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")

def secure_filename(name: str) -> str:
    base = os.path.basename(name or "")
    base = _SAFE_RE.sub("_", base)
    return (base[:200] or str(uuid.uuid4()))

def ensure_storage_dir() -> None:
    os.makedirs(settings.storage_dir, exist_ok=True)

def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()
