# app/solicitud/service.py
from typing import Optional, List
from datetime import datetime, date, time

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.solicitud import repository as repo
from app.solicitud.schema import SolicitudPermisoOut
from app.solicitud.model import SolicitudPermiso
from app.marcacion import repository as marc_repo
from app.marcacion.model import Marcacion

# ---------- Listar solicitudes con datos de personal ----------
def listar_solicitudes(
    db: Session,
    *,
    limit: int = 100,
    offset: int = 0,
    estado: Optional[str] = None,
    personal_id: Optional[int] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
) -> List[SolicitudPermisoOut]:
    rows = repo.list_with_personal(
        db,
        limit=limit,
        offset=offset,
        estado=estado,
        personal_id=personal_id,
        desde=desde,
        hasta=hasta,
    )
    out: List[SolicitudPermisoOut] = []
    for r in rows:
        out.append(
            SolicitudPermisoOut(
                id=r.id,
                personal_id=r.personal_id,
                fecha_permiso=r.fecha_permiso,
                hora_entrada=r.hora_entrada,
                hora_salida=r.hora_salida,
                justificacion=r.justificacion,
                evidencia_url=r.evidencia_url,
                observacion=r.observacion,
                reposicion_tiempo=r.reposicion_tiempo,
                estado=r.estado,
                marcacion_entrada_id=r.marcacion_entrada_id,
                marcacion_salida_id=r.marcacion_salida_id,
                creado_en=r.creado_en,
                actualizado_en=r.actualizado_en,
                personal={
                    "id": r.personal_id,
                    "documento": r.documento,
                    "nombres": r.nombres,
                    "apellidos": r.apellidos,
                },
            )
        )
    return out

# ---------- Crear una solicitud de permiso ----------
def crear_solicitud(
    db: Session,
    *,
    personal_id: int,
    fecha_permiso: date,
    hora_entrada: Optional[time] = None,
    hora_salida: Optional[time] = None,
    justificacion: Optional[str] = None,
    evidencia_url: Optional[str] = None,
    reposicion_tiempo: Optional[str] = None,
) -> SolicitudPermisoOut:
    data = {
        "personal_id": personal_id,
        "fecha_permiso": fecha_permiso,
        "hora_entrada": hora_entrada,
        "hora_salida": hora_salida,
        "justificacion": justificacion,
        "evidencia_url": evidencia_url,
        "reposicion_tiempo": reposicion_tiempo,
        "estado": "pendiente",
    }
    obj = repo.create(db, data)
    db.commit()
    db.refresh(obj)

    # Construir respuesta con datos de personal
    return SolicitudPermisoOut(
        id=obj.id,
        personal_id=obj.personal_id,
        fecha_permiso=obj.fecha_permiso,
        hora_entrada=obj.hora_entrada,
        hora_salida=obj.hora_salida,
        justificacion=obj.justificacion,
        evidencia_url=obj.evidencia_url,
        observacion=obj.observacion,
        reposicion_tiempo=obj.reposicion_tiempo,
        estado=obj.estado,
        marcacion_entrada_id=obj.marcacion_entrada_id,
        marcacion_salida_id=obj.marcacion_salida_id,
        creado_en=obj.creado_en,
        actualizado_en=obj.actualizado_en,
        personal={
            "id": obj.personal.id,
            "documento": obj.personal.documento,
            "nombres": obj.personal.nombres,
            "apellidos": obj.personal.apellidos,
        },
    )

# ---------- Actualizar una solicitud (observación, estado, justificación, evidencia, reposición y marcaciones) ----------
def actualizar_solicitud(
    db: Session,
    solicitud_id: int,
    *,
    justificacion: Optional[str] = None,
    evidencia_url: Optional[str] = None,
    reposicion_tiempo: Optional[str] = None,
    observacion: Optional[str] = None,
    estado: Optional[str] = None,
) -> SolicitudPermisoOut:
    sol = repo.get(db, solicitud_id)
    if not sol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")

    # Actualizar campos enviados
    if justificacion is not None:
        sol.justificacion = justificacion
    if evidencia_url is not None:
        sol.evidencia_url = evidencia_url
    if reposicion_tiempo is not None:
        sol.reposicion_tiempo = reposicion_tiempo
    if observacion is not None:
        sol.observacion = observacion

    # Procesar cambio de estado
    if estado is not None:
        # Validar valor del estado
        if estado not in {"pendiente", "aprobado", "rechazado"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Estado no válido. Debe ser 'pendiente', 'aprobado' o 'rechazado'.",
            )
        # Si se aprueba y aún no existen marcaciones asociadas, crearlas
        if estado == "aprobado" and (sol.marcacion_entrada_id is None or sol.marcacion_salida_id is None):
            crear_marcaciones_para_solicitud(db, sol)
        sol.estado = estado
    # En caso de rechazo, simplemente actualizamos el estado

    db.commit()
    db.refresh(sol)

    return SolicitudPermisoOut(
        id=sol.id,
        personal_id=sol.personal_id,
        fecha_permiso=sol.fecha_permiso,
        hora_entrada=sol.hora_entrada,
        hora_salida=sol.hora_salida,
        justificacion=sol.justificacion,
        evidencia_url=sol.evidencia_url,
        observacion=sol.observacion,
        reposicion_tiempo=sol.reposicion_tiempo,
        estado=sol.estado,
        marcacion_entrada_id=sol.marcacion_entrada_id,
        marcacion_salida_id=sol.marcacion_salida_id,
        creado_en=sol.creado_en,
        actualizado_en=sol.actualizado_en,
        personal={
            "id": sol.personal.id,
            "documento": sol.personal.documento,
            "nombres": sol.personal.nombres,
            "apellidos": sol.personal.apellidos,
        },
    )

# ---------- Crear marcaciones asociadas cuando se aprueba una solicitud ----------
def crear_marcaciones_para_solicitud(db: Session, sol: SolicitudPermiso) -> None:
    """
    Genera marcaciones de entrada y salida con los datos de la solicitud, asigna sus IDs
    a la solicitud y marca ambas como aprobadas.
    """
    # Crear marcación de entrada si hay hora_entrada
    if sol.hora_entrada:
        fecha_hora_ent = datetime.combine(sol.fecha_permiso, sol.hora_entrada)
        m_ent = marc_repo.create(db, {
            "personal_id": sol.personal_id,
            "tipo": "entrada",
            "fecha_hora": fecha_hora_ent,
            "justificacion": sol.justificacion,
            "evidencia_url": sol.evidencia_url,
            "aprobado": True,
        })
        sol.marcacion_entrada_id = m_ent.id
    # Crear marcación de salida si hay hora_salida
    if sol.hora_salida:
        fecha_hora_sal = datetime.combine(sol.fecha_permiso, sol.hora_salida)
        m_sal = marc_repo.create(db, {
            "personal_id": sol.personal_id,
            "tipo": "salida",
            "fecha_hora": fecha_hora_sal,
            "justificacion": sol.justificacion,
            "evidencia_url": sol.evidencia_url,
            "aprobado": True,
        })
        sol.marcacion_salida_id = m_sal.id
