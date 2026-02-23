# app/solicitud/model.py
from __future__ import annotations

from datetime import datetime, date, time
from typing import Optional

from sqlalchemy import (
    Date,
    Time,
    DateTime,
    Text,
    String,
    Enum,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects import mysql

from app.core.db import Base


class SolicitudPermiso(Base):
    __tablename__ = "solicitud_permisos"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )

    # Referencia al trabajador que solicita el permiso
    personal_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("personal.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Fecha a la que corresponde el permiso
    fecha_permiso: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    # Horarios solicitados (pueden ser NULL si no aplican)
    hora_entrada: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    hora_salida: Mapped[Optional[time]] = mapped_column(Time, nullable=True)

    # Motivo de la solicitud presentado por el empleado (texto libre)
    justificacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ruta al archivo de evidencia (imagen, PDF, vídeo, etc.)
    evidencia_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Observaciones añadidas por RRHH o el aprobador
    observacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Descripción o valor de la reposición de tiempo, si corresponde
    reposicion_tiempo: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Estado de la solicitud: 'pendiente', 'aprobado' o 'rechazado'
    estado: Mapped[str] = mapped_column(
        Enum("pendiente", "aprobado", "rechazado"),
        nullable=False,
        server_default="pendiente",
    )

    # Marcaciones asociadas (entrada y salida).  Se dejan NULL hasta que la solicitud sea aprobada.
    marcacion_entrada_id: Mapped[Optional[int]] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("marcacion.id", ondelete="SET NULL"),
        nullable=True,
    )
    marcacion_salida_id: Mapped[Optional[int]] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("marcacion.id", ondelete="SET NULL"),
        nullable=True,
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    actualizado_en: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        onupdate=func.current_timestamp(),
    )

    # Relaciones
    personal = relationship("Personal", back_populates="solicitudes")
    marcacion_entrada = relationship("Marcacion", foreign_keys=[marcacion_entrada_id])
    marcacion_salida = relationship("Marcacion", foreign_keys=[marcacion_salida_id])

    __table_args__ = (
        # Índice para búsquedas combinadas por personal y fecha
        Index("idx_solicitud_personal_fecha", "personal_id", "fecha_permiso"),
    )

    def __repr__(self) -> str:
        return (
            f"<SolicitudPermiso id={self.id} personal_id={self.personal_id} "
            f"fecha_permiso={self.fecha_permiso} estado={self.estado}>"
        )
