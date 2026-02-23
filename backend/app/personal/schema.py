# app/personal/schema.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import time

class PersonalCreate(BaseModel):
    documento: str = Field(..., max_length=32)
    nombres: str = Field(..., max_length=120)
    apellidos: str = Field(..., max_length=120)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, max_length=40)
    # Eliminamos horas_semana y añadimos horario de entrada y salida
    horario_int: Optional[time] = None
    horario_off: Optional[time] = None

class PersonalOut(BaseModel):
    id: int
    documento: str
    nombres: str
    apellidos: str
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    estado: str
    horario_int: Optional[time]
    horario_off: Optional[time]

    class Config:
        from_attributes = True  # mapear desde ORM
