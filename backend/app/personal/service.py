# app/personal/service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.personal import repository
from app.personal.model import Personal
from app.personal.schema import PersonalCreate

def crear_personal(db: Session, payload: PersonalCreate) -> Personal:
    if repository.get_by_documento(db, payload.documento):
        raise HTTPException(status_code=409, detail="El documento ya existe")
    data = payload.dict()
    # normalizaciones simples
    data["nombres"] = data["nombres"].strip().title()
    data["apellidos"] = data["apellidos"].strip().title()
    return repository.create(db, data)

def listar_personal(db: Session) -> list[Personal]:
    return repository.list_all(db)

def obtener_personal(db: Session, personal_id: int) -> Personal:
    obj = repository.get(db, personal_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Personal no encontrado")
    return obj
