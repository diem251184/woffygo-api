from decimal import Decimal
from datetime import datetime, timezone
import math
from pydantic import BaseModel, Field
import json
from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import func, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.booking import Booking, BookingPet, BookingStatus, ServiceType
from app.models.user import User, UserRole
from app.models.walk_location import WalkLocation
from app.models.walker_profile import WalkerProfile
from app.models.walker_verification import WalkerVerification, WalkerVerificationStatus
from app.services.kyc_eligibility import is_kyc_operationally_approved
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
    WALK_MAX_RADIUS_KM,
    accept_booking,
    calculate_quote,
    cancel_booking,
    create_booking,
    finish_booking,
    get_booking_or_404,
    start_booking,
)
from app.services.routing import (
    get_driving_distance_km,
    get_driving_route_details,
)

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


@router.get("/unread-message-ids", response_model=dict[str, list[int]])
def list_unread_message_ids(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, list[int]]:
    """Identificadores pendientes del participante autenticado."""
    from sqlalchemy import or_
    from app.models.message import Message

    if current_user.role not in (
        UserRole.OWNER,
        UserRole.WALKER,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso no autorizado.",
        )

    rows = (
        db.query(
            Message.walk_id,
            Message.id,
        )
        .join(
            Booking,
            Booking.id == Message.walk_id,
        )
        .filter(
            or_(
                Booking.owner_id == current_user.id,
                Booking.provider_id == current_user.id,
            ),
            Message.sender_id != current_user.id,
            Message.read_at.is_(None),
        )
        .order_by(Message.walk_id, Message.id)
        .all()
    )

    result: dict[str, list[int]] = {}

    for booking_id, message_id in rows:
        result.setdefault(str(booking_id), []).append(
            int(message_id)
        )

    return result


