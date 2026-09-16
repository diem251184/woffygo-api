from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.elements import WKTElement
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.walk import Walk, WalkStatus
from app.models.walk_location import WalkLocation
from app.schemas.walk import (
    WalkCancelRequest,
    WalkCreate,
    WalkLocationCreate,
    WalkLocationDetail,
    WalkLocationResponse,
    WalkResponse,
)
from app.services.walks import (
    accept_walk,
    cancel_walk,
    create_walk,
    finish_walk,
    get_latest_walk_location,
    list_available_walks,
    list_walk_locations,
    list_walks_for_user,
    start_walk,
)


router = APIRouter(prefix="/walks", tags=["walks"])


def _get_walk_or_404(db: Session, walk_id: int) -> Walk:
    walk = db.get(Walk, walk_id)
    if walk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paseo no encontrado",
        )
    return walk


@router.post("", response_model=WalkResponse, status_code=status.HTTP_201_CREATED)
def create(
    payload: WalkCreate,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    return create_walk(db, current_user, payload)


@router.get("", response_model=list[WalkResponse])
def list_mine(
    status_filter: WalkStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_walks_for_user(db, current_user, status_filter)


@router.get("/available", response_model=list[WalkResponse])
def list_available(
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    return list_available_walks(db)


def _attach_pickup_coords(db: Session, walk: Walk) -> None:
    """Carga pickup_latitude/longitude en el objeto Walk (via PostGIS)."""
    sql = text(
        "SELECT ST_Y(CAST(pickup_location AS geometry)) AS lat, "
        "ST_X(CAST(pickup_location AS geometry)) AS lon "
        "FROM walks WHERE id = :id"
    )
    row = db.execute(sql, {"id": walk.id}).first()
    if row is not None:
        walk._pickup_latitude = float(row.lat) if row.lat is not None else None
        walk._pickup_longitude = float(row.lon) if row.lon is not None else None


@router.get("/{walk_id}", response_model=WalkResponse)
def get_one(
    walk_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    walk = _get_walk_or_404(db, walk_id)

    is_owner = walk.owner_id == current_user.id
    is_walker = walk.walker_id == current_user.id
    is_admin = current_user.role == UserRole.ADMIN
    is_pending_open = walk.status == WalkStatus.PENDING

    if not (is_owner or is_walker or is_admin or is_pending_open):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenes acceso a este paseo",
        )
    _attach_pickup_coords(db, walk)
    return walk


@router.post("/{walk_id}/accept", response_model=WalkResponse)
def accept(
    walk_id: int,
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    return accept_walk(db, current_user, walk_id)


@router.post("/{walk_id}/start", response_model=WalkResponse)
def start(
    walk_id: int,
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    return start_walk(db, current_user, walk_id)


@router.post("/{walk_id}/location", response_model=WalkLocationResponse, status_code=status.HTTP_201_CREATED)
def add_location(
    walk_id: int,
    payload: WalkLocationCreate,
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    walk = _get_walk_or_404(db, walk_id)

    if walk.walker_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No estas asignado a este paseo",
        )
    if walk.status != WalkStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se puede reportar ubicacion en paseos en proceso. Estado: {walk.status.value}",
        )

    location = WalkLocation(
        walk_id=walk.id,
        location=WKTElement(f"POINT({payload.longitude} {payload.latitude})", srid=4326),
        accuracy_meters=payload.accuracy_meters,
        speed_kmh=payload.speed_kmh,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.post("/{walk_id}/finish", response_model=WalkResponse)
def finish(
    walk_id: int,
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    return finish_walk(db, current_user, walk_id)


@router.post("/{walk_id}/cancel", response_model=WalkResponse)
def cancel(
    walk_id: int,
    payload: WalkCancelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return cancel_walk(db, current_user, walk_id, payload.reason)

@router.get("/{walk_id}/locations", response_model=list[WalkLocationDetail])
def get_walk_locations(
    walk_id: int,
    limit: int = Query(default=500, ge=1, le=2000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_walk_locations(db, walk_id, current_user, limit)


@router.get("/{walk_id}/locations/latest", response_model=WalkLocationDetail | None)
def get_walk_latest_location(
    walk_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_latest_walk_location(db, walk_id, current_user)

