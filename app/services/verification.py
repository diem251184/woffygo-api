"""Verificacion de integridad de paseos."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.walk import Walk
from app.models.walk_location import WalkLocation


MIN_DISTANCE_METERS = 200.0
MIN_DURATION_RATIO = 0.01
MAX_AVG_SPEED_KMH = 15.0
MIN_AVG_SPEED_KMH = 0.5


def _calculate_distance_meters(db: Session, walk_id: int) -> float:
    """Calcula la distancia geodeca total de la ruta en metros.

    Usa SQL crudo con text() para evitar las conversiones automaticas de
    GeoAlchemy2 que transforman el resultado de ST_MakeLine a WKB binario
    (rompiendo ST_GeogFromText que espera WKT).

    El CAST a geography es lo que hace que ST_Length devuelva metros en
    lugar de grados (para SRID 4326).
    """
    sql = text(
        """
        SELECT ST_Length(
            CAST(
                ST_MakeLine(CAST(location AS geometry) ORDER BY recorded_at)
                AS geography
            )
        ) AS distance_m
        FROM walk_locations
        WHERE walk_id = :walk_id
        """
    )
    result = db.execute(sql, {"walk_id": walk_id}).scalar()
    if result is None:
        return 0.0
    return float(result)


def verify_walk_integrity(db: Session, walk: Walk) -> Walk:
    if walk.started_at is None or walk.finished_at is None:
        walk.flagged_for_review = True
        walk.flag_reason = "Faltan timestamps de inicio o fin"
        db.commit()
        db.refresh(walk)
        return walk

    distance_m = _calculate_distance_meters(db, walk.id)
    walk.distance_meters = Decimal(str(round(distance_m, 2)))

    duration_real_min = (walk.finished_at - walk.started_at).total_seconds() / 60.0
    duration_expected_min = float(walk.duration_minutes)
    ratio = duration_real_min / duration_expected_min if duration_expected_min > 0 else 0.0

    avg_speed_kmh = 0.0
    if duration_real_min > 0:
        avg_speed_kmh = (distance_m / 1000.0) / (duration_real_min / 60.0)

    reasons: list[str] = []

    if distance_m < MIN_DISTANCE_METERS:
        reasons.append(
            f"Distancia muy corta: {distance_m:.0f}m (minimo {MIN_DISTANCE_METERS:.0f}m)"
        )

    if ratio < MIN_DURATION_RATIO:
        reasons.append(
            f"Duracion real muy baja: {duration_real_min:.1f}min de {duration_expected_min:.0f}min"
        )

    if avg_speed_kmh > MAX_AVG_SPEED_KMH:
        reasons.append(
            f"Velocidad promedio sospechosa: {avg_speed_kmh:.1f} km/h (max {MAX_AVG_SPEED_KMH:.0f})"
        )

    if distance_m >= MIN_DISTANCE_METERS and avg_speed_kmh < MIN_AVG_SPEED_KMH:
        reasons.append(
            f"Velocidad promedio muy baja: {avg_speed_kmh:.1f} km/h (min {MIN_AVG_SPEED_KMH})"
        )

    if reasons:
        walk.flagged_for_review = True
        walk.flag_reason = " | ".join(reasons)[:500]
    else:
        walk.flagged_for_review = False
        walk.flag_reason = None

    db.commit()
    db.refresh(walk)
    return walk


def get_verification_summary(walk: Walk) -> dict:
    if walk.started_at is None or walk.finished_at is None:
        return {
            "distance_meters": None,
            "duration_real_minutes": None,
            "avg_speed_kmh": None,
            "flagged": walk.flagged_for_review,
            "reason": walk.flag_reason,
        }

    duration_min = (walk.finished_at - walk.started_at).total_seconds() / 60.0
    distance_m = float(walk.distance_meters) if walk.distance_meters is not None else 0.0
    speed = (distance_m / 1000.0) / (duration_min / 60.0) if duration_min > 0 else 0.0

    return {
        "distance_meters": round(distance_m, 2),
        "duration_real_minutes": round(duration_min, 2),
        "avg_speed_kmh": round(speed, 2),
        "flagged": walk.flagged_for_review,
        "reason": walk.flag_reason,
    }