@router.get("/unread-counts", response_model=dict[str, int])
def list_unread_counts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    from sqlalchemy import func, or_
    from app.models.message import Message

    if current_user.role not in (
        UserRole.OWNER,
        UserRole.WALKER,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso no autorizado.",
        )

    rows = (
        db.query(
            Message.walk_id,
            func.count(Message.id),
        )
        .join(
            Booking,
            Booking.id == Message.walk_id,
        )
        .filter(
            or_(
                Booking.owner_id == current_user.id,
                Booking.provider_id == current_user.id,
            ),
            Message.sender_id != current_user.id,
            Message.read_at.is_(None),
        )
        .group_by(Message.walk_id)
        .all()
    )

    return {
        str(booking_id): int(unread_count)
        for booking_id, unread_count in rows
    }


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

    if current_user.role not in (UserRole.OWNER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo propietarios y administradores pueden cotizar servicios",
        )

    distance_km: Decimal | None = None
    if payload.service_type == ServiceType.TRANSPORT:
        if (
            payload.origin_latitude is None
            or payload.origin_longitude is None
            or payload.destination_latitude is None
            or payload.destination_longitude is None
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Para cotizar Woofy Traslados debes enviar coordenadas de origen y destino",
            )
        distance_km = get_driving_distance_km(
            payload.origin_latitude,
            payload.origin_longitude,
            payload.destination_latitude,
            payload.destination_longitude,
        )

    price, fee, earnings = calculate_quote(
        payload.service_type,
        payload.duration_minutes,
        payload.num_pets,
        distance_km,
    )

    return BookingQuoteResponse(
        price_total=price,
        platform_fee=fee,
        provider_earnings=earnings,
        currency="ARS",
        distance_km=distance_km,
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

    if current_user.role == UserRole.WALKER:
        from fastapi.responses import JSONResponse

        safe_bookings = [
            BookingResponse.model_validate(b).model_dump(
                mode="json",
                exclude={"platform_fee", "price_total"},
            )
            for b in bookings
        ]
        return JSONResponse(content=safe_bookings)

    if current_user.role == UserRole.OWNER:
        return [
            BookingResponse.model_validate(b).model_copy(
                update={
                    "provider_name": b.provider.full_name if b.provider else None
                }
            )
            for b in bookings
        ]

    return bookings


def _eligible_available_bookings(
    service_type: ServiceType,
    current_user: User,
    db: Session,
    booking_id: int | None = None,
) -> list[Booking]:
    from app.services.profile_service_access import ensure_profile_services_enabled
    from app.services.bookings import is_booking_pet_snapshot_compatible
    ensure_profile_services_enabled(current_user)
    expected_type = (
        ServiceType.WALK if current_user.service_type == "walk"
        else ServiceType.TRANSPORT if current_user.service_type == "transport"
        else None
    )
    if expected_type is None or service_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenes acceso a solicitudes de este tipo de servicio.",
        )

    # Verificación de seguridad: solo paseadores online y con KYC aprobado pueden ver servicios disponibles
    profile = db.query(WalkerProfile).filter(WalkerProfile.user_id == current_user.id).first()
    if profile is None or not profile.is_online:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes tener tu perfil activo y estar online para ver servicios disponibles",
        )

    verification = (
        db.query(WalkerVerification)
        .filter(WalkerVerification.user_id == current_user.id)
        .order_by(WalkerVerification.id.desc())
        .first()
    )
    if not is_kyc_operationally_approved(verification, current_user.service_type):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta debe estar verificada para ver solicitudes disponibles",
        )

    # No mostrar nuevas solicitudes mientras el prestador
    # mantiene un servicio aceptado o en curso.
    occupied = (
        db.query(Booking.id)
        .filter(
            Booking.provider_id == current_user.id,
            Booking.status.in_(
                (BookingStatus.ACCEPTED, BookingStatus.IN_PROGRESS)
            ),
        )
        .first()
        is not None
    )
    if occupied:
        return []

    bookings = (
        db.query(Booking)
        .options(joinedload(Booking.booking_pets).joinedload(BookingPet.pet))
        .filter(Booking.status == BookingStatus.REQUESTED)
        .filter(Booking.provider_id.is_(None))
        .filter(Booking.service_type == service_type)
        .filter(
            Booking.id == booking_id
            if booking_id is not None
            else True
        )
        .filter(
            text(
                """
                (
                    :coverage_transport = true
                    OR EXISTS (
                        SELECT 1
                        FROM walker_profiles wp
                        WHERE wp.user_id = :coverage_provider_id
                          AND wp.current_location IS NOT NULL
                          AND wp.search_radius_km > 0
                          AND ST_DWithin(
                              wp.current_location,
                              bookings.pickup_location,
                              LEAST(wp.search_radius_km, :coverage_max_radius_km) * 1000
                          )
                    )
                )
                """
            )
        )
        .params(
            coverage_transport=(service_type == ServiceType.TRANSPORT),
            coverage_provider_id=current_user.id,
            coverage_max_radius_km=WALK_MAX_RADIUS_KM,
        )
        .order_by(Booking.created_at.asc())
        .all()
    )
    compatible_bookings = []
    for booking in bookings:
        if not booking.booking_pets:
            continue
        compatible = True
        for association in booking.booking_pets:
            pet = association.pet
            if pet is None or pet.species not in ("dog", "cat"):
                compatible = False
                break
            if service_type == ServiceType.WALK and pet.species != "dog":
                compatible = False
                break
            if pet.has_special_needs and not profile.accepts_special_needs:
                compatible = False
                break
            if pet.species == "cat" and (pet.is_ppp is True or not profile.accepts_cats):
                compatible = False
                break
            if pet.species == "dog" and (
                pet.is_ppp is None or (pet.is_ppp is True and not profile.accepts_ppp)
            ):
                compatible = False
                break
        if compatible:
            compatible = all(
                is_booking_pet_snapshot_compatible(
                    association, profile, booking.service_type
                )
                for association in booking.booking_pets
            )
        if compatible:
            compatible_bookings.append(booking)
    bookings = compatible_bookings

    return bookings


