import os, sys, shutil

# ============================================================
# 1) Crear servicio admin_log.py
# ============================================================
SERVICE_PATH = r"C:\woffygo\app\services\admin_log.py"

SERVICE_CONTENT = '''"""Servicio de auditoria: registra acciones de administradores."""
from sqlalchemy.orm import Session

from app.models.admin_action import AdminAction
from app.models.user import User


def log_action(
    db: Session,
    admin: User,
    action: str,
    target_type: str,
    target_id: int | None,
    description: str,
) -> AdminAction:
    """Registra una accion administrativa en el log de auditoria."""
    entry = AdminAction(
        admin_id=admin.id,
        admin_email=admin.email,
        action=action,
        target_type=target_type,
        target_id=target_id,
        description=description[:500],
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
'''

with open(SERVICE_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(SERVICE_CONTENT)
print("[OK] services/admin_log.py")

# ============================================================
# 2) Modificar admin.py: imports + endpoints + logging
# ============================================================
ADMIN_PATH = r"C:\woffygo\app\routers\admin.py"

backup = ADMIN_PATH + ".statslog.bak"
if not os.path.exists(backup):
    shutil.copyfile(ADMIN_PATH, backup)
    print("[BACKUP] " + backup)

with open(ADMIN_PATH, "r", encoding="utf-8") as f:
    src = f.read()

# 2a) Agregar imports
viejo_imports = "from app.models.payment import Payment, PaymentStatus"
nuevo_imports = (
    "from app.models.payment import Payment, PaymentStatus\n"
    "from app.models.admin_action import AdminAction\n"
    "from app.schemas.admin_action import AdminActionResponse, AdminStats\n"
    "from app.services.admin_log import log_action\n"
    "from sqlalchemy import func as sqlfunc, text"
)
if "from app.models.admin_action import AdminAction" in src:
    print("[SKIP] imports ya presentes")
else:
    if viejo_imports not in src:
        print("[FAIL] no encontre imports base")
        sys.exit(1)
    src = src.replace(viejo_imports, nuevo_imports, 1)
    print("[OK] Imports agregados")

# 2b) Modificar clear_walk_flag para loguear
viejo_flag = '''    walk.flagged_for_review = False
    if payload.note:
        walk.flag_reason = f"[REVISADO POR ADMIN] {payload.note}"[:500]
    db.commit()
    db.refresh(walk)
    return walk'''

nuevo_flag = '''    walk.flagged_for_review = False
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

    return walk'''

if viejo_flag in src:
    src = src.replace(viejo_flag, nuevo_flag, 1)
    print("[OK] Logging agregado a clear_walk_flag")
else:
    print("[WARN] no encontre el bloque exacto de clear_walk_flag")

# 2c) Modificar toggle_user_active para loguear
viejo_toggle = '''    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)

    # Devolvemos el detalle actualizado
    return get_user_detail(user.id, current_user, db)'''

nuevo_toggle = '''    user.is_active = payload.is_active
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
    return get_user_detail(user.id, current_user, db)'''

if viejo_toggle in src:
    src = src.replace(viejo_toggle, nuevo_toggle, 1)
    print("[OK] Logging agregado a toggle_user_active")
else:
    print("[WARN] no encontre el bloque exacto de toggle_user_active")

# 2d) Agregar endpoints de stats y actions al final
endpoints = '''

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
'''

src = src.rstrip() + endpoints

with open(ADMIN_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(src)
print("[OK] Endpoints /admin/stats y /admin/actions agregados")

# ============================================================
# 3) Modificar payments.py para loguear resolve_dispute
# ============================================================
PAY_PATH = r"C:\woffygo\app\routers\payments.py"

backup2 = PAY_PATH + ".logresolve.bak"
if not os.path.exists(backup2):
    shutil.copyfile(PAY_PATH, backup2)
    print("[BACKUP] " + backup2)

with open(PAY_PATH, "r", encoding="utf-8") as f:
    pay_src = f.read()

viejo_resolve = '''    return resolve_dispute(
        db,
        payment_id,
        current_user,
        payload.release_to_walker,
        payload.resolution_note,
    )'''

nuevo_resolve = '''    payment = resolve_dispute(
        db,
        payment_id,
        current_user,
        payload.release_to_walker,
        payload.resolution_note,
    )

    # Log de auditoria
    try:
        from app.services.admin_log import log_action
        accion_str = "libero al walker" if payload.release_to_walker else "reembolso al owner"
        log_action(
            db, current_user, "dispute_resolve", "payment", payment.id,
            f"Resolvio disputa del pago #{payment.id} ({accion_str})"
            + (f": {payload.resolution_note}" if payload.resolution_note else ""),
        )
    except Exception as _e:
        print(f"[admin_log] Error logueando dispute_resolve: {_e}")

    return payment'''

if viejo_resolve in pay_src:
    pay_src = pay_src.replace(viejo_resolve, nuevo_resolve, 1)
    with open(PAY_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(pay_src)
    print("[OK] Logging agregado a admin_resolve_payment")
else:
    print("[WARN] no encontre el bloque exacto en payments.py")

print("\n[DONE] PASO 2 completo")