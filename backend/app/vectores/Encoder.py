# app/vectores/encoder.py
from typing import BinaryIO, Optional
from pathlib import Path
from threading import Lock
import io
import numpy as np
from PIL import Image, ImageOps
import cv2


from insightface.app.common import Face
from insightface.model_zoo import get_model
from insightface.utils import ensure_available


class _FaceEngine:
    """Carga únicamente los dos ONNX originales necesarios de buffalo_l."""

    def __init__(self) -> None:
        model_dir = Path(ensure_available("models", "buffalo_l", root="~/.insightface"))
        self.detector = get_model(
            str(model_dir / "det_10g.onnx"), providers=["CPUExecutionProvider"]
        )
        self.recognizer = get_model(
            str(model_dir / "w600k_r50.onnx"), providers=["CPUExecutionProvider"]
        )
        if self.detector is None or self.detector.taskname != "detection":
            raise RuntimeError("El detector de buffalo_l no es compatible")
        if self.recognizer is None or self.recognizer.taskname != "recognition":
            raise RuntimeError("El modelo de reconocimiento de buffalo_l no es compatible")

        # Mismos parámetros que FaceAnalysis.prepare() con la configuración anterior.
        self.detector.prepare(ctx_id=0, input_size=(640, 640), det_thresh=0.5)
        self.recognizer.prepare(ctx_id=0)

    def embedding_from_bgr(self, image: "np.ndarray") -> Optional["np.ndarray"]:
        boxes, keypoints = self.detector.detect(image, max_num=0, metric="default")
        if boxes.shape[0] == 0:
            return None

        # Mantener el criterio anterior, incluidos los empates: mayor área, primero.
        def area(index: int) -> float:
            x1, y1, x2, y2 = boxes[index, :4]
            return max(0.0, (x2 - x1)) * max(0.0, (y2 - y1))

        index = max(range(boxes.shape[0]), key=area)
        face = Face(
            bbox=boxes[index, :4],
            kps=keypoints[index] if keypoints is not None else None,
            det_score=boxes[index, 4],
        )
        self.recognizer.get(image, face)
        return face.normed_embedding.astype("float32")


_APP: Optional[_FaceEngine] = None
_APP_LOCK = Lock()
_INFERENCE_LOCK = Lock()


def _get_app() -> _FaceEngine:
    """
    Inicializa y devuelve una única instancia del motor facial por proceso.
    Conserva detección y reconocimiento de 'buffalo_l' (512D, normalizado).
    """
    global _APP
    if _APP is None:
        with _APP_LOCK:
            # Otra solicitud puede haber completado la carga mientras esperábamos.
            if _APP is None:
                # Publicar solo después de preparar: un fallo permite reintentar.
                _APP = _FaceEngine()
    return _APP


def _load_image_fix_orientation(image_file: BinaryIO) -> Optional["np.ndarray"]:
    """
    Lee el archivo -> PIL -> aplica EXIF transpose -> RGB -> np.ndarray.
    Maneja CMYK, RGBA, etc.
    """
    with Image.open(image_file) as source:
        with ImageOps.exif_transpose(source) as oriented:
            if oriented.mode == "RGB":
                return np.asarray(oriented)
            with oriented.convert("RGB") as rgb:
                return np.asarray(rgb)


def embedding_from_image_file(image_file: BinaryIO) -> Optional["np.ndarray"]:
    """Serializa decodificación e inferencia para no acumular imágenes expandidas."""
    with _INFERENCE_LOCK:
        app = _get_app()
        arr = _load_image_fix_orientation(image_file)
        if arr is None:
            return None

        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        # La inferencia solo necesita BGR; liberar la representación RGB antes.
        del arr
        return app.embedding_from_bgr(bgr)


def embedding_from_image_bytes(image_bytes: bytes) -> Optional["np.ndarray"]:
    """
    Devuelve embedding float32 (shape (512,)) del rostro principal o None si no detecta.
    Con InsightFace el vector viene normalizado (norma ≈ 1.0) y tiene 512 dimensiones.
    """
    with io.BytesIO(image_bytes) as image_file:
        return embedding_from_image_file(image_file)


def bytes_from_embedding(vec: "np.ndarray") -> bytes:
    return vec.tobytes()