@router.get("/available", response_model=list[BookingResponse], response_model_exclude={"__all__": {"platform_fee", "price_total"}})
def list_available(
    service_type: ServiceType = Query(default=ServiceType.WALK),
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    bookings = _eligible_available_bookings(
        service_type, current_user, db
    )

    from app.services.bookings import get_platform_fee_rate
    from decimal import Decimal
    fee_rate = get_platform_fee_rate()
    for b in bookings:
        _attach_extra_fields(db, b)
        # Calcular ganancia estimada para mostrar en el radar antes de aceptar
        fee = (b.price_total * fee_rate).quantize(Decimal("0.01"))
        b.provider_earnings = b.price_total - fee
    return bookings




class TransportEtaRequest(BaseModel):
    latitude: float = Field(
        ..., ge=-90, le=90, allow_inf_nan=False
    )
    longitude: float = Field(
        ..., ge=-180, le=180, allow_inf_nan=False
    )


class TransportEtaResponse(BaseModel):
    pickup_eta_seconds: float | None = None
    transport_eta_seconds: float | None = None
    pickup_route_coordinates: list[list[float]] | None = None
    transport_route_coordinates: list[list[float]] | None = None
    calculated_at: datetime


def _valid_eta_coordinates(
    latitude: float | None,
    longitude: float | None,
) -> bool:
    return (
        latitude is not None
        and longitude is not None
        and math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def _transport_eta_details(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    include_geometry: bool = False,
) -> tuple[
    float | None,
    list[list[float]] | None,
]:
    try:
        _, duration, coordinates = get_driving_route_details(
            origin_lat,
            origin_lon,
            dest_lat,
            dest_lon,
            include_geometry=include_geometry,
        )
    except HTTPException:
        return None, None

    if duration is None:
        return None, coordinates

    seconds = float(duration)

    if not math.isfinite(seconds) or seconds < 0:
        return None, coordinates

    return seconds, coordinates




TRANSPORT_ETA_COOLDOWN_SECONDS = 15


def _admit_transport_eta(
    db: Session,
    user_id: int,
) -> None:
    """Control de concurrencia y frecuencia compartido en PostgreSQL."""

    try:
        # El bloqueo permanece durante la transaccion
        # de la solicitud actual y se libera al cerrarla.
        acquired = db.execute(
            text(
                """
                SELECT pg_try_advisory_xact_lock(
                    hashtextextended(:lock_key, 0)
                )
                """
            ),
            {
                "lock_key":
                    f"woffygo:transport-eta:v1:{user_id}"
            },
        ).scalar_one()

        if not acquired:
            raise HTTPException(
                status_code=429,
                detail="Ya hay una consulta ETA en curso.",
                headers={
                    "Retry-After": str(
                        TRANSPORT_ETA_COOLDOWN_SECONDS
                    )
                },
            )

        bind = db.get_bind()

        if not isinstance(bind, Engine):
            raise HTTPException(
                status_code=503,
                detail="Estimacion temporalmente no disponible.",
            )

        # Transaccion independiente para conservar el limite
        # aun cuando Mapbox falle posteriormente.
        # No confirmar cambios de la sesion de la reserva.

        with bind.begin() as quota_db:

            quota_db.execute(
                text("SET LOCAL lock_timeout = '2s'")
            )

            quota_db.execute(
                text("SET LOCAL statement_timeout = '3s'")
            )

            admitted = quota_db.execute(
                text(
                    """
                    INSERT INTO transport_eta_rate_limits (
                        user_id,
                        next_allowed_at
                    )
                    VALUES (
                        :user_id,
                        clock_timestamp()
                        + make_interval(secs => :cooldown)
                    )
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        next_allowed_at =
                            clock_timestamp()
                            + make_interval(secs => :cooldown)
                    WHERE
                        transport_eta_rate_limits.next_allowed_at
                        <= clock_timestamp()
                    RETURNING user_id
                    """
                ),
                {
                    "user_id": user_id,
                    "cooldown": float(
                        TRANSPORT_ETA_COOLDOWN_SECONDS
                    ),
                },
            ).scalar_one_or_none()

        if admitted is None:
            raise HTTPException(
                status_code=429,
                detail="Espera unos segundos antes de consultar nuevamente.",
                headers={
                    "Retry-After": str(
                        TRANSPORT_ETA_COOLDOWN_SECONDS
                    )
                },
            )

    except SQLAlchemyError:
        # Fallar de forma cerrada: si no se puede acreditar
        # el limite, no se autoriza consumo de Mapbox.

        raise HTTPException(
            status_code=503,
            detail="Estimacion temporalmente no disponible.",
        ) from None


@router.post(
    "/{booking_id}/transport-eta",
    response_model=TransportEtaResponse,
)
def get_transport_eta(
    booking_id: int,
    payload: TransportEtaRequest,
    current_user: User = Depends(
        require_role(UserRole.WALKER)
    ),
    db: Session = Depends(get_db),
):
    # Aplicar exactamente las reglas de acceso del Radar.
    # No utilizar las coordenadas del telefono para
    # autorizar una reserva.

    assigned_booking = (
        db.query(Booking)
        .filter(
            Booking.id == booking_id,
            Booking.provider_id == current_user.id,
            Booking.service_type == ServiceType.TRANSPORT,
            Booking.status.in_(
                (
                    BookingStatus.ACCEPTED,
                    BookingStatus.IN_PROGRESS,
                )
            ),
        )
        .first()
    )

    if assigned_booking is not None:

        from app.services.profile_service_access import (
            ensure_profile_services_enabled,
        )

        ensure_profile_services_enabled(current_user)

        if current_user.service_type != "transport":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso al traslado no autorizado.",
            )

        profile = (
            db.query(WalkerProfile)
            .filter(
                WalkerProfile.user_id == current_user.id
            )
            .first()
        )

        verification = (
            db.query(WalkerVerification)
            .filter(
                WalkerVerification.user_id == current_user.id
            )
            .order_by(WalkerVerification.id.desc())
            .first()
        )

        if (
            profile is None
            or not is_kyc_operationally_approved(
                verification,
                current_user.service_type,
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu cuenta no esta habilitada para el traslado.",
            )

        booking = assigned_booking

    else:

        # Conservar las reglas originales del Radar
        # para solicitudes todavia no asignadas.

        bookings = _eligible_available_bookings(
            ServiceType.TRANSPORT,
            current_user,
            db,
            booking_id=booking_id,
        )

        if len(bookings) != 1:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Traslado no disponible.",
            )

        booking = bookings[0]

    is_assigned = assigned_booking is not None

    # Leer las coordenadas oficiales de la reserva.
    # No aceptar destinos arbitrarios desde Android.

    route = db.execute(
        text(
            """
            SELECT
                ST_Y(CAST(pickup_location AS geometry))
                    AS pickup_lat,
                ST_X(CAST(pickup_location AS geometry))
                    AS pickup_lon,
                ST_Y(CAST(dropoff_location AS geometry))
                    AS dropoff_lat,
                ST_X(CAST(dropoff_location AS geometry))
                    AS dropoff_lon
            FROM bookings
            WHERE id = :booking_id
              AND service_type = :transport_type
              AND (
                  (
                      :assigned = false
                      AND provider_id IS NULL
                      AND status = :requested_status
                  )
                  OR
                  (
                      :assigned = true
                      AND provider_id = :provider_id
                      AND status = :assigned_status
                  )
              )
            """
        ),
        {
            "booking_id": booking.id,
            "requested_status": BookingStatus.REQUESTED.name,
            "transport_type": ServiceType.TRANSPORT.name,
            "assigned": is_assigned,
            "provider_id": current_user.id,
            "assigned_status": (
                booking.status.name if is_assigned
                else BookingStatus.REQUESTED.name
            ),
        },
    ).first()

    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Traslado no disponible.",
        )

    pickup_lat = (
        float(route.pickup_lat)
        if route.pickup_lat is not None else None
    )
    pickup_lon = (
        float(route.pickup_lon)
        if route.pickup_lon is not None else None
    )
    dropoff_lat = (
        float(route.dropoff_lat)
        if route.dropoff_lat is not None else None
    )
    dropoff_lon = (
        float(route.dropoff_lon)
        if route.dropoff_lon is not None else None
    )

    pickup_eta = None
    transport_eta = None
    pickup_route_coordinates = None
    transport_route_coordinates = None

    if booking.status == BookingStatus.IN_PROGRESS:

        # Durante el traslado, calcular el tiempo restante
        # desde la ubicacion actual hasta el destino.
        # No calcular nuevamente una llegada al retiro.

        if _valid_eta_coordinates(
            dropoff_lat, dropoff_lon
        ):

            _admit_transport_eta(db, current_user.id)

            transport_eta, transport_route_coordinates = (
                _transport_eta_details(
                    payload.latitude,
                    payload.longitude,
                    dropoff_lat,
                    dropoff_lon,
                    include_geometry=True,
                )
            )

    elif _valid_eta_coordinates(pickup_lat, pickup_lon):

        # Radar y servicios aceptados:
        # posicion actual -> retiro -> destino.

        _admit_transport_eta(db, current_user.id)

        pickup_eta, pickup_route_coordinates = (
            _transport_eta_details(
                payload.latitude,
                payload.longitude,
                pickup_lat,
                pickup_lon,
                include_geometry=is_assigned,
            )
        )

        if _valid_eta_coordinates(
            dropoff_lat, dropoff_lon
        ):
            transport_eta, transport_route_coordinates = (
                _transport_eta_details(
                    pickup_lat,
                    pickup_lon,
                    dropoff_lat,
                    dropoff_lon,
                    include_geometry=is_assigned,
                )
            )

    return TransportEtaResponse(
        pickup_eta_seconds=pickup_eta,
        transport_eta_seconds=transport_eta,
        pickup_route_coordinates=pickup_route_coordinates,
        transport_route_coordinates=transport_route_coordinates,
        calculated_at=datetime.now(timezone.utc),
    )


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

    # Paseador elegible: solo si tiene rol WALKER, está online, verificado y la reserva está libre
    from app.services.bookings import is_booking_pet_snapshot_compatible
    is_eligible_candidate = False
    if current_user.role == UserRole.WALKER and booking.status == BookingStatus.REQUESTED and booking.provider_id is None:
        from app.services.profile_service_access import ensure_profile_services_enabled
        ensure_profile_services_enabled(current_user)

        profile = db.query(WalkerProfile).filter(WalkerProfile.user_id == current_user.id).first()
        if profile and profile.is_online:
            verification = (
                db.query(WalkerVerification)
                .filter(WalkerVerification.user_id == current_user.id)
                .order_by(WalkerVerification.id.desc())
                .first()
            )
            if is_kyc_operationally_approved(verification, current_user.service_type):
                expected_service = (
                    ServiceType.WALK if current_user.service_type == "walk"
                    else ServiceType.TRANSPORT if current_user.service_type == "transport"
                    else None
                )
                if booking.service_type == expected_service and booking.booking_pets:
                    compatible = True
                    for association in booking.booking_pets:
                        pet = association.pet
                        if pet is None or pet.species not in ("dog", "cat"):
                            compatible = False
                            break
                        if booking.service_type == ServiceType.WALK and pet.species != "dog":
                            compatible = False
                            break
                        if pet.has_special_needs and not profile.accepts_special_needs:
                            compatible = False
                            break
                        if pet.species == "cat" and (pet.is_ppp is True or not profile.accepts_cats):
                            compatible = False
                            break
                        if pet.species == "dog" and (
                            pet.is_ppp is None or (pet.is_ppp is True and not profile.accepts_ppp)
                        ):
                            compatible = False
                            break
                    if compatible:
                        compatible = all(
                            is_booking_pet_snapshot_compatible(
                                association, profile, booking.service_type
                            )
                            for association in booking.booking_pets
                        )
                    if compatible and booking.service_type == ServiceType.WALK:
                        within_coverage = db.execute(
                            text(
                                """
                                SELECT ST_DWithin(
                                    wp.current_location,
                                    b.pickup_location,
                                    LEAST(wp.search_radius_km, :max_radius_km) * 1000
                                )
                                FROM walker_profiles wp
                                JOIN bookings b ON b.id = :booking_id
                                WHERE wp.user_id = :provider_id
                                  AND wp.current_location IS NOT NULL
                                  AND wp.search_radius_km > 0
                                """
                            ),
                            {
                                "booking_id": booking.id,
                                "provider_id": current_user.id,
                                "max_radius_km": WALK_MAX_RADIUS_KM,
                            },
                        ).scalar()
                        compatible = within_coverage is True

                    is_eligible_candidate = compatible

    # Un candidato ocupado no puede acceder a una solicitud
    # que tampoco estaria autorizado a aceptar.
    if is_eligible_candidate:
        occupied = (
            db.query(Booking.id)
            .filter(
                Booking.provider_id == current_user.id,
                Booking.status.in_(
                    (BookingStatus.ACCEPTED, BookingStatus.IN_PROGRESS)
                ),
            )
            .first()
            is not None
        )
        if occupied:
            is_eligible_candidate = False

    if not (is_owner or is_provider or is_admin or is_eligible_candidate):
        raise HTTPException(status_code=403, detail="Sin acceso a esta reserva")

    _attach_extra_fields(db, booking)
    if current_user.role == UserRole.WALKER:
        from fastapi.responses import JSONResponse

        safe_booking = BookingResponse.model_validate(booking).model_copy(
            update={
                "owner_name": booking.owner.full_name
                if is_provider and booking.owner else None,
                "cancelled_by_name": booking.cancelled_by.full_name
                if is_provider
                and booking.status == BookingStatus.CANCELLED
                and booking.cancelled_by else None,
            }
        ).model_dump(
            mode="json",
            exclude={"platform_fee", "price_total"},
        )
        return JSONResponse(content=safe_booking)
    if is_owner:
        return BookingResponse.model_validate(booking).model_copy(
            update={
                "provider_name": booking.provider.full_name
                if booking.provider else None
            }
        )
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
    if current_user.role == UserRole.WALKER:
        from fastapi.responses import JSONResponse

        safe_booking = BookingResponse.model_validate(b).model_dump(
            mode="json",
            exclude={"platform_fee", "price_total"},
        )
        return JSONResponse(content=safe_booking)
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


@router.get("/{booking_id}/locations")
def get_booking_locations(
    booking_id: int,
    limit: int = Query(default=500, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = get_booking_or_404(db, booking_id)
    if booking.owner_id != current_user.id and booking.provider_id != current_user.id and current_user.role != UserRole.ADMIN:
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

    from math import isfinite

    results = []
    for r in query.all():
        if not r.geojson:
            continue

        try:
            geom = json.loads(r.geojson)
            if geom.get("type") != "Point":
                continue

            coords = geom.get("coordinates")
            if not isinstance(coords, (list, tuple)) or len(coords) < 2:
                continue

            lon = float(coords[0])
            lat = float(coords[1])

            if not (
                isfinite(lon)
                and isfinite(lat)
                and -180 <= lon <= 180
                and -90 <= lat <= 90
            ):
                continue
        except (TypeError, ValueError, IndexError, AttributeError):
            continue

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