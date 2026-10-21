from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from geoalchemy2.elements import WKTElement
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingPet, BookingStatus, ServiceType
from app.models.payment import Payment, PaymentStatus
from app.models.pet import Pet
from app.models.user import User, UserRole
from app.models.walker_profile import WalkerProfile
from app.models.walker_verification import WalkerVerification, WalkerVerificationStatus
from app.schemas.booking import BookingCreate
from app.services import push
from app.services.escrow import start_escrow_window
from app.services.pricing import walk_price, transport_price
from app.services.routing import get_driving_distance_km

ALLOWED_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.REQUESTED: {BookingStatus.ACCEPTED, BookingStatus.REJECTED, BookingStatus.CANCELLED},
    BookingStatus.ACCEPTED: {BookingStatus.IN_PROGRESS, BookingStatus.CANCELLED},
    BookingStatus.IN_PROGRESS: {BookingStatus.COMPLETED, BookingStatus.CANCELLED},
    BookingStatus.COMPLETED: set(),
    BookingStatus.CANCELLED: set(),
    BookingStatus.REJECTED: set(),
}

COMMISSION_TIERS = [
    (0, 10, Decimal("0.20")),
    (10, 50, Decimal("0.15")),
    (50, 999999, Decimal("0.12")),
]

MAX_PETS = 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_point(latitude: float, longitude: float) -> WKTElement:
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def get_platform_fee_rate(total_completed: int) -> Decimal:
    for min_w, max_w, rate in COMMISSION_TIERS:
        if min_w <= total_completed < max_w:
            return rate
    return Decimal("0.15")


def validate_status_transition(current: BookingStatus, target: BookingStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transición de estado no permitida de {current.value} a {target.value}",
        )


def get_booking_or_404(db: Session, booking_id: int) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva no encontrada",
        )
    return booking


