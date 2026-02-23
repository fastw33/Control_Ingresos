# scripts/test_db.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()  # lee .env en la raíz

DB_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}?charset={os.getenv('DB_CHARSET','utf8mb4')}"
)

engine = create_engine(DB_URL, pool_pre_ping=True, future=True)

with engine.connect() as conn:
    # fija zona horaria (opcional)
    tz = os.getenv("TIME_ZONE", "America/Bogota")
    conn.execute(text(f"SET time_zone = '{tz}'"))
    r = conn.execute(text("SELECT NOW() as ahora")).mappings().first()
    print("✅ Conexión OK. NOW():", r["ahora"])
