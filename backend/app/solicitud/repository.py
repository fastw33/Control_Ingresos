# app/solicitud/repository.py
from typing import Optional, List
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.solicitud.model import SolicitudPermiso
from app.personal.model import Personal


def create(db: Session, data: dict) -> SolicitudPermiso:
    """
    Crea una nueva solicitud de permiso en la base de datos.
    """
    obj = SolicitudPermiso(**data)
    db.add(obj)
    db.flush()
    db.refresh(obj)
    return obj


def get(db: Session, solicitud_id: int) -> Optional[SolicitudPermiso]:
    """
    Obtiene una solicitud por ID o devuelve None si no existe.
    """
    return db.get(SolicitudPermiso, solicitud_id)


def list_with_personal(
    db: Session,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
    estado: Optional[str] = None,
    personal_id: Optional[int] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
):
    """
    Lista solicitudes de permiso junto con datos básicos del personal.
    Permite filtrar por estado, por empleado y por rango de fechas.
    Devuelve los resultados como filas sin mapear; el servicio se encargará de transformarlos.
    """
    stmt = (
        select(
            SolicitudPermiso.id,
            SolicitudPermiso.personal_id,
            SolicitudPermiso.fecha_permiso,
            SolicitudPermiso.hora_entrada,
            SolicitudPermiso.hora_salida,
            SolicitudPermiso.justificacion,
            SolicitudPermiso.evidencia_url,
            SolicitudPermiso.observacion,
            SolicitudPermiso.reposicion_tiempo,
            SolicitudPermiso.estado,
            SolicitudPermiso.marcacion_entrada_id,
            SolicitudPermiso.marcacion_salida_id,
            SolicitudPermiso.creado_en,
            SolicitudPermiso.actualizado_en,
            Personal.documento,
            Personal.nombres,
            Personal.apellidos,
        )
        .join(Personal, Personal.id == SolicitudPermiso.personal_id)
    )

    conds = []
    if estado is not None:
        conds.append(SolicitudPermiso.estado == estado)
    if personal_id is not None:
        conds.append(SolicitudPermiso.personal_id == personal_id)
    if desde is not None:
        conds.append(SolicitudPermiso.fecha_permiso >= desde)
    if hasta is not None:
        conds.append(SolicitudPermiso.fecha_permiso <= hasta)

    if conds:
        stmt = stmt.where(and_(*conds))

    stmt = stmt.order_by(
        SolicitudPermiso.creado_en.desc(),
        SolicitudPermiso.id.desc(),
    )

    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)

    return db.execute(stmt).all()