def calculate_quote(
    service_type: ServiceType,
    duration_minutes: int,
    num_pets: int,
    completed_services: int,
    distance_km: Decimal | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Calcula precio total, comision y ganancia segun reglas oficiales del servidor."""
    if service_type == ServiceType.WALK:
        price_total = walk_price(duration_minutes, num_pets)
    elif service_type == ServiceType.TRANSPORT:
        if distance_km is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere la distancia calculada para cotizar Pet Taxi",
            )
        price_total = transport_price(distance_km, num_pets)
    else:
        price_total = walk_price(duration_minutes, num_pets)

    fee_rate = get_platform_fee_rate(completed_services)
    fee = (price_total * fee_rate).quantize(Decimal("0.01"))
    earnings = price_total - fee
    return price_total, fee, earnings


def create_booking(db: Session, owner: User, payload: BookingCreate) -> Booking:
    if len(payload.pet_ids) == 0 or len(payload.pet_ids) > MAX_PETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Debes seleccionar entre 1 y {MAX_PETS} mascotas",
        )

    pets = db.query(Pet).filter(Pet.id.in_(payload.pet_ids)).all()
    if len(pets) != len(payload.pet_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alguna de las mascotas no existe",
        )
    for pet in pets:
        if pet.owner_id != owner.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"La mascota '{pet.name}' no te pertenece",
            )

    num_pets = len(pets)
    distance_meters: Decimal | None = None

    if payload.service_type == ServiceType.TRANSPORT:
        if (
            payload.dropoff_latitude is None
            or payload.dropoff_longitude is None
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pet Taxi requiere coordenadas de destino validas",
            )
        dist_km = get_driving_distance_km(
            payload.pickup_latitude,
            payload.pickup_longitude,
            payload.dropoff_latitude,
            payload.dropoff_longitude,
        )
        distance_meters = (dist_km * Decimal("1000")).quantize(Decimal("0.01"))
        price_total = transport_price(dist_km, num_pets)
    else:
        price_total = walk_price(payload.duration_minutes, num_pets)

    now = _now()
    booking = Booking(
        owner_id=owner.id,
        provider_id=None,
        service_type=payload.service_type,
        status=BookingStatus.REQUESTED,
        pickup_location=_make_point(payload.pickup_latitude, payload.pickup_longitude),
        pickup_address=payload.pickup_address,
        duration_minutes=payload.duration_minutes,
        notes=payload.notes,
        price_total=price_total,
        platform_fee=Decimal("0.00"),
        provider_earnings=Decimal("0.00"),
        distance_meters=distance_meters,
        requested_at=now,
        flagged_for_review=False,
    )
    db.add(booking)
    db.flush()

    for pet in pets:
        db.add(BookingPet(booking_id=booking.id, pet_id=pet.id))

    db.commit()
    db.refresh(booking)

    try:
        notify_nearby_providers_new_booking(db, booking, pets)
    except Exception as e:
        print(f"[push] Error notificando proveedores: {e}")

    return booking


def accept_booking(db: Session, provider: User, booking_id: int) -> Booking:
    # 1. Bloqueo pesimista de fila en BD para evitar asignaciones concurrentes
    booking = (
        db.query(Booking)
        .filter(Booking.id == booking_id)
        .with_for_update()
        .first()
    )
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva no encontrada",
        )

    # 2. Validar que la reserva siga disponible
    if booking.status != BookingStatus.REQUESTED or booking.provider_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta solicitud ya fue aceptada por otro paseador o ya no está disponible",
        )

    validate_status_transition(booking.status, BookingStatus.ACCEPTED)

    # 3. Validar estado y verificacion del paseador
    profile = db.query(WalkerProfile).filter(WalkerProfile.user_id == provider.id).first()
    if profile is None or not profile.is_online:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes tener tu perfil activo y estar online para aceptar solicitudes",
        )

    verification = (
        db.query(WalkerVerification)
        .filter(WalkerVerification.user_id == provider.id)
        .order_by(WalkerVerification.id.desc())
        .first()
    )
    if not verification or verification.status != WalkerVerificationStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta debe estar verificada por un administrador para aceptar solicitudes",
        )

    # 4. Validar que el paseador no tenga ya un servicio en curso
    active_booking = db.query(Booking).filter(
        Booking.provider_id == provider.id,
        Booking.status.in_([BookingStatus.ACCEPTED, BookingStatus.IN_PROGRESS]),
    ).first()
    if active_booking:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya tienes un servicio activo. Debes finalizarlo antes de tomar otro.",
        )

    num_pets = len(booking.booking_pets)
    dist_km = (booking.distance_meters / Decimal("1000")) if booking.distance_meters else None

    price_total, fee, earnings = calculate_quote(
        booking.service_type,
        booking.duration_minutes,
        num_pets,
        profile.total_walks,
        dist_km,
    )

    booking.provider_id = provider.id
    booking.status = BookingStatus.ACCEPTED
    booking.accepted_at = _now()
    booking.price_total = price_total
    booking.platform_fee = fee
    booking.provider_earnings = earnings
    db.commit()
    db.refresh(booking)

    try:
        push.send_to_user(
            db,
            booking.owner_id,
            "¡Servicio confirmado!",
            f"{provider.full_name} aceptó tu solicitud. Total: ${price_total}",
            {"type": "booking_accepted", "booking_id": booking.id},
        )
    except Exception as e:
        print(f"[push] Error notificando al dueño: {e}")

    return booking


def start_booking(db: Session, provider: User, booking_id: int) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    if booking.provider_id != provider.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No estás asignado a esta reserva",
        )
    validate_status_transition(booking.status, BookingStatus.IN_PROGRESS)

    payment = db.query(Payment).filter(Payment.booking_id == booking.id).first()
    if payment is None or payment.status != PaymentStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El servicio no puede iniciarse sin pago aprobado",
        )

    booking.status = BookingStatus.IN_PROGRESS
    booking.started_at = _now()
    db.commit()
    db.refresh(booking)
    return booking


def finish_booking(db: Session, provider: User, booking_id: int) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    if booking.provider_id != provider.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No estás asignado a esta reserva",
        )
    validate_status_transition(booking.status, BookingStatus.COMPLETED)

    booking.status = BookingStatus.COMPLETED
    booking.finished_at = _now()

    profile = db.query(WalkerProfile).filter(WalkerProfile.user_id == provider.id).first()
    if profile:
        profile.total_walks += 1

    db.commit()
    db.refresh(booking)

    start_escrow_window(db, booking.id)

    try:
        push.send_to_user(
            db,
            booking.owner_id,
            "Servicio completado",
            "Tu mascota está de regreso. Por favor confirma la entrega para liberar el pago.",
            {"type": "booking_finished", "booking_id": booking.id},
        )
    except Exception as e:
        print(f"[push] Error notificando finalización: {e}")

    return booking


def cancel_booking(db: Session, user: User, booking_id: int, reason: str | None) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    validate_status_transition(booking.status, BookingStatus.CANCELLED)

    is_owner = booking.owner_id == user.id
    is_provider = booking.provider_id == user.id

    if not (is_owner or is_provider or user.role == UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para cancelar esta reserva",
        )

    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = _now()
    booking.cancel_reason = reason
    booking.cancelled_by_id = user.id
    db.commit()
    db.refresh(booking)
    return booking


WALK_MAX_RADIUS_KM = 6


def notify_nearby_providers_new_booking(db: Session, booking: Booking, pets: list) -> None:
    is_transport = booking.service_type == ServiceType.TRANSPORT

    sql = text(
        """
        SELECT wp.user_id
        FROM walker_profiles wp
        JOIN users u ON u.id = wp.user_id
        WHERE wp.is_online = true
          AND u.is_active = true
          AND (
              :is_transport = true
              OR (
                  wp.current_location IS NOT NULL
                  AND ST_DWithin(
                      wp.current_location,
                      (SELECT pickup_location FROM bookings WHERE id = :booking_id),
                      LEAST(wp.search_radius_km, :walk_max_radius_km) * 1000
                  )
              )
          )
        """
    )
    rows = db.execute(
        sql,
        {
            "booking_id": booking.id,
            "is_transport": is_transport,
            "walk_max_radius_km": WALK_MAX_RADIUS_KM,
        },
    ).all()
    user_ids = [r.user_id for r in rows]
    if user_ids:
        pets_names = ", ".join(p.name for p in pets)
        if is_transport:
            title = "Nueva solicitud de traslado"
            body = f"{pets_names}\n{booking.pickup_address}"
        else:
            title = "Nueva solicitud de paseo"
            body = f"{pets_names} · {booking.duration_minutes} min\n{booking.pickup_address}"

        push.send_to_users(
            db,
            user_ids,
            title,
            body,
            {"type": "new_booking", "booking_id": booking.id},
        )