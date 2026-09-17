"""Servicio de eliminacion y anonimizacion de cuenta."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.walk import Walk, WalkStatus
from app.models.walker_profile import WalkerProfile


ACTIVE_WALK_STATUSES = (WalkStatus.PENDING, WalkStatus.ACCEPTED, WalkStatus.IN_PROGRESS)


def delete_account(db: Session, user: User) -> None:
    """Elimina la cuenta del usuario: anonimiza datos personales y desactiva.

    - No se puede eliminar si tiene un paseo activo (pendiente/aceptado/en_proceso).
    - Los pagos, walks y reviews historicas se mantienen (integridad referencial).
    - Email y datos personales se anonimizan.
    """
    active_walks = (
        db.query(Walk)
        .filter(
            (Walk.owner_id == user.id) | (Walk.walker_id == user.id)
        )
        .filter(Walk.status.in_(ACTIVE_WALK_STATUSES))
        .count()
    )
    if active_walks > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No podes eliminar tu cuenta con {active_walks} "
                f"paseo(s) activo(s). Espera a que finalicen o cancelalos."
            ),
        )

    # Si es walker, lo ponemos offline y limpiamos su ubicacion
    if user.role == UserRole.WALKER:
        profile = (
            db.query(WalkerProfile)
            .filter(WalkerProfile.user_id == user.id)
            .first()
        )
        if profile is not None:
            profile.is_online = False
            profile.current_location = None

    # Anonimizar
    user.email = f"deleted_{user.id}@woffygo.local"
    user.full_name = "Usuario Eliminado"
    user.phone = "+0000000000"
    user.password_hash = "!"
    user.is_active = False

    db.commit()
