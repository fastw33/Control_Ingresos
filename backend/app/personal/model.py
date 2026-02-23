# app/personal/model.py
from sqlalchemy import String, DateTime, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects import mysql
from app.core.db import Base
from typing import Optional
from datetime import datetime, time

class Personal(Base):
    __tablename__ = "personal"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )
    documento: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    nombres: Mapped[str] = mapped_column(String(120), nullable=False)
    apellidos: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    estado: Mapped[str] = mapped_column(
        mysql.ENUM("activo", "inactivo"),
        nullable=False,
        server_default="inactivo",
    )

    # Campos de horario (entrada y salida)
    horario_int: Mapped[Optional[time]] = mapped_column(
        Time(), nullable=True
    )
    horario_off: Mapped[Optional[time]] = mapped_column(
        Time(), nullable=True
    )

    fecha_alta: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    fecha_baja: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )

    # Relaciones con otras tablas
    vectores = relationship("PersonalVectores", back_populates="personal", uselist=False)
    marcaciones = relationship("Marcacion", back_populates="personal")
    # Nueva relación: solicitudes de permiso
    solicitudes = relationship("SolicitudPermiso", back_populates="personal")

    def __repr__(self) -> str:
        return f"<Personal id={self.id} documento={self.documento} estado={self.estado}>"
