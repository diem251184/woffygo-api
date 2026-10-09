from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, UserRole
from app.models.walk import Walk
from app.schemas.admin import FlagClearRequest, WalkVerificationDetail
from app.schemas.walk import WalkResponse
from app.services.verification import get_verification_summary
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentResponse
from app.schemas.admin import AdminUserListItem, AdminUserDetail, AdminWalkerProfileInfo, ToggleActiveRequest
from app.models.pet import Pet
from app.models.walk import Walk, WalkStatus


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/walks/flagged", response_model=list[WalkResponse])
def list_flagged_walks(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return (
        db.query(Walk)
        .filter(Walk.flagged_for_review.is_(True))
        .order_by(Walk.finished_at.desc().nullslast(), Walk.created_at.desc())
        .all()
    )


@router.get("/walks/{walk_id}/verification", response_model=WalkVerificationDetail)
def get_walk_verification(
    walk_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    walk = db.get(Walk, walk_id)
    if walk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paseo no encontrado",
        )

    summary = get_verification_summary(walk)
    return WalkVerificationDetail(
        walk_id=walk.id,
        owner_id=walk.owner_id,
        walker_id=walk.walker_id,
        status=walk.status.value,
        started_at=walk.started_at,
        finished_at=walk.finished_at,
        duration_minutes_expected=walk.duration_minutes,
        duration_real_minutes=summary["duration_real_minutes"],
        distance_meters=walk.distance_meters,
        avg_speed_kmh=summary["avg_speed_kmh"],
        flagged=summary["flagged"],
        reason=summary["reason"],
    )


@router.post("/walks/{walk_id}/clear-flag", response_model=WalkResponse)
def clear_walk_flag(
    walk_id: int,
    payload: FlagClearRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    walk = db.get(Walk, walk_id)
    if walk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paseo no encontrado",
        )
    if not walk.flagged_for_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este paseo no esta marcado para revision",
        )

    walk.flagged_for_review = False
    if payload.note:
        walk.flag_reason = f"[REVISADO POR ADMIN] {payload.note}"[:500]
    db.commit()
    db.refresh(walk)
    return walk


@router.get("/payments/disputed", response_model=list[PaymentResponse])
def list_disputed_payments(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Lista los pagos con disputa abierta, mas recientes primero."""
    return (
        db.query(Payment)
        .filter(Payment.status == PaymentStatus.DISPUTED)
        .order_by(Payment.dispute_opened_at.desc().nullslast(), Payment.created_at.desc())
        .all()
    )


@router.get("/users", response_model=list[AdminUserListItem])
def list_users(
    role: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Lista usuarios con filtros opcionales.

    - role: owner | walker | admin
    - is_active: true | false
    - search: busca por email o nombre (contiene)
    """
    query = db.query(User)
    if role:
        try:
            query = query.filter(User.role == UserRole(role))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rol invalido: {role}",
            )
    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            (User.email.ilike(like)) | (User.full_name.ilike(like))
        )
    return (
        query.order_by(User.created_at.desc())
        .limit(min(limit, 200))
        .offset(offset)
        .all()
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user_detail(
    user_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Devuelve el detalle de un usuario con contadores y perfil walker."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    # Contadores
    pets_count = db.query(Pet).filter(Pet.owner_id == user.id).count()
    walks_as_owner = db.query(Walk).filter(Walk.owner_id == user.id).count()
    walks_as_walker = db.query(Walk).filter(Walk.walker_id == user.id).count()

    # Perfil walker
    wp_info = None
    wp = user.walker_profile
    if wp is not None:
        lat = lon = None
        try:
            from sqlalchemy import text as _text
            row = db.execute(_text(
                "SELECT ST_Y(CAST(current_location AS geometry)) AS lat, "
                "ST_X(CAST(current_location AS geometry)) AS lon "
                "FROM walker_profiles WHERE user_id = :uid"
            ), {"uid": user.id}).first()
            if row is not None:
                lat = float(row.lat) if row.lat is not None else None
                lon = float(row.lon) if row.lon is not None else None
        except Exception:
            pass
        wp_info = AdminWalkerProfileInfo(
            bio=wp.bio,
            hourly_rate=wp.hourly_rate,
            search_radius_km=wp.search_radius_km,
            is_online=wp.is_online,
            rating_avg=wp.rating_avg,
            total_walks=wp.total_walks,
            current_latitude=lat,
            current_longitude=lon,
        )

    return AdminUserDetail(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        pets_count=pets_count,
        walks_as_owner_count=walks_as_owner,
        walks_as_walker_count=walks_as_walker,
        walker_profile=wp_info,
    )


@router.post("/users/{user_id}/toggle-active", response_model=AdminUserDetail)
def toggle_user_active(
    user_id: int,
    payload: ToggleActiveRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Bloquea o desbloquea un usuario."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No podes bloquearte a vos mismo",
        )
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede bloquear a otro admin",
        )

    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)

    # Devolvemos el detalle actualizado
    return get_user_detail(user.id, current_user, db)
