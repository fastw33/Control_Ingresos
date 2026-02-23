# app/marcacion/model.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects import mysql

from app.core.db import Base


class Marcacion(Base):
    __tablename__ = "marcacion"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )

    personal_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("personal.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Evento de marcación (no biometría, solo tipo de marca)
    tipo: Mapped[str] = mapped_column(
        mysql.ENUM("entrada", "salida", "on_almuerzo", "off_almuerzo"),
        nullable=False,
    )

    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        index=True,
    )

  
    dispositivo: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

 
    observacion: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    
    justificacion: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

   
    evidencia_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

 
    aprobado: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(),
    )

    # relación inversa con Personal
    personal = relationship("Personal", back_populates="marcaciones")

    # índice compuesto
    __table_args__ = (
        Index("idx_marc_personal_fecha", "personal_id", "fecha_hora"),
    )

    def __repr__(self) -> str:
        return (
            f"<Marcacion id={self.id} personal_id={self.personal_id} "
            f"tipo={self.tipo} fecha_hora={self.fecha_hora}>"
        )
