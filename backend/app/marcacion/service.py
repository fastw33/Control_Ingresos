# app/marcacion/service.py
from typing import Optional, List, Tuple, Literal
from datetime import datetime, timezone, timedelta
import numpy as np

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.marcacion import repository as repo
from app.marcacion.schema import (
    MarcacionWithPersonalOut,
    MarcacionRegistrarOut,
    MarcacionAutoOut,
)
from app.marcacion.model import Marcacion
from app.vectores.service import UMBRAL_COSENO as DEFAULT_UMBRAL_COSINE

# Tipos permitidos (capa de servicio valida esto)
_ALLOWED_TYPES = {"entrada", "salida", "on_almuerzo", "off_almuerzo"}

# ────────────────────────────────────────────────────────────────────
#  Zonas horarias (robusto en Windows sin tzdata) → Bogotá fija UTC-5
# ────────────────────────────────────────────────────────────────────
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        BOGOTA = ZoneInfo("America/Bogota")
    except ZoneInfoNotFoundError:
        # Fallback fijo (Colombia no usa DST)
        BOGOTA = timezone(timedelta(hours=-5))
except Exception:
    BOGOTA = timezone(timedelta(hours=-5))

UTC = timezone.utc

# ---------- Helpers (biometría en memoria, sin persistir) ----------
def _embedding_from_upload(file) -> Optional[np.ndarray]:
    """
    Extrae la incrustación facial del archivo utilizando InsightFace.
    - No persiste el archivo.
    """
    from app.vectores.service import _embedding_from_upload as _enc_util
    return _enc_util(file)

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na = a / (np.linalg.norm(a) + 1e-12)
    nb = b / (np.linalg.norm(b) + 1e-12)
    return float(np.dot(na, nb))

def _best_similarity_vs_list(query_vec: np.ndarray, vectors: List[np.ndarray]) -> Tuple[float, int]:
    sims = [_cosine_sim(query_vec, v) for v in vectors]
    best_idx = int(np.argmax(sims))
    return float(sims[best_idx]), best_idx

# ────────────────────────────────────────────────────────────────────
#  Helpers fecha/hora → TRABAJAMOS TODO EN BOGOTÁ (UTC-5)
# ────────────────────────────────────────────────────────────────────
def _ensure_aware(dt: datetime, assume_tz=BOGOTA) -> datetime:
    """
    Asegura datetime aware. Si viene naive, le inyecta assume_tz (Bogotá).
    """
    if dt is None:
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=assume_tz)
    return dt

def _to_bogota(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convierte cualquier datetime a zona Bogotá.
    - Si viene naive (sin tz) asumimos que ya está en hora Bogotá.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Ya es hora local almacenada como naive → interpretar como Bogotá
        return dt.replace(tzinfo=BOGOTA)
    return dt.astimezone(BOGOTA)

def _parse_iso_to_bogota(s: str, fallback_tz) -> Optional[datetime]:
    """
    Acepta 'YYYY-MM-DDTHH:MM[:SS][±HH:MM]'.
    - Si viene sin tz, asumimos fallback_tz (Bogotá por defecto)
    - Devuelve timezone-aware en Bogotá
    """
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=fallback_tz)
        return dt.astimezone(BOGOTA)
    except Exception:
        return None

def _compose_from_date_time_to_bogota(d: str, t: str, tz) -> Optional[datetime]:
    """
    d: 'YYYY-MM-DD', t: 'HH:MM' o 'HH:MM:SS'
    Retorna timezone-aware en Bogotá
    """
    try:
        y, m, d_ = map(int, d.split("-"))
        parts = list(map(int, t.split(":")))
        hh, mm = parts[0], parts[1]
        ss = parts[2] if len(parts) > 2 else 0
        local_dt = datetime(y, m, d_, hh, mm, ss, tzinfo=tz)
        return local_dt.astimezone(BOGOTA)
    except Exception:
        return None

