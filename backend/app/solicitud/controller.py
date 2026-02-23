# app/solicitud/controller.py
from typing import Optional, List
from datetime import date, time
import os
import shutil

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.solicitud.schema import SolicitudPermisoOut
from app.solicitud import service as solicitud_service

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])

UPLOAD_DIR = "upload/evidencias"

@router.get("", response_model=List[SolicitudPermisoOut])
def listar_solicitudes(
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    estado: Optional[str] = Query(
        None,
        pattern="^(pendiente|aprobado|rechazado)$",
    ),
    personal_id: Optional[int] = Query(None, ge=1),
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return solicitud_service.listar_solicitudes(
        db,
        limit=limit,
        offset=offset,
        estado=estado,
        personal_id=personal_id,
        desde=desde,
        hasta=hasta,
    )

@router.post("", response_model=SolicitudPermisoOut)
def crear_solicitud(
    personal_id: int = Form(...),
    fecha_permiso: date = Form(...),
    hora_entrada: Optional[time] = Form(None),
    hora_salida: Optional[time] = Form(None),
    justificacion: Optional[str] = Form(None),
    reposicion_tiempo: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    evidencia_url: Optional[str] = None
    if file:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        evidencia_url = file_path

    return solicitud_service.crear_solicitud(
        db,
        personal_id=personal_id,
        fecha_permiso=fecha_permiso,
        hora_entrada=hora_entrada,
        hora_salida=hora_salida,
        justificacion=justificacion,
        evidencia_url=evidencia_url,
        reposicion_tiempo=reposicion_tiempo,
    )

@router.put("/{solicitud_id}", response_model=SolicitudPermisoOut)
def actualizar_solicitud(
    solicitud_id: int,
    justificacion: Optional[str] = Form(None),
    reposicion_tiempo: Optional[str] = Form(None),
    observacion: Optional[str] = Form(None),
    estado: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    evidencia_url: Optional[str] = None
    if file:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        evidencia_url = file_path

    return solicitud_service.actualizar_solicitud(
        db,
        solicitud_id=solicitud_id,
        justificacion=justificacion,
        evidencia_url=evidencia_url,
        reposicion_tiempo=reposicion_tiempo,
        observacion=observacion,
        estado=estado,
    )
