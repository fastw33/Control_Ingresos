from typing import Optional, List, Literal
from datetime import datetime
import os

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.marcacion.schema import (
    MarcacionFullOut,           # ← usa el nuevo esquema “full”
    MarcacionRegistrarOut,
    MarcacionAutoOut,
)
from app.marcacion import service as marc_service

# Config para la carga de justificaciones (NO biometría)
from app.core.config import settings
from app.core.files import secure_filename, ensure_storage_dir, sha256_bytes

router = APIRouter(prefix="/marcacion", tags=["marcacion"])

# Directorio para JUSTIFICACIONES (PDF/imagen) — no usar para biometría
UPLOAD_DIR = settings.storage_dir


# =========================
# LISTADO (expone evidencia_url; el front decide si mostrarla)
# =========================
@router.get("", response_model=List[MarcacionFullOut])  # ← cambio de esquema
def listar_marcaciones(
    limit: Optional[int] = Query(None, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    tipo: Optional[str] = Query(None, pattern="^(entrada|salida|on_almuerzo|off_almuerzo)$"),
    personal_id: Optional[int] = None,
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    return marc_service.listar_con_personal(
        db,
        limit=limit,
        offset=offset,
        tipo=tipo,
        personal_id=personal_id,
        desde=desde,
        hasta=hasta,
        include_evidencia_url=True,  # backend la expone; front decide si mostrarla
    )


# =========================
# REGISTRAR (con personal_id) — biometría EFÍMERA, NO se guarda archivo
# =========================
@router.post("/registrar", response_model=MarcacionRegistrarOut)
def registrar_con_personal(
    personal_id: int = Form(...),
    file: UploadFile = File(...),  # no se persiste
    tipo: Optional[Literal["entrada","salida","on_almuerzo","off_almuerzo"]] = Form(None),

    # —— control horario / alias —— 
    usar_manual: bool = Form(False),
    # ISO completos (varios alias)
    fecha_hora_manual: Optional[str] = Form(None),
    fecha_hora: Optional[str] = Form(None),
    fechaHora: Optional[str] = Form(None),
    fechaHoraManual: Optional[str] = Form(None),
    # pares fecha/hora (alias)
    fecha_manual: Optional[str] = Form(None),
    hora_manual: Optional[str] = Form(None),
    fecha: Optional[str] = Form(None),
    hora: Optional[str] = Form(None),
    # zona horaria
    tz: Optional[str] = Form(None),
    offset_minutes: Optional[int] = Form(None),  

    # otros campos no persistidos aquí
    justificacion: Optional[str] = Form(None),
    aprobado: Optional[bool] = Form(None),
    umbral: Optional[float] = Form(None),

    db: Session = Depends(get_db),
):
    try:
        result = marc_service.registrar_con_personal(
            db,
            personal_id=personal_id,
            file=file,
            tipo=tipo,
            usar_manual=usar_manual,
            tz=tz,
            fecha_hora_manual=fecha_hora_manual,
            fecha_hora=fecha_hora,
            fechaHora=fechaHora,
            fechaHoraManual=fechaHoraManual,
            fecha_manual=fecha_manual,
            hora_manual=hora_manual,
            fecha=fecha,
            hora=hora,
            justificacion=None,
            evidencia_url=None,
            aprobado=None,
            umbral=umbral,
        )
    finally:
        try:
            file.file.close()
        except Exception:
            pass
    return result


# =========================
# AUTO-RECONOCER — biometría EFÍMERA, NO se guarda archivo
# =========================
@router.post("/auto", response_model=MarcacionAutoOut)
def auto_reconocer(
    file: UploadFile = File(...),  # no se persiste
    tipo: Optional[Literal["entrada","salida","on_almuerzo","off_almuerzo"]] = Form(None),

    # —— control horario / alias —— 
    usar_manual: bool = Form(False),
    # ISO completos (varios alias)
    fecha_hora_manual: Optional[str] = Form(None),
    fecha_hora: Optional[str] = Form(None),
    fechaHora: Optional[str] = Form(None),
    fechaHoraManual: Optional[str] = Form(None),
    # pares fecha/hora (alias)
    fecha_manual: Optional[str] = Form(None),
    hora_manual: Optional[str] = Form(None),
    fecha: Optional[str] = Form(None),
    hora: Optional[str] = Form(None),
    # zona horaria
    tz: Optional[str] = Form(None),
    offset_minutes: Optional[int] = Form(None),

    # otros campos no persistidos aquí
    justificacion: Optional[str] = Form(None),
    aprobado: Optional[bool] = Form(None),
    umbral: Optional[float] = Form(None),

    db: Session = Depends(get_db),
):
    try:
        result = marc_service.auto_reconocer_y_registrar(
            db,
            file=file,
            tipo=tipo,
            usar_manual=usar_manual,
            tz=tz,
            fecha_hora_manual=fecha_hora_manual,
            fecha_hora=fecha_hora,
            fechaHora=fechaHora,
            fechaHoraManual=fechaHoraManual,
            fecha_manual=fecha_manual,
            hora_manual=hora_manual,
            fecha=fecha,
            hora=hora,
            justificacion=None,
            evidencia_url=None,
            aprobado=None,
            umbral=umbral,
        )
    finally:
        try:
            file.file.close()
        except Exception:
            pass
    return result


# =========================
# ACTUALIZAR (subir justificación posterior) — aquí SÍ se guarda archivo
# =========================
@router.put("/{marcacion_id}", response_model=MarcacionFullOut)  # ← cambio de esquema
def actualizar_marcacion(
    marcacion_id: int,
    justificacion: Optional[str] = Form(None),
    observacion: Optional[str] = Form(None),
    aprobado: Optional[bool] = Form(None),
    file: Optional[UploadFile] = File(None),  # documento de justificación (pdf/imagen)
    db: Session = Depends(get_db),
):
    evidencia_url: Optional[str] = None

    if file is not None:
        mime = (file.content_type or "").lower()
        if mime not in settings.allowed_mime:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Tipo no permitido: {mime}"
            )

        data = file.file.read()
        if not data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archivo vacío")
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Archivo supera {settings.max_upload_mb} MB",
            )

        ensure_storage_dir()
        from datetime import datetime as _dt
        unique = _dt.utcnow().strftime("%Y%m%d%H%M%S%f")
        safe_name = secure_filename(file.filename or "justificacion")
        final_name = f"{unique}_{safe_name}"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        final_path = os.path.join(UPLOAD_DIR, final_name)

        with open(final_path, "wb") as f:
            f.write(data)

        _ = sha256_bytes(data)  # si luego decides guardar el hash
        evidencia_url = final_path

        try:
            file.file.close()
        except Exception:
            pass

    return marc_service.actualizar_marcacion(
        db,
        marcacion_id,
        justificacion=justificacion,
        evidencia_url=evidencia_url,
        observacion=observacion,
        aprobado=aprobado,
    )


# =========================
# ACTUALIZAR FECHA/HORA (solo creado_en o fecha_hora) — requiere aprobado
# =========================
@router.put("/{marcacion_id}/fecha", response_model=MarcacionFullOut)  # ← cambio de esquema
def actualizar_fecha_marcacion(
    marcacion_id: int,
    # mismos alias que usas en registrar/auto:
    usar_manual: bool = Form(True),
    fecha_hora_manual: Optional[str] = Form(None),
    fecha_hora: Optional[str] = Form(None),
    fechaHora: Optional[str] = Form(None),
    fechaHoraManual: Optional[str] = Form(None),
    fecha_manual: Optional[str] = Form(None),
    hora_manual: Optional[str] = Form(None),
    fecha: Optional[str] = Form(None),
    hora: Optional[str] = Form(None),
    tz: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    return marc_service.actualizar_fecha_hora(
        db,
        marcacion_id,
        usar_manual=usar_manual,
        tz=tz,
        fecha_hora_manual=fecha_hora_manual,
        fecha_hora=fecha_hora,
        fechaHora=fechaHora,
        fechaHoraManual=fechaHoraManual,
        fecha_manual=fecha_manual,
        hora_manual=hora_manual,
        fecha=fecha,
        hora=hora,
    )