def _resolve_target_dt_bogota(
    *,
    usar_manual: bool,
    tz_name: Optional[str],
    fecha_hora_manual: Optional[str] = None,
    fecha_hora: Optional[str] = None,
    fechaHora: Optional[str] = None,
    fechaHoraManual: Optional[str] = None,
    fecha_manual: Optional[str] = None,
    hora_manual: Optional[str] = None,
    fecha: Optional[str] = None,
    hora: Optional[str] = None,
) -> datetime:
    """
    Resuelve la datetime objetivo en BOGOTÁ (aware). 
    Si la columna en DB es DATETIME (naive), guardaremos sin tzinfo.
    """
    try:
        tzinfo = ZoneInfo(tz_name) if tz_name else BOGOTA
    except Exception:
        tzinfo = BOGOTA

    if usar_manual:
        # 1) Intentar cualquier ISO completo
        for iso in (fecha_hora_manual, fecha_hora, fechaHora, fechaHoraManual):
            if iso:
                dt_loc = _parse_iso_to_bogota(iso, tzinfo)
                if dt_loc:
                    return dt_loc

        # 2) Intentar con pares fecha/hora (acepta alias)
        d = fecha_manual or fecha
        h = hora_manual or hora
        if d and h:
            dt_loc = _compose_from_date_time_to_bogota(d, h, tzinfo)
            if dt_loc:
                return dt_loc

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fecha/hora manual inválida.")
    else:
        # Ahora en Bogotá
        return datetime.now(tz=BOGOTA)

def _aware_bogota_to_naive(dt_bog: datetime) -> datetime:
    """
    Convierte un datetime aware (Bogotá) a naive (quita tzinfo) para persistir
    exactamente la hora local en DB (cuando columnas son DATETIME).
    """
    return dt_bog.replace(tzinfo=None)

# ---------- Listado con datos de personal ----------
def listar_con_personal(
    db: Session,
    *,
    limit: int = 100,
    offset: int = 0,
    tipo: Optional[str] = None,
    personal_id: Optional[int] = None,
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    include_evidencia_url: bool = False,
) -> List[MarcacionWithPersonalOut]:
    rows = repo.list_with_personal(
        db,
        limit=limit,
        offset=offset,
        tipo=tipo,
        personal_id=personal_id,
        desde=desde,
        hasta=hasta,
    )
    out: List[MarcacionWithPersonalOut] = []
    for r in rows:
        # Normalizamos a Bogotá (tratando naive como Bogotá)
        fh_bog = _to_bogota(r.fecha_hora)
        creado_bog = _to_bogota(r.creado_en)

        out.append(
            MarcacionWithPersonalOut(
                id=r.id,
                personal_id=r.personal_id,  # ← añadido
                tipo=r.tipo,
                fecha_hora=fh_bog,
                dispositivo=r.dispositivo,
                observacion=r.observacion,
                justificacion=r.justificacion,
                evidencia_url=(r.evidencia_url if include_evidencia_url else None),
                aprobado=r.aprobado,
                creado_en=creado_bog,
                personal={
                    "id": r.personal_id,
                    "documento": r.documento,
                    "nombres": r.nombres,
                    "apellidos": r.apellidos,
                },
            )
        )
    return out

