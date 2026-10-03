from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.safety_report import SafetyReport, SafetyCategory
from app.schemas.safety_report import SafetyReportCreate, SafetyReportResponse


router = APIRouter(prefix="/safety-reports", tags=["safety-reports"])

EXPIRATION_DAYS = 30


def _to_response(db: Session, r: SafetyReport) -> SafetyReportResponse:
    name = "Usuario"
    try:
        u = db.get(User, r.reporter_id)
        if u is not None:
            name = u.full_name
    except Exception:
        pass
    return SafetyReportResponse(
        id=r.id,
        category=r.category,
        description=r.description,
        latitude=r.latitude,
        longitude=r.longitude,
        verified=r.verified,
        created_at=r.created_at,
        expires_at=r.expires_at,
        reporter_id=r.reporter_id,
        reporter_name=name,
        reporter_role=r.reporter_role,
        walk_id=r.walk_id,
    )


@router.post("", response_model=SafetyReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: SafetyReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crea un reporte de seguridad. Cualquier usuario logueado puede reportar."""
    now = datetime.now(timezone.utc)
    report = SafetyReport(
        reporter_id=current_user.id,
        reporter_role=current_user.role.value,
        walk_id=payload.walk_id,
        category=payload.category,
        description=payload.description,
        latitude=payload.latitude,
        longitude=payload.longitude,
        expires_at=now + timedelta(days=EXPIRATION_DAYS),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _to_response(db, report)


@router.get("/nearby", response_model=list[SafetyReportResponse])
def list_nearby(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(default=5.0, ge=0.5, le=50.0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista reportes activos (no vencidos, no eliminados) dentro del radio.

    Filtra por distancia usando Haversine aproximado (suficiente para radio chico).
    """
    now = datetime.now(timezone.utc)

    # Bounding box rapido antes del filtro exacto
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * max(0.1, abs(__import__("math").cos(__import__("math").radians(lat)))))

    q = (
        db.query(SafetyReport)
        .filter(SafetyReport.deleted.is_(False))
        .filter(SafetyReport.expires_at > now)
        .filter(SafetyReport.latitude >= lat - lat_delta)
        .filter(SafetyReport.latitude <= lat + lat_delta)
        .filter(SafetyReport.longitude >= lng - lng_delta)
        .filter(SafetyReport.longitude <= lng + lng_delta)
        .order_by(SafetyReport.created_at.desc())
        .limit(200)
    )

    import math

    def haversine_km(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return 2 * R * math.asin(math.sqrt(a))

    results = []
    for r in q.all():
        if haversine_km(lat, lng, r.latitude, r.longitude) <= radius_km:
            results.append(_to_response(db, r))
    return results
