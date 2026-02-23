from pydantic import BaseModel, field_serializer
from typing import Optional
from datetime import datetime
import base64

class VectoresBase(BaseModel):
    vector1: Optional[bytes] = None
    vector2: Optional[bytes] = None
    vector3: Optional[bytes] = None
    vector4: Optional[bytes] = None
    vector5: Optional[bytes] = None

class VectoresCreate(VectoresBase):
    personal_id: int
    vector1: bytes
    vector2: bytes
    vector3: bytes
    vector4: bytes
    vector5: bytes

class VectoresUpdate(VectoresBase):
    pass

class VectoresOut(BaseModel):
    id_personal: int
    vector1: bytes
    vector2: bytes
    vector3: bytes
    vector4: bytes
    vector5: bytes

    # 👇 convierte bytes -> base64 string en la salida JSON
    @field_serializer("vector1", "vector2", "vector3", "vector4", "vector5")
    def _bytes_to_b64(self, v: bytes, _info):
        return base64.b64encode(v).decode("ascii")

    class Config:
        from_attributes = True

class VectoresMetaOut(BaseModel):
    id_personal: int
    creado_en: Optional[datetime] = None
    class Config:
        from_attributes = True

class VerificacionOut(BaseModel):
    match: bool
    score: float
    umbral: float
    mejor_vector: int
    mensaje: Optional[str] = None