# ---------- Registrar con personal_id ----------
def registrar_con_personal(
    db: Session,
    *,
    personal_id: int,
    file,
    tipo: Optional[str] = None,
    # Nuevos params de control horario
    usar_manual: bool = False,
    tz: Optional[str] = None,
    fecha_hora_manual: Optional[str] = None,
    fecha_hora: Optional[str] = None,
    fechaHora: Optional[str] = None,
    fechaHoraManual: Optional[str] = None,
    fecha_manual: Optional[str] = None,
    hora_manual: Optional[str] = None,
    fecha: Optional[str] = None,
    hora: Optional[str] = None,
    # Ignorados en creación
    justificacion: Optional[str] = None,
    evidencia_url: Optional[str] = None,
    aprobado: Optional[bool] = None,
    umbral: Optional[float] = None,
) -> MarcacionRegistrarOut:
    if tipo not in _ALLOWED_TYPES:
        return MarcacionRegistrarOut(
            match=False, score=0.0,
            umbral=float(umbral or DEFAULT_UMBRAL_COSINE),
            mejor_vector=0, registrado=False,
            mensaje="Tipo de marcación inválido",
        )

    row = repo.get_vectors_for_person(db, personal_id)
    if not row:
        return MarcacionRegistrarOut(
            match=False, score=0.0,
            umbral=float(umbral or DEFAULT_UMBRAL_COSINE),
            mejor_vector=0, registrado=False,
            mensaje="Personal sin vectores o no existe",
        )

    query_vec = _embedding_from_upload(file)
    if query_vec is None:
        return MarcacionRegistrarOut(
            match=False, score=0.0,
            umbral=float(umbral or DEFAULT_UMBRAL_COSINE),
            mejor_vector=0, registrado=False,
            mensaje="No se detectó rostro en la imagen",
        )

    stored = [
        v for v in [
            np.frombuffer(row.vector1, dtype=np.float32) if row.vector1 is not None else None,
            np.frombuffer(row.vector2, dtype=np.float32) if row.vector2 is not None else None,
            np.frombuffer(row.vector3, dtype=np.float32) if row.vector3 is not None else None,
            np.frombuffer(row.vector4, dtype=np.float32) if row.vector4 is not None else None,
            np.frombuffer(row.vector5, dtype=np.float32) if row.vector5 is not None else None,
        ] if v is not None
    ]
    if not stored:
        return MarcacionRegistrarOut(
            match=False, score=0.0,
            umbral=float(umbral or DEFAULT_UMBRAL_COSINE),
            mejor_vector=0, registrado=False,
            mensaje="No hay vectores válidos para este personal",
        )

    stored = [(v / (np.linalg.norm(v) + 1e-12)).astype(np.float32) for v in stored]
    query_vec = (query_vec / (np.linalg.norm(query_vec) + 1e-12)).astype(np.float32)

    dim_q = int(query_vec.size)
    if any(int(v.size) != dim_q for v in stored):
        return MarcacionRegistrarOut(
            match=False, score=0.0,
            umbral=float(umbral or DEFAULT_UMBRAL_COSINE),
            mejor_vector=0, registrado=False,
            mensaje="Vectores incompatibles (dimensiones distintas). Re-registra vectores.",
        )

    best_sim, best_idx = _best_similarity_vs_list(query_vec, stored)
    threshold = float(umbral or DEFAULT_UMBRAL_COSINE)
    is_match = bool(best_sim >= threshold)

    registrado = False
    marc_id = None
    ts_loc = None

    if is_match:
        # === RESOLVER FECHA/HORA EN BOGOTÁ ===
        ts_loc = _resolve_target_dt_bogota(
            usar_manual=usar_manual,
            tz_name=tz,
            fecha_hora_manual=fecha_hora_manual,
            fecha_hora=fecha_hora,
            fechaHora=fechaHora,
            fechaHoraManual=fechaHoraManual,
            fecha_manual=fecha_manual,
            hora_manual=hora_manual,
            fecha=fecha,
            hora=hora,
        )

        # Guardar como NAIVE (DB con time_zone='-05:00' → exacto Bogotá)
        obj = repo.create(db, {
            "personal_id": row.personal_id,
            "tipo": tipo,
            "fecha_hora": _aware_bogota_to_naive(ts_loc),
        })
        db.commit()
        registrado = True
        marc_id = obj.id

    # Responder en hora Bogotá (legible)
    fecha_hora_bog = _to_bogota(ts_loc)

    return MarcacionRegistrarOut(
        match=is_match,
        score=best_sim,
        umbral=threshold,
        mejor_vector=best_idx + 1 if is_match else 0,
        registrado=registrado,
        marcacion_id=marc_id,
        fecha_hora=fecha_hora_bog,
        mensaje="ok" if is_match else "no match",
    )

