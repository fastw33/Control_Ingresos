# app/core/db.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

# Cargar variables desde .env
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "control_ingresos")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")

# ⚙️ Fijo para Colombia (sin DST)
TIME_ZONE_OFFSET = "-05:00"  # Bogotá UTC-5

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset={DB_CHARSET}"
)


class Base(DeclarativeBase):
    pass


# Crear engine y Session
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        # Establecer la zona horaria fija a UTC-5 (Bogotá)
        db.execute(text(f"SET time_zone = '{TIME_ZONE_OFFSET}'"))

        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
