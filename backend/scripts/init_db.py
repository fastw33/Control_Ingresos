import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # agrega ../ al path

from app.core.db import Base, engine
import app.personal.model  # noqa
import app.vectores.model  # noqa
import app.marcacion.model  # noqa


def main():
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas creadas (o ya existían).")

if __name__ == "__main__":
    main()
