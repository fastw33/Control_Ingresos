# app/vectores/model.py
from datetime import datetime
from sqlalchemy import ForeignKey, LargeBinary, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects import mysql
from sqlalchemy.sql import func
from app.core.db import Base

class PersonalVectores(Base):
    __tablename__ = "personal_vectores"

    id_personal: Mapped[int] = mapped_column(
        "personal_id",                      # columna real
        mysql.BIGINT(unsigned=True),
        ForeignKey("personal.id", ondelete="CASCADE"),
        primary_key=True,                   # o unique=True si no es PK en tu tabla
        nullable=False,
        unique=True,
    )

    vector1: Mapped[bytes] = mapped_column("vector_1", LargeBinary, nullable=False)
    vector2: Mapped[bytes] = mapped_column("vector_2", LargeBinary, nullable=False)
    vector3: Mapped[bytes] = mapped_column("vector_3", LargeBinary, nullable=False)
    vector4: Mapped[bytes] = mapped_column("vector_4", LargeBinary, nullable=False)
    vector5: Mapped[bytes] = mapped_column("vector_5", LargeBinary, nullable=False)

    creado_en: Mapped[datetime] = mapped_column(  # 👈 atributo y nombre de columna iguales
        "creado_en",
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(),
    )

    personal = relationship("Personal", back_populates="vectores", passive_deletes=True)

    def __repr__(self) -> str:
        return f"<PersonalVectores id_personal={self.id_personal}>"
