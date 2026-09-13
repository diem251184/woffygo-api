"""Servicio de paseos: maquina de estados + validaciones de negocio."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models.pet import Pet
from app.models.user import User, UserRole
from app.models.walk import Walk, WalkStatus
from app.models.walk_pet import WalkPet
from app.models.walker_profile import WalkerProfile
from app.schemas.walk import WalkCreate
from app.services.escrow import start_escrow_window
from app.services.verification import verify_walk_integrity


PLATFORM_FEE_RATE = Decimal("0.15")
MAX_PETS_PER_WALK = 3

# Multiplicadores de precio por cantidad de mascotas.
# La 1ra se paga 100%, la 2da al 75%, la 3ra al 50%.
PET_MULTIPLIERS = [Decimal("1.00"), Decimal("0.75"), Decimal("0.50")]

ACTIVE_STATUSES = (WalkStatus.PENDING, WalkStatus.ACCEPTED, WalkStatus.IN_PROGRESS)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_point(latitude: float, longitude: float) -> WKTElement:
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def _get_walk_or_404(db: Session, walk_id: int) -> Walk:
    walk = db.get(Walk, walk_id)
    if walk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paseo no encontrado",
        )
    return walk


def _validate_pets(db: Session, owner: User, pet_ids: list[int]) -> list[Pet]:
    if len(pet_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes seleccionar al menos una mascota",
        )
    if len(pet_ids) > MAX_PETS_PER_WALK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximo {MAX_PETS_PER_WALK} mascotas por paseo",
        )
    pets = db.query(Pet).filter(Pet.id.in_(pet_ids)).all()
    if len(pets) != len(pet_ids):
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
    return pets


def _check_overlap(db: Session, owner: User, duration_minutes: int) -> None:
    """Rechaza si el duenio ya tiene un paseo activo que se solape con ahora."""
    now = _now()
    active_walks = (
        db.query(Walk)
        .filter(Walk.owner_id == owner.id)
        .filter(Walk.status.in_(ACTIVE_STATUSES))
        .all()
    )
    for w in active_walks:
        finish_at = w.requested_at + timedelta(minutes=w.duration_minutes)
        # El nuevo empieza ahora y termina en duration_minutes.
        if finish_at > now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Ya tenes un paseo activo (id={w.id}) que se solapa en horario. "
                    f"Termina aproximadamente a las {finish_at.strftime('%H:%M')}."
                ),
            )


def create_walk(db: Session, owner: User, payload: WalkCreate) -> Walk:
    pets = _validate_pets(db, owner, payload.pet_ids)
    _check_overlap(db, owner, payload.duration_minutes)

    walk = Walk(
        owner_id=owner.id,
        walker_id=None,
        status=WalkStatus.PENDING,
        pickup_location=_make_point(payload.pickup_latitude, payload.pickup_longitude),
        pickup_address=payload.pickup_address,
        duration_minutes=payload.duration_minutes,
        notes=payload.notes,
        price_total=Decimal("0"),
        platform_fee=Decimal("0"),
        walker_earnings=Decimal("0"),
    )
    db.add(walk)
    db.flush()

    for pet in pets:
        db.add(WalkPet(walk_id=walk.id, pet_id=pet.id))

    db.commit()
    db.refresh(walk)
    return walk


def accept_walk(db: Session, walker_user: User, walk_id: int) -> Walk:
    walk = _get_walk_or_404(db, walk_id)

    if walk.status != WalkStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se pueden aceptar paseos pendientes. Estado actual: {walk.status.value}",
        )

    profile = (
        db.query(WalkerProfile).filter(WalkerProfile.user_id == walker_user.id).first()
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Necesitas un perfil de paseador para aceptar paseos",
        )
    if not profile.is_online:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes estar online para aceptar paseos",
        )

    num_pets = len(walk.walk_pets)
    if num_pets == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El paseo no tiene mascotas asignadas",
        )
    if num_pets > len(PET_MULTIPLIERS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cantidad de mascotas invalida",
        )

    hours = Decimal(walk.duration_minutes) / Decimal(60)
    base_price = profile.hourly_rate * hours
    multiplier_sum = sum(PET_MULTIPLIERS[:num_pets], Decimal("0"))
    price = (base_price * multiplier_sum).quantize(Decimal("0.01"))
    fee = (price * PLATFORM_FEE_RATE).quantize(Decimal("0.01"))
    earnings = price - fee

    walk.walker_id = walker_user.id
    walk.status = WalkStatus.ACCEPTED
    walk.accepted_at = _now()
    walk.price_total = price
    walk.platform_fee = fee
    walk.walker_earnings = earnings
    db.commit()
    db.refresh(walk)
    return walk


def start_walk(db: Session, walker_user: User, walk_id: int) -> Walk:
    walk = _get_walk_or_404(db, walk_id)

    if walk.walker_id != walker_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No estas asignado a este paseo",
        )
    if walk.status != WalkStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se pueden iniciar paseos aceptados. Estado actual: {walk.status.value}",
        )

    walk.status = WalkStatus.IN_PROGRESS
    walk.started_at = _now()
    db.commit()
    db.refresh(walk)
    return walk


def finish_walk(db: Session, walker_user: User, walk_id: int) -> Walk:
    walk = _get_walk_or_404(db, walk_id)

    if walk.walker_id != walker_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No estas asignado a este paseo",
        )
    if walk.status != WalkStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se pueden finalizar paseos en proceso. Estado actual: {walk.status.value}",
        )

    walk.status = WalkStatus.COMPLETED
    walk.finished_at = _now()

    profile = (
        db.query(WalkerProfile).filter(WalkerProfile.user_id == walker_user.id).first()
    )
    if profile is not None:
        profile.total_walks = profile.total_walks + 1

    db.commit()
    db.refresh(walk)

    verify_walk_integrity(db, walk)
    start_escrow_window(db, walk.id)

    db.refresh(walk)
    return walk


def cancel_walk(
    db: Session,
    user: User,
    walk_id: int,
    reason: str | None,
) -> Walk:
    walk = _get_walk_or_404(db, walk_id)

    is_owner = walk.owner_id == user.id
    is_walker = walk.walker_id == user.id

    if not (is_owner or is_walker):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No participas en este paseo",
        )

    if walk.status in (WalkStatus.COMPLETED, WalkStatus.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede cancelar un paseo {walk.status.value}",
        )

    if walk.status == WalkStatus.IN_PROGRESS and not is_walker:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el paseador asignado puede cancelar un paseo en curso",
        )

    walk.status = WalkStatus.CANCELLED
    walk.cancelled_at = _now()
    walk.cancel_reason = reason
    db.commit()
    db.refresh(walk)
    return walk


def list_walks_for_user(
    db: Session,
    user: User,
    status_filter: WalkStatus | None = None,
) -> list[Walk]:
    query = db.query(Walk)

    if user.role == UserRole.OWNER:
        query = query.filter(Walk.owner_id == user.id)
    elif user.role == UserRole.WALKER:
        query = query.filter(Walk.walker_id == user.id)

    if status_filter is not None:
        query = query.filter(Walk.status == status_filter)

    return query.order_by(Walk.created_at.desc()).all()


def list_available_walks(db: Session) -> list[Walk]:
    return (
        db.query(Walk)
        .filter(Walk.status == WalkStatus.PENDING)
        .filter(Walk.walker_id.is_(None))
        .order_by(Walk.created_at.asc())
        .all()
    )