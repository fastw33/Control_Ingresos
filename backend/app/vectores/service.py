# app/vectores/service.py
from typing import Optional, List
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import numpy as np

from . import repository
from .schema import (
    VectoresCreate,
    VectoresUpdate,
    VectoresMetaOut,
    VerificacionOut,
)
from .model import PersonalVectores
from .Encoder import embedding_from_image_bytes 

UMBRAL_COSENO = 0.33


# Import tardío de Personal para evitar conflictos de mapper con Marcacion
def _personal_existe(db: Session, personal_id: int) -> bool:
    from ..personal.model import Personal  # <- relativo a 'app.personal'
    return db.get(Personal, personal_id) is not None


# ---------------- CRUD JSON ----------------
def crear_o_reemplazar(db: Session, payload: VectoresCreate) -> PersonalVectores:
    if not _personal_existe(db, payload.personal_id):
        raise HTTPException(status_code=404, detail="Personal no existe")

    data = {
        "id_personal": payload.personal_id,
        "vector1": payload.vector1,
        "vector2": payload.vector2,
        "vector3": payload.vector3,
        "vector4": payload.vector4,
        "vector5": payload.vector5,
    }
    existente = repository.get_by_personal(db, payload.personal_id)
    return repository.update(db, existente, data) if existente else repository.create(db, data)


def actualizar(db: Session, personal_id: int, payload: VectoresUpdate) -> Optional[PersonalVectores]:
    if not _personal_existe(db, personal_id):
        raise HTTPException(status_code=404, detail="Personal no existe")
    obj = repository.get_by_personal(db, personal_id)
    if not obj:
        return None
    data = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    return repository.update(db, obj, data) if data else obj


def obtener_por_personal(db: Session, personal_id: int) -> Optional[PersonalVectores]:
    return repository.get_by_personal(db, personal_id)


def eliminar_por_personal(db: Session, personal_id: int) -> int:
    return repository.delete_by_personal(db, personal_id)


# ---------------- Helpers IMAGEN ----------------
def _embedding_from_upload(file: UploadFile) -> Optional[np.ndarray]:
    """
    Carga la imagen desde UploadFile y devuelve un embedding float32 (shape (512,))
    del rostro principal usando InsightFace. Devuelve None si no detecta rostro.
    """
    # Asegura puntero al inicio
    try:
        file.file.seek(0)
    except Exception:
        pass

    try:
        image_bytes: bytes = file.file.read()
    except Exception:
        try:
            file.file.seek(0)
            image_bytes = file.file.read()
        except Exception:
            return None
    finally:
        try:
            file.file.seek(0)
        except Exception:
            pass

    vec = embedding_from_image_bytes(image_bytes)
    if vec is None:
        return None
    # Normalizamos por seguridad (InsightFace ya entrega norm≈1)
    n = np.linalg.norm(vec)
    if n > 0:
        vec = (vec / n).astype("float32")
    else:
        vec = vec.astype("float32")
    return vec