# ---------- Reconocimiento automático ----------
def auto_reconocer_y_registrar(
    db: Session,
    *,
    file,
    tipo: Optional[str] = None,
    # Nuevos params de control horario
    usar_manual: bool = False,
    tz: Optional[str] = None,
    fecha_hora_manual: Optional[str] = None,
    fecha_hora: Optional[str] = None,
    fechaHora: Optional[str] = None,
    fechaHoraManual: Optional[str] = None,
    fecha_manual: Optional[str] = None,
    hora_manual: Optional[str] = None,
    fecha: Optional[str] = None,
    hora: Optional[str] = None,
    # Ignorados en creación
    justificacion: Optional[str] = None,
    evidencia_url: Optional[str] = None,
    aprobado: Optional[bool] = None,
    umbral: Optional[float] = None,
) -> MarcacionAutoOut:
    if tipo not in _ALLOWED_TYPES:
        return MarcacionAutoOut(
            match=False, score=0.0,
            umbral=float(umbral or DEFAULT_UMBRAL_COSINE),
            registrado=False, mensaje="Tipo de marcación inválido",
        )

    query_vec = _embedding_from_upload(file)
    if query_vec is None:
        return MarcacionAutoOut(
            match=False, score=0.0,
            umbral=float(umbral or DEFAULT_UMBRAL_COSINE),
            registrado=False, mensaje="No se detectó rostro en la imagen",
        )

    rows = repo.fetch_all_vectors_joined(db)
    if not rows:
        return MarcacionAutoOut(
            match=False, score=0.0,
            umbral=float(umbral or DEFAULT_UMBRAL_COSINE),
            registrado=False, mensaje="No hay personal con vectores registrados",
        )

    query_vec = (query_vec / (np.linalg.norm(query_vec) + 1e-12)).astype(np.float32)

    global_best_sim = -1.0
    global_best_idx = 0
    global_best_row = None

    for r in rows:
        vectors = [
            v for v in [
                np.frombuffer(r.vector1, dtype=np.float32) if r.vector1 is not None else None,
                np.frombuffer(r.vector2, dtype=np.float32) if r.vector2 is not None else None,
                np.frombuffer(r.vector3, dtype=np.float32) if r.vector3 is not None else None,
                np.frombuffer(r.vector4, dtype=np.float32) if r.vector4 is not None else None,
                np.frombuffer(r.vector5, dtype=np.float32) if r.vector5 is not None else None,
            ] if v is not None
        ]
        if not vectors:
            continue

        vectors = [(v / (np.linalg.norm(v) + 1e-12)).astype(np.float32) for v in vectors]
        if any(int(v.size) != int(query_vec.size) for v in vectors):
            continue

        best_sim, best_idx = _best_similarity_vs_list(query_vec, vectors)
        if best_sim > global_best_sim:
            global_best_sim = best_sim
            global_best_idx = best_idx
            global_best_row = r

    threshold = float(umbral or DEFAULT_UMBRAL_COSINE)
    is_match = bool(global_best_sim >= threshold)

    registrado = False
    marc_id = None
    ts_loc = None

    if is_match and global_best_row is not None:
        # === RESOLVER FECHA/HORA EN BOGOTÁ ===
        ts_loc = _resolve_target_dt_bogota(
            usar_manual=usar_manual,
            tz_name=tz,
            fecha_hora_manual=fecha_hora_manual,
            fecha_hora=fecha_hora,
            fechaHora=fechaHora,
            fechaHoraManual=fechaHoraManual,
            fecha_manual=fecha_manual,
            hora_manual=hora_manual,
            fecha=fecha,
            hora=hora,
        )

        obj = repo.create(db, {
            "personal_id": global_best_row.personal_id,
            "tipo": tipo,
            "fecha_hora": _aware_bogota_to_naive(ts_loc),
        })
        db.commit()
        registrado = True
        marc_id = obj.id

    fecha_hora_bog = _to_bogota(ts_loc)

    return MarcacionAutoOut(
        match=is_match,
        score=global_best_sim,
        umbral=threshold,
        mejor_vector=(global_best_idx + 1) if is_match else None,
        personal_id=global_best_row.personal_id if is_match else None,
        documento=global_best_row.documento if is_match else None,
        nombres=global_best_row.nombres if is_match else None,
        apellidos=global_best_row.apellidos if is_match else None,
        registrado=registrado,
        marcacion_id=marc_id,
        fecha_hora=fecha_hora_bog,
        mensaje="ok" if is_match else "no match",
    )

