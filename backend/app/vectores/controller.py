# app/vectores/controller.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from . import service
from .schema import (
    VectoresCreate,
    VectoresOut,
    VectoresUpdate,
    VectoresMetaOut,
    VerificacionOut,
)

router = APIRouter(prefix="/vectores", tags=["vectores"])

# ---- crear/reemplazar desde imágenes (multipart) ----
@router.post("/from-images", response_model=VectoresMetaOut, status_code=status.HTTP_201_CREATED)
def crear_vectores_desde_imagenes(
    personal_id: int = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    obj = service.crear_o_reemplazar_from_images(db, personal_id, files)
    return VectoresMetaOut(id_personal=obj.id_personal, creado_en=getattr(obj, "creado_en", None))

# ---- actualizar (reemplazar) desde imágenes (multipart) ----
@router.put("/from-images", response_model=VectoresMetaOut, status_code=status.HTTP_200_OK)
def actualizar_vectores_desde_imagenes(
    personal_id: int = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    obj = service.crear_o_reemplazar_from_images(db, personal_id, files)
    return VectoresMetaOut(id_personal=obj.id_personal, creado_en=getattr(obj, "creado_en", None))

# ---- verificar imagen contra los 5 vectores (similitud coseno) ----
@router.post("/verify", response_model=VerificacionOut)
def verificar_imagen(
    personal_id: int = Form(...),
    file: UploadFile = File(...),
    tipo: Optional[str] = Form(None),      # "entrada" / "salida" / "on_almuerzo" / "off_almuerzo" (opcional)
    umbral: Optional[float] = Form(None),  # si no viene, se usa service.UMBRAL_COSENO (0.35)
    db: Session = Depends(get_db),
):
    um = service.UMBRAL_COSENO if umbral is None else float(umbral)
    return service.verificar_imagen(db, personal_id, file, tipo=tipo, umbral=um)

# ---- CRUD JSON plano ----
@router.post("", response_model=VectoresOut, status_code=status.HTTP_201_CREATED)
def crear_vectores(payload: VectoresCreate, db: Session = Depends(get_db)):
    return service.crear_o_reemplazar(db, payload)

@router.get("/{personal_id}", response_model=VectoresOut)
def obtener_vectores(personal_id: int, db: Session = Depends(get_db)):
    obj = service.obtener_por_personal(db, personal_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Vectores no encontrados para ese personal")
    return obj

@router.put("/{personal_id}", response_model=VectoresOut)
def actualizar_vectores(personal_id: int, payload: VectoresUpdate, db: Session = Depends(get_db)):
    obj = service.actualizar(db, personal_id, payload)
    if not obj:
        raise HTTPException(status_code=404, detail="Vectores no encontrados para ese personal")
    return obj

@router.delete("/{personal_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_vectores(personal_id: int, db: Session = Depends(get_db)):
    borrados = service.eliminar_por_personal(db, personal_id)
    if not borrados:
        raise HTTPException(status_code=404, detail="Vectores no encontrados para ese personal")
    return None
