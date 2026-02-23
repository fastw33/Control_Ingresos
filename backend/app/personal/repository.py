# app/personal/repository.py
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import select
from app.personal.model import Personal


def get_by_documento(db: Session, documento: str) -> Optional[Personal]:
    return db.execute(
        select(Personal).where(Personal.documento == documento)
    ).scalar_one_or_none()


def create(db: Session, data: dict) -> Personal:
    obj = Personal(**data)
    db.add(obj)
    db.flush()   # para obtener id
    db.refresh(obj)
    return obj


def list_all(db: Session) -> List[Personal]:
    return db.execute(
        select(Personal).order_by(Personal.id.desc())
    ).scalars().all()


def get(db: Session, personal_id: int) -> Optional[Personal]:
    return db.get(Personal, personal_id)