# ---------- Actualizar una marcación existente ----------
def actualizar_marcacion(
    db: Session,
    marcacion_id: int,
    *,
    justificacion: Optional[str] = None,
    evidencia_url: Optional[str] = None,
    observacion: Optional[str] = None,
    aprobado: Optional[bool] = None,
) -> MarcacionWithPersonalOut:
    """
    Actualiza campos opcionales de una marcación existente.
    """
    marc = db.get(Marcacion, marcacion_id)
    if not marc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marcación no encontrada")

    if justificacion is not None:
        marc.justificacion = justificacion[:500] if justificacion is not None else None
    if evidencia_url is not None:
        marc.evidencia_url = evidencia_url[:255]
    if observacion is not None:
        marc.observacion = observacion[:255] if observacion is not None else None
    if aprobado is not None:
        marc.aprobado = bool(aprobado)

    db.commit()
    db.refresh(marc)

    # Normalizamos salida a Bogotá
    return MarcacionWithPersonalOut(
        id=marc.id,
        personal_id=marc.personal_id,  # ← añadido
        tipo=marc.tipo,
        fecha_hora=_to_bogota(marc.fecha_hora),
        dispositivo=marc.dispositivo,
        observacion=marc.observacion,
        justificacion=marc.justificacion,
        evidencia_url=marc.evidencia_url,
        aprobado=marc.aprobado,
        creado_en=_to_bogota(marc.creado_en),
        personal={
            "id": marc.personal_id,
            "documento": marc.personal.documento,
            "nombres": marc.personal.nombres,
            "apellidos": marc.personal.apellidos,
        },
    )

# ---------- Actualizar SOLO la fecha/hora efectiva (creado_en) ----------
def actualizar_fecha_hora(
    db: Session,
    marcacion_id: int,
    *,
    usar_manual: bool,
    tz: Optional[str] = None,
    fecha_hora_manual: Optional[str] = None,
    fecha_hora: Optional[str] = None,
    fechaHora: Optional[str] = None,
    fechaHoraManual: Optional[str] = None,
    fecha_manual: Optional[str] = None,
    hora_manual: Optional[str] = None,
    fecha: Optional[str] = None,
    hora: Optional[str] = None,
) -> MarcacionWithPersonalOut:
    marc = db.get(Marcacion, marcacion_id)
    if not marc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marcación no encontrada")

    # Debe estar aprobada para permitir el cambio
    if not bool(marc.aprobado):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Marcación no aprobada")

    # Resolver la fecha/hora objetivo en Bogotá (aware)
    ts_loc = _resolve_target_dt_bogota(
        usar_manual=usar_manual,
        tz_name=tz,
        fecha_hora_manual=fecha_hora_manual,
        fecha_hora=fecha_hora,
        fechaHora=fechaHora,
        fechaHoraManual=fechaHoraManual,
        fecha_manual=fecha_manual,
        hora_manual=hora_manual,
        fecha=fecha,
        hora=hora,
    )

    # Actualiza SOLO creado_en con hora local Bogotá (naive)
    marc.creado_en = _aware_bogota_to_naive(ts_loc)
    db.commit()
    db.refresh(marc)

    return MarcacionWithPersonalOut(
        id=marc.id,
        personal_id=marc.personal_id,  # ← añadido
        tipo=marc.tipo,
        fecha_hora=_to_bogota(marc.fecha_hora),
        dispositivo=marc.dispositivo,
        observacion=marc.observacion,
        justificacion=marc.justificacion,
        evidencia_url=marc.evidencia_url,
        aprobado=marc.aprobado,
        creado_en=_to_bogota(marc.creado_en),
        personal={
            "id": marc.personal_id,
            "documento": marc.personal.documento,
            "nombres": marc.personal.nombres,
            "apellidos": marc.personal.apellidos,
        },
    )
