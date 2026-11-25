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
from app.services.kyc_eligibility import is_kyc_operationally_approved
from app.schemas.booking import BookingCreate
from app.services import push
from app.services.escrow import start_escrow_window
from app.services.pricing import walk_price, transport_price
from app.services.routing import (
    get_driving_distance_km,
    get_driving_route_metrics,
)

ALLOWED_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.REQUESTED: {BookingStatus.ACCEPTED, BookingStatus.REJECTED, BookingStatus.CANCELLED},
    BookingStatus.ACCEPTED: {BookingStatus.IN_PROGRESS, BookingStatus.CANCELLED},
    BookingStatus.IN_PROGRESS: {BookingStatus.COMPLETED, BookingStatus.CANCELLED},
    BookingStatus.COMPLETED: set(),
    BookingStatus.CANCELLED: set(),
    BookingStatus.REJECTED: set(),
}

MAX_PETS = 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_point(latitude: float, longitude: float) -> WKTElement:
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def get_platform_fee_rate() -> Decimal:
    # Comision plana del 15% por decision comercial (23/10/2026)
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
    distance_km: Decimal | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Calcula precio total, comision y ganancia segun reglas oficiales del servidor."""
    if service_type == ServiceType.WALK:
        price_total = walk_price(duration_minutes, num_pets)
    elif service_type == ServiceType.TRANSPORT:
        if distance_km is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere la distancia calculada para cotizar Woofy Traslados",
            )
        price_total = transport_price(distance_km, num_pets)
    else:
        price_total = walk_price(duration_minutes, num_pets)

    fee_rate = get_platform_fee_rate()
    fee = (price_total * fee_rate).quantize(Decimal("0.01"))
    earnings = price_total - fee
    return price_total, fee, earnings


def create_booking(db: Session, owner: User, payload: BookingCreate) -> Booking:
    from app.services.profile_service_access import ensure_profile_services_enabled
    ensure_profile_services_enabled(owner)
    scheduled_pickup = payload.scheduled_pickup_at
    estimated_transport_seconds = None

    if payload.service_type == ServiceType.TRANSPORT:
        if scheduled_pickup is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Indica la fecha y hora programadas de retiro.",
            )

        if scheduled_pickup.utcoffset() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El horario de retiro debe incluir zona horaria.",
            )

        scheduled_pickup = scheduled_pickup.astimezone(timezone.utc)

        if scheduled_pickup <= _now():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El horario de retiro debe ser futuro.",
            )
    else:
        if scheduled_pickup is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El horario programado corresponde a Woofy Traslados.",
            )

    if len(payload.pet_ids) == 0 or len(payload.pet_ids) > MAX_PETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Debes seleccionar entre 1 y {MAX_PETS} mascotas",
        )

    # Bloquear mascotas en orden estable hasta confirmar la reserva.
    # Coordina con update_pet y evita validar condiciones obsoletas.
    pets = (
        db.query(Pet)
        .filter(Pet.id.in_(payload.pet_ids))
        .order_by(Pet.id.asc())
        .with_for_update()
        .populate_existing()
        .all()
    )
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

    if payload.service_type not in (ServiceType.WALK, ServiceType.TRANSPORT):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Solo se permiten reservas de paseo o Woofy Traslados.",
        )

    for pet in pets:
        if pet.species not in ("dog", "cat"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"La especie de {pet.name} no esta permitida.",
            )
        if payload.service_type == ServiceType.WALK and pet.species != "dog":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Los paseos son exclusivamente para perros.",
            )
        if pet.species == "cat" and pet.is_ppp is True:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Revisa la declaracion PPP de {pet.name}.",
            )
        if pet.species == "dog" and pet.is_ppp is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Completa la declaracion PPP de {pet.name} antes de reservar.",
            )
        if pet.has_special_needs and not (pet.notes or "").strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Completá las necesidades especiales y los cuidados "
                    f"requeridos de {pet.name} en Mis Mascotas antes de reservar."
                ),
            )

    num_pets = len(pets)
    distance_meters: Decimal | None = None
    destination_address: str | None = None

    if payload.service_type == ServiceType.TRANSPORT:
        if (
            payload.dropoff_latitude is None
            or payload.dropoff_longitude is None
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Woofy Traslados requiere coordenadas de destino validas",
            )
        destination_address = (payload.dropoff_address or "").strip()
        if not destination_address or len(destination_address) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Woofy Traslados requiere una direccion de destino valida de hasta 255 caracteres",
            )

        dist_km, route_duration = get_driving_route_metrics(
            payload.pickup_latitude,
            payload.pickup_longitude,
            payload.dropoff_latitude,
            payload.dropoff_longitude,
        )

        if (
            route_duration is None
            or not route_duration.is_finite()
            or route_duration < 0
            or route_duration > Decimal("2147483647")
            or (dist_km > 0 and route_duration == 0)
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "No se pudo acreditar la duracion vial del traslado. "
                    "Intenta nuevamente."
                ),
            )

        from decimal import ROUND_CEILING

        estimated_transport_seconds = int(
            route_duration.to_integral_value(
                rounding=ROUND_CEILING
            )
        )
        distance_meters = (dist_km * Decimal("1000")).quantize(Decimal("0.01"))
        price_total = transport_price(dist_km, num_pets)
    else:
        price_total = walk_price(payload.duration_minutes, num_pets)

    # El telefono informa el importe que el dueno vio y confirmo.
    # El servidor calcula siempre el precio oficial y exige coincidencia.
    if payload.service_type == ServiceType.TRANSPORT:
        if payload.estimated_price is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Necesitas confirmar una cotizacion vigente antes de solicitar el traslado.",
            )
        if (
            not payload.estimated_price.is_finite()
            or payload.estimated_price <= Decimal("0.00")
            or payload.estimated_price != price_total
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El precio del traslado cambio. Actualiza la cotizacion y confirma nuevamente.",
            )

    booking_notes = (
        f"Destino: {destination_address}" + (f" | {payload.notes}" if payload.notes else "")
        if payload.service_type == ServiceType.TRANSPORT and destination_address
        else payload.notes
    )
    if booking_notes is not None and len(booking_notes) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Las observaciones superan el limite de 500 caracteres.",
        )

    now = _now()
    booking = Booking(
        owner_id=owner.id,
        provider_id=None,
        service_type=payload.service_type,
        status=BookingStatus.REQUESTED,
        pickup_location=_make_point(payload.pickup_latitude, payload.pickup_longitude),
        pickup_address=payload.pickup_address,
        dropoff_location=(
            _make_point(payload.dropoff_latitude, payload.dropoff_longitude)
            if payload.service_type == ServiceType.TRANSPORT
            else None
        ),
        dropoff_address=destination_address,
        duration_minutes=payload.duration_minutes,
        estimated_transport_seconds=estimated_transport_seconds,
        notes=booking_notes,
        price_total=price_total,
        platform_fee=Decimal("0.00"),
        provider_earnings=Decimal("0.00"),
        distance_meters=distance_meters,
        requested_at=now,
        scheduled_pickup_at=scheduled_pickup,
        flagged_for_review=False,
    )
    db.add(booking)
    db.flush()

    for pet in pets:
        db.add(
            BookingPet(
                booking_id=booking.id,
                pet_id=pet.id,
                conditions_snapshot={
                    "name": pet.name,
                    "species": pet.species,
                    "is_ppp": pet.is_ppp,
                    "has_special_needs": pet.has_special_needs,
                    "notes": pet.notes,
                    "aggressive_with_dogs": pet.aggressive_with_dogs,
                    "aggressive_with_people": pet.aggressive_with_people,
                },
            )
        )

    db.commit()
    db.refresh(booking)

    try:
        notify_nearby_providers_new_booking(db, booking, pets)
    except Exception as e:
        print(f"[push] Error notificando proveedores: {e}")

    return booking


def is_booking_pet_snapshot_compatible(
    association: BookingPet,
    profile: WalkerProfile,
    service_type: ServiceType,
) -> bool:
    """Conserva restricciones declaradas al reservar.

    Las verificaciones de condiciones actuales se mantienen
    en los puntos de acceso y aceptacion existentes.
    """
    snapshot = association.conditions_snapshot

    # Reserva anterior a CL145: no inventar condiciones historicas.
    # Los controles actuales siguen siendo obligatorios.
    if snapshot is None:
        return True

    if not isinstance(snapshot, dict):
        return False

    pet = association.pet
    species = snapshot.get("species")

    if (
        pet is None
        or species not in ("dog", "cat")
        or pet.species != species
        or service_type not in (ServiceType.WALK, ServiceType.TRANSPORT)
    ):
        return False

    if service_type == ServiceType.WALK and species != "dog":
        return False

    special = snapshot.get("has_special_needs")
    if not isinstance(special, bool):
        return False
    if special and not profile.accepts_special_needs:
        return False

    ppp = snapshot.get("is_ppp")

    if species == "cat":
        return (
            (ppp is False or ppp is None)
            and bool(profile.accepts_cats)
        )

    if not isinstance(ppp, bool):
        return False

    if ppp and not profile.accepts_ppp:
        return False

    return True

# Margenes operativos iniciales de planificacion.
# No representan una duracion vial medida.
# Mantener los mismos valores para todos los consumidores.
TRANSPORT_PICKUP_HANDLING_SECONDS = 600
TRANSPORT_DELIVERY_HANDLING_SECONDS = 600


def transport_schedule_conflict(
    db: Session,
    provider_id: int,
    booking: Booking,
    *,
    verify_road_transfer: bool = True,
    actual_start_at: datetime | None = None,
):
    """Read-only schedule evaluation.

    Acceptance must hold the provider row lock before
    calling this function. Advisory consumers do not
    reserve capacity and must not authorize acceptance.
    """

    from app.services.transport_schedule import (
        ScheduleConflict,
        TransportWindow,
        evaluate_transport_candidate,
        evaluate_transport_pair,
        transport_window_bounds,
    )

    from app.services.transport_schedule_routes import (
        RoadPoint,
        ScheduledTransport,
        evaluate_road_compatibility,
        valid_road_point,
    )

    from geoalchemy2.shape import to_shape

    def as_scheduled(item, pickup_override=None):

        if item.service_type != ServiceType.TRANSPORT:
            return None

        window = TransportWindow(
            pickup_at=(
                item.scheduled_pickup_at
                if pickup_override is None
                else pickup_override
            ),
            road_seconds=item.estimated_transport_seconds,
            pickup_handling_seconds=(
                TRANSPORT_PICKUP_HANDLING_SECONDS
                + (30 if pickup_override is not None else 0)
            ),
            delivery_handling_seconds=(
                TRANSPORT_DELIVERY_HANDLING_SECONDS
            ),
        )

        if transport_window_bounds(window) is None:
            return None

        try:

            pickup_shape = to_shape(item.pickup_location)
            dropoff_shape = to_shape(item.dropoff_location)

            pickup = RoadPoint(
                latitude=float(pickup_shape.y),
                longitude=float(pickup_shape.x),
            )

            dropoff = RoadPoint(
                latitude=float(dropoff_shape.y),
                longitude=float(dropoff_shape.x),
            )

        except (
            AttributeError,
            TypeError,
            ValueError,
            ArithmeticError,
        ):
            return None

        if (
            not valid_road_point(pickup)
            or not valid_road_point(dropoff)
        ):
            return None

        return ScheduledTransport(
            window=window,
            pickup=pickup,
            dropoff=dropoff,
        )

    if type(verify_road_transfer) is not bool:
        return ScheduleConflict.INVALID_DATA

    if actual_start_at is not None:

        # Only a definitively assigned transport may
        # be evaluated for actual commencement.
        if (
            not verify_road_transfer
            or booking.status != BookingStatus.ACCEPTED
            or booking.provider_id != provider_id
            or not isinstance(actual_start_at, datetime)
            or actual_start_at.utcoffset() is None
            or booking.scheduled_pickup_at is None
            or booking.scheduled_pickup_at.utcoffset() is None
            or actual_start_at < booking.scheduled_pickup_at
        ):
            return ScheduleConflict.INVALID_DATA

    candidate = as_scheduled(
        booking,
        pickup_override=actual_start_at,
    )

    if candidate is None:
        return ScheduleConflict.INVALID_DATA

    current = _now()

    active = (
        db.query(Booking)
        .filter(
            Booking.provider_id == provider_id,
            Booking.id != booking.id,
            Booking.status.in_(
                (
                    BookingStatus.ACCEPTED,
                    BookingStatus.IN_PROGRESS,
                )
            ),
        )
        .populate_existing()
        .all()
    )

    has_service_in_progress = any(
        item.status == BookingStatus.IN_PROGRESS
        for item in active
    )

    if actual_start_at is None:

        result = evaluate_transport_candidate(
            candidate.window,
            now=current,
            has_service_in_progress=has_service_in_progress,
        )

        if result != ScheduleConflict.NONE:
            return result

    else:

        # A real start is not a future pickup request.
        # Its time is generated exclusively by the server.
        if has_service_in_progress:
            return ScheduleConflict.ACTIVE_SERVICE

        if actual_start_at > current:
            return ScheduleConflict.INVALID_DATA

    existing = []

    for item in active:

        scheduled = as_scheduled(item)

        # Unknown historical duration or coordinates
        # cannot be treated as a free interval.
        if scheduled is None:
            return ScheduleConflict.INVALID_DATA

        bounds = transport_window_bounds(
            scheduled.window
        )

        # An overdue accepted service remains unresolved.
        if bounds is None or bounds[0] <= current:
            return ScheduleConflict.ACTIVE_SERVICE

        preliminary = evaluate_transport_pair(
            candidate.window,
            scheduled.window,
            transfer_seconds=0,
        )

        if preliminary != ScheduleConflict.NONE:
            return preliminary

        existing.append(scheduled)

    # Advisory consumers filter known scheduling conflicts
    # without generating external route requests.
    # This is not authorization to accept a booking.
    if not verify_road_transfer:
        return ScheduleConflict.NONE

    candidate_start = transport_window_bounds(
        candidate.window
    )[0]

    previous = None
    following = None

    for scheduled in existing:

        start = transport_window_bounds(
            scheduled.window
        )[0]

        if start < candidate_start:

            if (
                previous is None
                or start > transport_window_bounds(
                    previous.window
                )[0]
            ):
                previous = scheduled

        else:

            if (
                following is None
                or start < transport_window_bounds(
                    following.window
                )[0]
            ):
                following = scheduled

    # Only adjacent appointments require new
    # inter-service routes when inserting a booking.
    if previous is not None:

        result = evaluate_road_compatibility(
            previous,
            candidate,
        )

        if result != ScheduleConflict.NONE:
            return result

    if following is not None:

        result = evaluate_road_compatibility(
            candidate,
            following,
        )

        if result != ScheduleConflict.NONE:
            return result

    # Recheck expiration after external route calls.
    if actual_start_at is None:

        return evaluate_transport_candidate(
            candidate.window,
            now=_now(),
            has_service_in_progress=False,
        )

    # The definitive start path performs its final
    # evaluation again if time advanced materially.
    return ScheduleConflict.NONE


def accept_booking(db: Session, provider: User, booking_id: int) -> Booking:
    from app.services.profile_service_access import ensure_profile_services_enabled
    ensure_profile_services_enabled(provider)
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
    if not is_kyc_operationally_approved(verification, provider.service_type):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta debe estar verificada por un administrador para aceptar solicitudes",
        )

    # Serializar aceptaciones del mismo prestador en la transaccion.
    # Bloquear solo la reserva no impide aceptar dos reservas distintas.
    locked_provider = (
        db.query(User)
        .filter(User.id == provider.id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if locked_provider is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El prestador no esta disponible.",
        )

    # Preserve the original single-service policy
    # for walks. Transport uses the scheduling engine.
    if booking.service_type != ServiceType.TRANSPORT:
        active_booking = db.query(Booking).filter(
            Booking.provider_id == provider.id,
            Booking.status.in_([
                BookingStatus.ACCEPTED,
                BookingStatus.IN_PROGRESS,
            ]),
        ).first()

        if active_booking:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya tienes un servicio activo. Debes finalizarlo antes de tomar otro.",
            )

    # Compatibilidad obligatoria entre servicio y prestador.
    expected_provider_type = (
        "walk" if booking.service_type == ServiceType.WALK
        else "transport" if booking.service_type == ServiceType.TRANSPORT
        else None
    )
    if expected_provider_type is None or provider.service_type != expected_provider_type:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El prestador no esta habilitado para este tipo de servicio.",
        )

    if locked_provider.role != UserRole.WALKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un prestador puede aceptar solicitudes.",
        )

    provider = locked_provider

    if not booking.booking_pets:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La reserva no contiene mascotas.",
        )

    for association in booking.booking_pets:
        pet = association.pet
        if pet is None or pet.species not in ("dog", "cat"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La reserva contiene una especie no admitida.",
            )
        if booking.service_type == ServiceType.WALK and pet.species != "dog":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Los paseos son exclusivamente para perros.",
            )
        if pet.has_special_needs and not profile.accepts_special_needs:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El prestador no acepta mascotas con necesidades especiales.",
            )
        if pet.species == "cat":
            if pet.is_ppp is True:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="La declaracion PPP de la mascota es incompatible.",
                )
            if not profile.accepts_cats:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="El prestador no acepta traslados de gatos.",
                )
        if pet.species == "dog":
            if pet.is_ppp is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="La mascota requiere una declaracion PPP.",
                )
            if pet.is_ppp is True and not profile.accepts_ppp:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="El prestador no acepta perros declarados PPP.",
                )

    # Verificar tambien las condiciones originales de la reserva.
    # No permitir que una edicion posterior elimine restricciones.
    for association in booking.booking_pets:
        if not is_booking_pet_snapshot_compatible(
            association, profile, booking.service_type
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Las condiciones originales de la reserva no son compatibles con este prestador.",
            )

    # Cobertura obligatoria antes de aceptar un paseo.
    if booking.service_type == ServiceType.WALK:
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
                "provider_id": provider.id,
                "max_radius_km": WALK_MAX_RADIUS_KM,
            },
        ).scalar()
        if within_coverage is not True:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La solicitud esta fuera de tu cobertura o no tenes ubicacion disponible.",
            )

    # El precio aceptado debe ser el registrado al solicitar la reserva.
    # Recalcularlo aqui podria modificar el importe informado al propietario.
    price_total = booking.price_total
    if (
        price_total is None
        or not price_total.is_finite()
        or price_total <= Decimal("0.00")
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La reserva no tiene un precio valido. Requiere revision.",
        )

    fee_rate = get_platform_fee_rate()
    fee = (price_total * fee_rate).quantize(Decimal("0.01"))
    earnings = price_total - fee

    if booking.service_type == ServiceType.TRANSPORT:

        from app.services.transport_schedule import (
            ScheduleConflict,
        )

        conflict = transport_schedule_conflict(
            db,
            provider.id,
            booking,
        )

        if conflict != ScheduleConflict.NONE:

            messages = {
                ScheduleConflict.INVALID_DATA:
                    "No se pudo acreditar la duracion o el horario de tu agenda.",
                ScheduleConflict.EXPIRED_PICKUP:
                    "El horario de retiro de esta solicitud ya paso.",
                ScheduleConflict.OVERLAPPING:
                    "Este traslado se superpone con otro servicio reservado.",
                ScheduleConflict.TRANSFER_UNKNOWN:
                    "No se pudo calcular el desplazamiento entre servicios.",
                ScheduleConflict.INSUFFICIENT_TRANSFER:
                    "No hay tiempo suficiente para llegar al siguiente retiro.",
                ScheduleConflict.ACTIVE_SERVICE:
                    "Tenes un servicio en curso o una reserva vencida sin resolver.",
            }

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=messages.get(
                    conflict,
                    "No se pudo verificar la compatibilidad horaria.",
                ),
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
    if provider.role != UserRole.WALKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el prestador puede iniciar el servicio.",
        )

    # Mismo orden de bloqueos que accept_booking:
    # primero reserva y luego prestador.
    booking = (
        db.query(Booking)
        .filter(Booking.id == booking_id)
        .with_for_update()
        .populate_existing()
        .first()
    )

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva no encontrada",
        )

    if booking.provider_id != provider.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No estás asignado a esta reserva",
        )
    locked_provider = (
        db.query(User)
        .filter(User.id == provider.id)
        .with_for_update()
        .populate_existing()
        .first()
    )

    if (
        locked_provider is None
        or locked_provider.role != UserRole.WALKER
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El prestador no esta disponible.",
        )

    provider = locked_provider

    validate_status_transition(
        booking.status,
        BookingStatus.IN_PROGRESS,
    )

    # La fila del prestador permanece bloqueada hasta
    # finalizar la transaccion. Dos inicios del mismo
    # prestador no pueden superar este control a la vez.
    other_in_progress = (
        db.query(Booking.id)
        .filter(
            Booking.provider_id == provider.id,
            Booking.id != booking.id,
            Booking.status == BookingStatus.IN_PROGRESS,
        )
        .first()
    )

    if other_in_progress is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Ya tenes un servicio en curso. "
                "Debes finalizarlo antes de iniciar otro."
            ),
        )

    expected_provider_type = (
        "walk" if booking.service_type == ServiceType.WALK
        else "transport" if booking.service_type == ServiceType.TRANSPORT
        else None
    )

    if (
        expected_provider_type is None
        or provider.service_type != expected_provider_type
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No estas habilitado para este tipo de servicio.",
        )

    # Revalidar habilitacion y KYC en el momento real de inicio.
    # La aprobacion al aceptar no sustituye este control.
    from app.services.profile_service_access import ensure_profile_services_enabled
    ensure_profile_services_enabled(provider)

    verification = (
        db.query(WalkerVerification)
        .filter(WalkerVerification.user_id == provider.id)
        .order_by(WalkerVerification.id.desc())
        .first()
    )
    if not is_kyc_operationally_approved(verification, provider.service_type):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta debe estar verificada por un administrador para iniciar el servicio.",
        )

    payment = db.query(Payment).filter(Payment.booking_id == booking.id).first()
    if payment is None or payment.status != PaymentStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El servicio no puede iniciarse sin pago aprobado",
        )

    # Un pago aprobado no autoriza un traslado anticipado.
    started_now = _now()

    if booking.service_type == ServiceType.TRANSPORT:
        scheduled = booking.scheduled_pickup_at

        if scheduled is None or scheduled.utcoffset() is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El traslado no tiene un horario de retiro valido.",
            )

        if started_now < scheduled.astimezone(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Todavia no llego el horario programado de retiro.",
            )

    if booking.service_type == ServiceType.TRANSPORT:

        from datetime import timedelta

        from app.services.transport_schedule import (
            ScheduleConflict,
        )

        # Keep a short planning allowance for the time
        # spent checking the road routes.
        # This is not added to the persisted start time.
        validation_allowance = timedelta(seconds=30)

        # The actual-start evaluation must use a time
        # obtained from the server, not the client.
        started_now = _now()

        conflict = transport_schedule_conflict(
            db,
            provider.id,
            booking,
            actual_start_at=started_now,
        )

        if conflict != ScheduleConflict.NONE:

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "No se pudo confirmar que este traslado "
                    "sea compatible con tu agenda actual. "
                    "Revisa tus servicios reservados."
                ),
            )

        checked_at = _now()

        # Avoid using a stale schedule evaluation.
        if (
            checked_at < started_now
            or checked_at - started_now > validation_allowance
        ):

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "La comprobacion de agenda demoro demasiado. "
                    "Intenta iniciar nuevamente."
                ),
            )

        # Persist the time used by the schedule check.
        # All existing start prerequisites remain intact.

    booking.status = BookingStatus.IN_PROGRESS
    booking.started_at = started_now
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
          AND u.profile_review_status = 'clear'
          AND u.service_type = :provider_service_type
          AND NOT EXISTS (
              SELECT 1
              FROM bookings active_b
              WHERE active_b.provider_id = wp.user_id
                AND (
                    active_b.status = :in_progress_status
                    OR (
                        :is_transport = false
                        AND active_b.status = :accepted_status
                    )
                )
          )
          AND (:has_cats = false OR wp.accepts_cats = true)
          AND (:has_ppp = false OR wp.accepts_ppp = true)
          AND (:has_special_needs = false OR wp.accepts_special_needs = true)
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
    # Conservar las restricciones declaradas al crear la reserva.
    # Los datos actuales de las mascotas siguen siendo obligatorios.
    snapshots = tuple(
        association.conditions_snapshot
        for association in booking.booking_pets
        if isinstance(association.conditions_snapshot, dict)
    )

    rows = db.execute(
        sql,
        {
            "booking_id": booking.id,
            "is_transport": is_transport,
            "provider_service_type": "transport" if is_transport else "walk",
            "accepted_status": BookingStatus.ACCEPTED.value,
            "in_progress_status": BookingStatus.IN_PROGRESS.value,
            "has_cats": (
                any(p.species == "cat" for p in pets)
                or any(s.get("species") == "cat" for s in snapshots)
            ),
            "has_ppp": (
                any(p.species == "dog" and p.is_ppp is True for p in pets)
                or any(
                    s.get("species") == "dog" and s.get("is_ppp") is True
                    for s in snapshots
                )
            ),
            "has_special_needs": (
                any(p.has_special_needs is True for p in pets)
                or any(s.get("has_special_needs") is True for s in snapshots)
            ),
            "walk_max_radius_km": WALK_MAX_RADIUS_KM,
        },
    ).all()
    candidate_ids = [r.user_id for r in rows]

    # Solo notificar a prestadores con KYC operativo aprobado.
    # Reutilizar la misma validacion aplicada al aceptar.
    user_ids = []
    if candidate_ids:
        verifications = (
            db.query(WalkerVerification)
            .filter(WalkerVerification.user_id.in_(candidate_ids))
            .order_by(
                WalkerVerification.user_id.asc(),
                WalkerVerification.id.desc(),
            )
            .all()
        )
        verification_by_user = {}

        for verification in verifications:

            # Rows are ordered newest first for each user.
            verification_by_user.setdefault(
                verification.user_id,
                verification,
            )
        required_service = "transport" if is_transport else "walk"

        user_ids = [
            user_id
            for user_id in candidate_ids
            if is_kyc_operationally_approved(
                verification_by_user.get(user_id),
                required_service,
            )
        ]

    if is_transport and user_ids:

        from app.services.transport_schedule import (
            ScheduleConflict,
        )

        # Use the same advisory schedule criteria as Radar
        # and booking detail. No external routing requests.
        # Acceptance still requires the definitive checks.
        user_ids = [
            user_id
            for user_id in user_ids
            if transport_schedule_conflict(
                db,
                user_id,
                booking,
                verify_road_transfer=False,
            ) == ScheduleConflict.NONE
        ]

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