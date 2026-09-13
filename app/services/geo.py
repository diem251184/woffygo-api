"""Servicio geoespacial de Woffy Go.

Usa PostGIS a traves de SQLAlchemy para:
- Guardar la ubicacion actual de un paseador.
- Buscar paseadores dentro de un radio (en km).
- Calcular distancias reales sobre la superficie terrestre.
"""
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKTElement
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.walker_profile import WalkerProfile


def _make_point(latitude: float, longitude: float) -> WKTElement:
    """Crea un POINT de PostGIS en SRID 4326.

    OJO: el orden es (longitud latitud), no (latitud longitud).
    """
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def update_walker_location(
    db: Session,
    walker_profile: WalkerProfile,
    latitude: float,
    longitude: float,
) -> WalkerProfile:
    walker_profile.current_location = _make_point(latitude, longitude)
    walker_profile.last_location_update = datetime.now(timezone.utc)
    db.commit()
    db.refresh(walker_profile)
    return walker_profile


def set_walker_online(
    db: Session,
    walker_profile: WalkerProfile,
    is_online: bool,
) -> WalkerProfile:
    walker_profile.is_online = is_online
    db.commit()
    db.refresh(walker_profile)
    return walker_profile


def find_nearby_walkers(
    db: Session,
    latitude: float,
    longitude: float,
    radius_km: float,
    limit: int = 20,
) -> list[dict]:
    """Busca paseadores online dentro de un radio (km).

    Devuelve lista de dicts con la info del paseador y la distancia real
    en km calculada por PostGIS.
    """
    origin = _make_point(latitude, longitude)
    radius_m = radius_km * 1000.0

    distance_col = func.ST_Distance(
        WalkerProfile.current_location,
        origin,
    ).label("distance_m")

    geom_expr = cast(WalkerProfile.current_location, Geometry)

    stmt = (
        select(
            WalkerProfile.id.label("walker_id"),
            User.id.label("user_id"),
            User.full_name.label("full_name"),
            WalkerProfile.hourly_rate.label("hourly_rate"),
            WalkerProfile.rating_avg.label("rating_avg"),
            WalkerProfile.total_walks.label("total_walks"),
            distance_col,
            func.ST_Y(geom_expr).label("latitude"),
            func.ST_X(geom_expr).label("longitude"),
        )
        .join(User, User.id == WalkerProfile.user_id)
        .where(WalkerProfile.is_online.is_(True))
        .where(User.is_active.is_(True))
        .where(User.role == UserRole.WALKER)
        .where(WalkerProfile.current_location.is_not(None))
        .where(func.ST_DWithin(WalkerProfile.current_location, origin, radius_m))
        .order_by(distance_col.asc())
        .limit(limit)
    )

    rows = db.execute(stmt).all()

    return [
        {
            "walker_id": r.walker_id,
            "user_id": r.user_id,
            "full_name": r.full_name,
            "hourly_rate": r.hourly_rate,
            "rating_avg": r.rating_avg,
            "total_walks": r.total_walks,
            "distance_km": round(r.distance_m / 1000.0, 3),
            "latitude": r.latitude,
            "longitude": r.longitude,
        }
        for r in rows
    ]