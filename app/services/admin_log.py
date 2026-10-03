"""Servicio de auditoria: registra acciones de administradores."""
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
