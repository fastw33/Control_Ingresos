# app/vectores/repository.py
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from app.vectores.model import PersonalVectores

def get_by_personal(db: Session, personal_id: int) -> Optional[PersonalVectores]:
    return db.execute(
        select(PersonalVectores).where(PersonalVectores.id_personal == personal_id)
    ).scalar_one_or_none()

def create(db: Session, data: dict) -> PersonalVectores:
    obj = PersonalVectores(**data)
    db.add(obj)
    db.flush()     # inserta y genera defaults (creado_en)
    db.refresh(obj)
    db.commit()    # 👈 asegura persistencia
    return obj

def update(db: Session, obj: PersonalVectores, data: dict) -> PersonalVectores:
    for k, v in data.items():
        setattr(obj, k, v)
    db.flush()
    db.refresh(obj)
    db.commit()    # 👈 asegura persistencia
    return obj

def delete_by_personal(db: Session, personal_id: int) -> int:
    res = db.execute(
        delete(PersonalVectores)
        .where(PersonalVectores.id_personal == personal_id)
    )
    db.commit()    # 👈 asegura persistencia
    try:
        return res.rowcount or 0
    except Exception:
        return 0
from sqlalchemy import select

def list_all(db: Session) -> list[PersonalVectores]:
    return db.execute(select(PersonalVectores)).scalars().all()
