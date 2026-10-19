from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.elements import WKTElement
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.booking import Booking, BookingPet, BookingStatus, ServiceType
from app.models.walk_location import WalkLocation
from app.schemas.booking import (
    BookingCreate,
    BookingLocationCreate,
    BookingLocationDetail,
    BookingQuoteRequest,
    BookingQuoteResponse,
    BookingResponse,
    BookingStatusUpdateRequest,
)
from app.services.bookings import (
    accept_booking,
    calculate_quote,
    cancel_booking,
    create_booking,
    finish_booking,
    get_booking_or_404,
    start_booking,
)
from app.models.walker_profile import WalkerProfile

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _attach_extra_fields(db: Session, booking: Booking) -> None:
    sql = text(
        "SELECT ST_Y(CAST(pickup_location AS geometry)) AS lat, "
        "ST_X(CAST(pickup_location AS geometry)) AS lon "
        "FROM bookings WHERE id = :id"
    )
    row = db.execute(sql, {"id": booking.id}).first()
    if row is not None:
        booking._pickup_latitude = float(row.lat) if row.lat is not None else None
        booking._pickup_longitude = float(row.lon) if row.lon is not None else None


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create(
    payload: BookingCreate,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    booking = create_booking(db, current_user, payload)
    _attach_extra_fields(db, booking)
    return booking


@router.post("/quote", response_model=BookingQuoteResponse)
def quote(
    payload: BookingQuoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(WalkerProfile).filter(WalkerProfile.user_id == payload.provider_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    price, fee, earnings = calculate_quote(
        profile.hourly_rate,
        payload.duration_minutes,
        payload.num_pets,
        profile.total_walks,
    )
    return BookingQuoteResponse(
        price_total=price,
        platform_fee=fee,
        provider_earnings=earnings,
        currency="ARS",
    )


@router.get("", response_model=list[BookingResponse])
def list_mine(
    status_filter: BookingStatus | None = Query(default=None, alias="status"),
    service_type: ServiceType | None = Query(default=None, alias="type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Booking)
        .options(joinedload(Booking.booking_pets).joinedload(BookingPet.pet))
    )

    if current_user.role == UserRole.OWNER:
        query = query.filter(Booking.owner_id == current_user.id)
    elif current_user.role == UserRole.WALKER:
        query = query.filter(Booking.provider_id == current_user.id)

    if status_filter:
        query = query.filter(Booking.status == status_filter)
    if service_type:
        query = query.filter(Booking.service_type == service_type)

    bookings = query.order_by(Booking.created_at.desc()).all()
    for b in bookings:
        _attach_extra_fields(db, b)
    return bookings


@router.get("/available", response_model=list[BookingResponse])
def list_available(
    service_type: ServiceType = Query(default=ServiceType.WALK),
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    bookings = (
        db.query(Booking)
        .options(joinedload(Booking.booking_pets).joinedload(BookingPet.pet))
        .filter(Booking.status == BookingStatus.REQUESTED)
        .filter(Booking.provider_id.is_(None))
        .filter(Booking.service_type == service_type)
        .order_by(Booking.created_at.asc())
        .all()
    )
    for b in bookings:
        _attach_extra_fields(db, b)
    return bookings


@router.get("/{booking_id}", response_model=BookingResponse)
def get_one(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = (
        db.query(Booking)
        .options(joinedload(Booking.booking_pets).joinedload(BookingPet.pet))
        .filter(Booking.id == booking_id)
        .first()
    )
    if booking is None:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")

    is_owner = booking.owner_id == current_user.id
    is_provider = booking.provider_id == current_user.id
    is_admin = current_user.role == UserRole.ADMIN
    is_open = booking.status == BookingStatus.REQUESTED

    if not (is_owner or is_provider or is_admin or is_open):
        raise HTTPException(status_code=403, detail="Sin acceso a esta reserva")

    _attach_extra_fields(db, booking)
    return booking


@router.patch("/{booking_id}/status", response_model=BookingResponse)
def update_status(
    booking_id: int,
    payload: BookingStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.status == BookingStatus.ACCEPTED:
        b = accept_booking(db, current_user, booking_id)
    elif payload.status == BookingStatus.IN_PROGRESS:
        b = start_booking(db, current_user, booking_id)
    elif payload.status == BookingStatus.COMPLETED:
        b = finish_booking(db, current_user, booking_id)
    elif payload.status == BookingStatus.CANCELLED:
        b = cancel_booking(db, current_user, booking_id, payload.reason)
    else:
        raise HTTPException(status_code=400, detail="Acción no soportada para este estado")

    _attach_extra_fields(db, b)
    return b


@router.post("/{booking_id}/location", status_code=status.HTTP_201_CREATED)
def add_location(
    booking_id: int,
    payload: BookingLocationCreate,
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    booking = get_booking_or_404(db, booking_id)
    if booking.provider_id != current_user.id:
        raise HTTPException(status_code=403, detail="No asignado a esta reserva")
    if booking.status != BookingStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Solo se reporta ubicación en servicios en progreso")

    loc = WalkLocation(
        walk_id=booking.id,
        location=WKTElement(f"POINT({payload.longitude} {payload.latitude})", srid=4326),
        accuracy_meters=payload.accuracy_meters,
        speed_kmh=payload.speed_kmh,
    )
    db.add(loc)
    db.commit()
    return {"status": "ok"}
from geoalchemy2.functions import ST_X, ST_Y

import json
from sqlalchemy import func

@router.get("/{booking_id}/locations")
def get_booking_locations(
    booking_id: int,
    limit: int = 500,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = get_booking_or_404(db, booking_id)
    if booking.owner_id != current_user.id and booking.provider_id != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado a ver este viaje")

    query = (
        db.query(
            WalkLocation.id,
            WalkLocation.walk_id,
            func.ST_AsGeoJSON(WalkLocation.location).label("geojson"),
            WalkLocation.accuracy_meters,
            WalkLocation.speed_kmh,
            WalkLocation.recorded_at,
        )
        .filter(WalkLocation.walk_id == booking_id)
        .order_by(WalkLocation.recorded_at.asc())
        .limit(limit)
    )

    results = []
    for r in query.all():
        lat = 0.0
        lon = 0.0
        if r.geojson:
            try:
                geom = json.loads(r.geojson)
                coords = geom.get("coordinates", [0.0, 0.0])
                lon = float(coords[0])
                lat = float(coords[1])
            except Exception:
                pass

        results.append({
            "id": r.id,
            "walk_id": r.walk_id,
            "latitude": lat,
            "longitude": lon,
            "accuracy_meters": str(r.accuracy_meters) if r.accuracy_meters is not None else None,
            "speed_kmh": str(r.speed_kmh) if r.speed_kmh is not None else None,
            "recorded_at": r.recorded_at.isoformat() if r.recorded_at else "",
        })

    return results

