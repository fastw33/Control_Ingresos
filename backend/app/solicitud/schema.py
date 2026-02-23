# app/solicitud/schema.py
from typing import Optional
from datetime import date, time, datetime
from pydantic import BaseModel, Field

# Modelo reducido de personal
class PersonalLite(BaseModel):
    id: int
    documento: str
    nombres: str
    apellidos: str

    class Config:
        from_attributes = True

# Esquema de creación de solicitud
class SolicitudPermisoCreate(BaseModel):
    personal_id: int
    fecha_permiso: date
    hora_entrada: Optional[time] = None
    hora_salida: Optional[time] = None
    justificacion: Optional[str] = None
    reposicion_tiempo: Optional[str] = None

# Esquema de actualización (RRHH)
class SolicitudPermisoUpdate(BaseModel):
    justificacion: Optional[str] = None
    reposicion_tiempo: Optional[str] = None
    observacion: Optional[str] = None
    # Usamos 'pattern' en lugar de 'regex' para Pydantic v2
    estado: Optional[str] = Field(
        None, pattern="^(pendiente|aprobado|rechazado)$"
    )
    marcacion_entrada_id: Optional[int] = None
    marcacion_salida_id: Optional[int] = None

# Esquema de salida
class SolicitudPermisoOut(BaseModel):
    id: int
    personal_id: int
    fecha_permiso: date
    hora_entrada: Optional[time]
    hora_salida: Optional[time]
    justificacion: Optional[str]
    evidencia_url: Optional[str]
    observacion: Optional[str]
    reposicion_tiempo: Optional[str]
    estado: str
    marcacion_entrada_id: Optional[int]
    marcacion_salida_id: Optional[int]
    creado_en: datetime
    actualizado_en: Optional[datetime]
    personal: PersonalLite

    class Config:
        from_attributes = True
