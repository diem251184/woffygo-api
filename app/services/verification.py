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

# --- Filtros de calidad GPS ---
MAX_ACCURACY_METERS = 50.0
MAX_REPORTED_SPEED_KMH = 20.0
MIN_SEGMENT_METERS = 1.5
MAX_SEGMENT_METERS = 200.0
MAX_IMPLIED_SPEED_KMH = 20.0


def _calculate_distance_meters(db: Session, walk_id: int) -> float:
    """Calcula la distancia geodeca total de la ruta en metros.

    Filtra puntos y segmentos para evitar que GPS impreciso infle la distancia.
    """
    sql = text(
        """
        WITH filtered_points AS (
            SELECT
                location,
                recorded_at,
                LAG(location) OVER (ORDER BY recorded_at) AS prev_location,
                LAG(recorded_at) OVER (ORDER BY recorded_at) AS prev_recorded_at
            FROM walk_locations
            WHERE walk_id = :walk_id
              AND (accuracy_meters IS NULL OR accuracy_meters <= :max_accuracy)
              AND (speed_kmh IS NULL OR speed_kmh <= :max_reported_speed)
        ),
        segments AS (
            SELECT
                ST_Distance(
                    CAST(location AS geography),
                    CAST(prev_location AS geography)
                ) AS seg_m,
                EXTRACT(EPOCH FROM (recorded_at - prev_recorded_at)) AS seg_s
            FROM filtered_points
            WHERE prev_location IS NOT NULL
        )
        SELECT COALESCE(SUM(seg_m), 0) AS distance_m
        FROM segments
        WHERE seg_m >= :min_segment
          AND seg_m <= :max_segment
          AND (
              seg_s IS NULL
              OR seg_s <= 0
              OR (seg_m / seg_s) * 3.6 <= :max_implied_speed
          )
        """
    )
    result = db.execute(
        sql,
        {
            "walk_id": walk_id,
            "max_accuracy": MAX_ACCURACY_METERS,
            "max_reported_speed": MAX_REPORTED_SPEED_KMH,
            "min_segment": MIN_SEGMENT_METERS,
            "max_segment": MAX_SEGMENT_METERS,
            "max_implied_speed": MAX_IMPLIED_SPEED_KMH,
        },
    ).scalar()
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