def _ensure_five_vectors(vectors: List[bytes]) -> List[bytes]:
    if not vectors:
        raise ValueError("No se detectó rostro en las imágenes enviadas.")
    out = vectors[:5]
    while len(out) < 5:
        out.append(out[-1])
    return out


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Similitud coseno entre dos embeddings."""
    na = a / (np.linalg.norm(a) + 1e-12)
    nb = b / (np.linalg.norm(b) + 1e-12)
    return float(np.dot(na, nb))


# ---------------- Crear/Reemplazar desde IMÁGENES (multipart) ----------------
def crear_o_reemplazar_from_images(db: Session, personal_id: int, files: List[UploadFile]) -> PersonalVectores:
    if not _personal_existe(db, personal_id):
        raise HTTPException(status_code=404, detail="Personal no existe")
    if not files:
        raise HTTPException(status_code=400, detail="Debes enviar al menos 1 imagen.")

    vectors: List[bytes] = []
    total = 0
    sin_rostro = 0

    for f in files:
        total += 1
        enc = _embedding_from_upload(f)  # <- InsightFace 512D
        if enc is not None:
            vectors.append(enc.tobytes())
        else:
            sin_rostro += 1
        if len(vectors) == 5:
            break

    if not vectors:
        raise HTTPException(
            status_code=400,
            detail=f"No se detectó rostro en las imágenes enviadas. Imágenes sin rostro: {sin_rostro}/{total}",
        )

    vectors = _ensure_five_vectors(vectors)

    data = {
        "id_personal": personal_id,
        "vector1": vectors[0],
        "vector2": vectors[1],
        "vector3": vectors[2],
        "vector4": vectors[3],
        "vector5": vectors[4],
    }

    existente = repository.get_by_personal(db, personal_id)
    return repository.update(db, existente, data) if existente else repository.create(db, data)


# ---------------- Verificación (comparar, SIN registrar marcación) ----------------
def verificar_imagen(
    db: Session,
    personal_id: int,
    file: UploadFile,
    tipo: Optional[str] = None,   # se ignora aquí; la marcación real es en app/marcacion
    umbral: float = UMBRAL_COSENO
) -> VerificacionOut:
    """
    Compara la imagen enviada contra los 5 embeddings guardados del personal usando
    SIMILITUD COSENO. 'umbral' es el mínimo cosine similarity para considerar MATCH.
    """
    if not _personal_existe(db, personal_id):
        raise HTTPException(status_code=404, detail="Personal no existe")

    pv = repository.get_by_personal(db, personal_id)
    if not pv:
        raise HTTPException(status_code=404, detail="Este personal no tiene vectores registrados")

    query_vec = _embedding_from_upload(file)  # <- InsightFace 512D
    if query_vec is None:
        raise HTTPException(status_code=400, detail="No se detectó rostro en la imagen")

    # Reconstruir 5 vectores guardados (float32)
    stored_raw = [
        np.frombuffer(pv.vector1, dtype=np.float32),
        np.frombuffer(pv.vector2, dtype=np.float32),
        np.frombuffer(pv.vector3, dtype=np.float32),
        np.frombuffer(pv.vector4, dtype=np.float32),
        np.frombuffer(pv.vector5, dtype=np.float32),
    ]

    # Seguridad: comprobar que los tamaños coinciden (migración 128D -> 512D)
    dim_q = int(query_vec.size)
    dims_stored = [int(v.size) for v in stored_raw]
    if any(d != dim_q for d in dims_stored):
        raise HTTPException(
            status_code=409,
            detail=(
                "Los vectores almacenados no son compatibles con el motor actual (dimensiones distintas). "
                "Re registra los vectores de este personal para completar la migración a InsightFace."
            ),
        )

    # Normalizamos por seguridad (InsightFace suele dar norma≈1)
    stored = []
    for v in stored_raw:
        n = np.linalg.norm(v)
        stored.append((v / (n + 1e-12)).astype(np.float32))

    q = (query_vec / (np.linalg.norm(query_vec) + 1e-12)).astype(np.float32)

    # SIMILITUD COSENO (cuanto más alto, mejor). Rango típico [0..1].
    sims = [_cosine_sim(v, q) for v in stored]
    best_idx = int(np.argmax(sims)) if sims else -1
    best_sim = float(sims[best_idx]) if sims else -1.0

    is_match = (best_sim >= float(umbral))

    # 'score' legible para UI: la propia similitud (acotada a [0..1])
    score = max(0.0, min(1.0, best_sim))

    return VerificacionOut(
        match=is_match,
        score=score,             # similitud coseno (0..1 aprox.)
        umbral=float(umbral),    # se aplica sobre similitud (>= umbral => match)
        mejor_vector=best_idx + 1 if best_idx >= 0 else 0,
        mensaje="ok" if is_match else "no match",
    )
