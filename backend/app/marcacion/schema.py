# app/marcacion/schema.py
from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# ---------------------------
# Enums (más estrictos)
# ---------------------------
TipoMarcacion = Literal["entrada", "salida", "on_almuerzo", "off_almuerzo"]

# ---------------------------
# DTOs de Personal (ligero)
# ---------------------------
class PersonalLite(BaseModel):
    id: int
    documento: str
    nombres: str
    apellidos: str

    class Config:
        from_attributes = True  # Pydantic v2


# =========================================================
# RESPUESTAS PARA LISTADO / DETALLE DE MARCACIONES
# =========================================================

# Modelo base con TODOS los campos de la tabla marcacion
class MarcacionWithPersonalOut(BaseModel):
    id: int
    personal_id: int
    tipo: TipoMarcacion
    fecha_hora: datetime
    dispositivo: Optional[str] = None
    observacion: Optional[str] = None
    justificacion: Optional[str] = None
    evidencia_url: Optional[str] = None
    aprobado: Optional[bool] = None
    creado_en: datetime
    personal: PersonalLite

    class Config:
        from_attributes = True  # Pydantic v2


# Alias de compatibilidad para el controller
class MarcacionFullOut(MarcacionWithPersonalOut):
    pass


# 👑 Uso admin (mantiene compatibilidad; hereda todo)
class MarcacionWithPersonalAdminOut(MarcacionFullOut):
    pass


# =========================================================
# ENTRADAS Y RESPUESTAS DE NEGOCIO
# =========================================================

# Registrar marcación manual (sin biometría)
class MarcacionCreateIn(BaseModel):
    personal_id: int
    tipo: TipoMarcacion = Field(
        ...,
        description="entrada | salida | on_almuerzo | off_almuerzo"
    )
    dispositivo: Optional[str] = None
    observacion: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Texto breve; no enviar datos sensibles"
    )


# Resultado de registrar (con personal_id conocido) — BIOMETRÍA EFÍMERA
class MarcacionRegistrarOut(BaseModel):
    match: bool = Field(..., description="Coincidencia biométrica")
    score: float = Field(..., ge=0)
    umbral: float = Field(..., ge=0)
    mejor_vector: int
    registrado: bool
    marcacion_id: Optional[int] = None
    fecha_hora: Optional[datetime] = None
    mensaje: Optional[str] = None

    class Config:
        from_attributes = True


# Reconocimiento automático (sin personal_id); registra si coincide — BIOMETRÍA EFÍMERA
class MarcacionAutoOut(BaseModel):
    match: bool
    score: float = Field(..., ge=0)
    umbral: float = Field(..., ge=0)
    mejor_vector: Optional[int] = None
    personal_id: Optional[int] = None
    documento: Optional[str] = None
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    registrado: bool
    marcacion_id: Optional[int] = None
    fecha_hora: Optional[datetime] = None
    mensaje: Optional[str] = None

    class Config:
        from_attributes = True


# Respuesta al subir justificación (PDF/imagen) — metadatos únicamente
class JustificacionOut(BaseModel):
    filename: str
    mime: str
    size: int
    sha256: str
