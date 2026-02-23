# app/vectores/encoder.py
from typing import Optional
import io
import numpy as np
from PIL import Image, ImageOps
import cv2


from insightface.app import FaceAnalysis

_APP: Optional[FaceAnalysis] = None

def _get_app() -> FaceAnalysis:
    """
    Inicializa y devuelve una instancia singleton de FaceAnalysis.
    Usa el modelo por defecto 'buffalo_l' (512D, normalizado).
    """
    global _APP
    if _APP is None:
        _APP = FaceAnalysis(name="buffalo_l")
        # ctx_id=0 -> CPU; det_size ajusta la resolución del detector
        _APP.prepare(ctx_id=0, det_size=(640, 640))
    return _APP


def _load_image_fix_orientation(image_bytes: bytes) -> Optional["np.ndarray"]:
    """
    Carga bytes -> PIL -> aplica EXIF transpose -> RGB -> np.ndarray.
    Maneja CMYK, RGBA, etc.
    """
    with Image.open(io.BytesIO(image_bytes)) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode != "RGB":
            im = im.convert("RGB")
        arr = np.asarray(im)
    return arr


def embedding_from_image_bytes(image_bytes: bytes) -> Optional["np.ndarray"]:
    """
    Devuelve embedding float32 (shape (512,)) del rostro principal o None si no detecta.
    Con InsightFace el vector viene normalizado (norma ≈ 1.0) y tiene 512 dimensiones.
    """
    arr = _load_image_fix_orientation(image_bytes)
    if arr is None:
        return None

    # InsightFace trabaja en BGR
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    app = _get_app()
    faces = app.get(bgr)  # detecta rostros y calcula embeddings

    if not faces:
        return None

    # Elegimos el rostro más grande
    def area(face) -> float:
        x1, y1, x2, y2 = face.bbox
        return max(0.0, (x2 - x1)) * max(0.0, (y2 - y1))

    face = max(faces, key=area)

    # Embedding normalizado (512D)
    vec = face.normed_embedding.astype("float32")
    return vec


def bytes_from_embedding(vec: "np.ndarray") -> bytes:
    return vec.tobytes()
