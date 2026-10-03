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
from app.models.admin_action import AdminAction
from app.schemas.admin_action import AdminActionResponse, AdminStats
from app.services.admin_log import log_action
from app.models.safety_report import SafetyReport
from app.schemas.safety_report import SafetyReportAdminResponse, SafetyReportDeleteRequest
from sqlalchemy import func as sqlfunc, text
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

    try:
        log_action(
            db, current_user, "flag_clear", "walk", walk.id,
            f"Limpio flag del paseo #{walk.id}" + (f": {payload.note}" if payload.note else ""),
        )
    except Exception as _e:
        print(f"[admin_log] Error logueando flag_clear: {_e}")

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

    accion_str = "Desbloqueo" if payload.is_active else "Bloqueo"
    try:
        log_action(
            db, current_user,
            "user_unblock" if payload.is_active else "user_block",
            "user", user.id,
            f"{accion_str} a {user.email} ({user.full_name})",
        )
    except Exception as _e:
        print(f"[admin_log] Error logueando toggle_active: {_e}")

    # Devolvemos el detalle actualizado
    return get_user_detail(user.id, current_user, db)

# ============================================
# Estadisticas y auditoria
# ============================================


@router.get("/stats", response_model=AdminStats)
def get_admin_stats(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Contadores agregados para el dashboard del panel admin."""
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Usuarios
    users_total = db.query(User).count()
    users_active = db.query(User).filter(User.is_active.is_(True)).count()
    users_owners = db.query(User).filter(User.role == UserRole.OWNER).count()
    users_walkers = db.query(User).filter(User.role == UserRole.WALKER).count()
    users_admins = db.query(User).filter(User.role == UserRole.ADMIN).count()

    # Walkers online
    walkers_online_now = 0
    try:
        from app.models.walker_profile import WalkerProfile
        walkers_online_now = (
            db.query(WalkerProfile)
            .filter(WalkerProfile.is_online.is_(True))
            .count()
        )
    except Exception:
        pass

    # Paseos
    walks_total = db.query(Walk).count()
    walks_pending = db.query(Walk).filter(Walk.status == WalkStatus.PENDING).count()
    walks_accepted = db.query(Walk).filter(Walk.status == WalkStatus.ACCEPTED).count()
    walks_in_progress = db.query(Walk).filter(Walk.status == WalkStatus.IN_PROGRESS).count()
    walks_completed = db.query(Walk).filter(Walk.status == WalkStatus.COMPLETED).count()
    walks_cancelled = db.query(Walk).filter(Walk.status == WalkStatus.CANCELLED).count()
    walks_today = db.query(Walk).filter(Walk.created_at >= today_start).count()
    walks_this_month = db.query(Walk).filter(Walk.created_at >= month_start).count()

    # Dinero
    revenue_total = db.query(sqlfunc.coalesce(sqlfunc.sum(Payment.platform_fee), 0)).filter(
        Payment.status == PaymentStatus.RELEASED
    ).scalar() or Decimal("0")

    revenue_this_month = db.query(sqlfunc.coalesce(sqlfunc.sum(Payment.platform_fee), 0)).filter(
        Payment.status == PaymentStatus.RELEASED,
        Payment.released_at >= month_start,
    ).scalar() or Decimal("0")

    escrow_pending_total = db.query(sqlfunc.coalesce(sqlfunc.sum(Payment.amount), 0)).filter(
        Payment.status == PaymentStatus.APPROVED,
        Payment.payment_release_deadline.isnot(None),
    ).scalar() or Decimal("0")

    disputed_total = db.query(sqlfunc.coalesce(sqlfunc.sum(Payment.amount), 0)).filter(
        Payment.status == PaymentStatus.DISPUTED
    ).scalar() or Decimal("0")

    # Moderacion
    flagged_walks = db.query(Walk).filter(Walk.flagged_for_review.is_(True)).count()
    disputed_payments = db.query(Payment).filter(
        Payment.status == PaymentStatus.DISPUTED
    ).count()

    return AdminStats(
        users_total=users_total,
        users_active=users_active,
        users_owners=users_owners,
        users_walkers=users_walkers,
        users_admins=users_admins,
        walkers_online_now=walkers_online_now,
        walks_total=walks_total,
        walks_pending=walks_pending,
        walks_accepted=walks_accepted,
        walks_in_progress=walks_in_progress,
        walks_completed=walks_completed,
        walks_cancelled=walks_cancelled,
        walks_today=walks_today,
        walks_this_month=walks_this_month,
        revenue_total=str(revenue_total),
        revenue_this_month=str(revenue_this_month),
        escrow_pending_total=str(escrow_pending_total),
        disputed_total=str(disputed_total),
        flagged_walks=flagged_walks,
        disputed_payments=disputed_payments,
    )


@router.get("/actions", response_model=list[AdminActionResponse])
def list_admin_actions(
    limit: int = 100,
    offset: int = 0,
    action: str | None = None,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Historial de acciones administrativas, mas recientes primero."""
    query = db.query(AdminAction)
    if action:
        query = query.filter(AdminAction.action == action)
    return (
        query.order_by(AdminAction.created_at.desc())
        .limit(min(limit, 200))
        .offset(offset)
        .all()
    )

# ============================================
# Reportes de seguridad
# ============================================


@router.get("/safety-reports", response_model=list[SafetyReportAdminResponse])
def list_safety_reports(
    include_deleted: bool = False,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Lista reportes de seguridad. Por defecto solo los activos."""
    q = db.query(SafetyReport)
    if not include_deleted:
        q = q.filter(SafetyReport.deleted.is_(False))
    rows = q.order_by(SafetyReport.created_at.desc()).limit(200).all()

    out = []
    for r in rows:
        reporter_name = "Usuario"
        try:
            u = db.get(User, r.reporter_id)
            if u is not None:
                reporter_name = u.full_name
        except Exception:
            pass
        out.append(SafetyReportAdminResponse(
            id=r.id,
            category=r.category,
            description=r.description,
            latitude=r.latitude,
            longitude=r.longitude,
            verified=r.verified,
            created_at=r.created_at,
            expires_at=r.expires_at,
            reporter_id=r.reporter_id,
            reporter_name=reporter_name,
            reporter_role=r.reporter_role,
            walk_id=r.walk_id,
            deleted=r.deleted,
            deleted_reason=r.deleted_reason,
        ))
    return out


@router.post("/safety-reports/{report_id}/verify", response_model=SafetyReportAdminResponse)
def verify_safety_report(
    report_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Marca un reporte como verificado (util para destacar reportes validos)."""
    r = db.get(SafetyReport, report_id)
    if r is None or r.deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado")

    r.verified = True
    db.commit()
    db.refresh(r)

    try:
        log_action(db, current_user, "safety_verify", "safety_report", r.id,
                   f"Verifico el reporte #{r.id} ({r.category.value})")
    except Exception as _e:
        print(f"[admin_log] Error logueando safety_verify: {_e}")

    reporter_name = "Usuario"
    try:
        u = db.get(User, r.reporter_id)
        if u is not None:
            reporter_name = u.full_name
    except Exception:
        pass

    return SafetyReportAdminResponse(
        id=r.id, category=r.category, description=r.description,
        latitude=r.latitude, longitude=r.longitude, verified=r.verified,
        created_at=r.created_at, expires_at=r.expires_at,
        reporter_id=r.reporter_id, reporter_name=reporter_name,
        reporter_role=r.reporter_role, walk_id=r.walk_id,
        deleted=r.deleted, deleted_reason=r.deleted_reason,
    )


@router.delete("/safety-reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_safety_report(
    report_id: int,
    payload: SafetyReportDeleteRequest = None,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Elimina (soft delete) un reporte de seguridad."""
    r = db.get(SafetyReport, report_id)
    if r is None or r.deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado")

    r.deleted = True
    r.deleted_reason = (payload.reason if payload and payload.reason else "Eliminado por admin")[:300]
    db.commit()

    try:
        log_action(db, current_user, "safety_delete", "safety_report", r.id,
                   f"Elimino el reporte #{r.id} ({r.category.value}): {r.deleted_reason}")
    except Exception as _e:
        print(f"[admin_log] Error logueando safety_delete: {_e}")

    return None
