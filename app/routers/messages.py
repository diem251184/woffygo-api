from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.message import Message
from app.models.user import User, UserRole
from app.models.walk import Walk, WalkStatus
from app.schemas.message import MessageCreate, MessageResponse
from app.services.chat_filter import filter_contact_info


router = APIRouter(prefix="/walks/{walk_id}/messages", tags=["messages"])


CHAT_ALLOWED_STATUSES = {
    WalkStatus.ACCEPTED,
    WalkStatus.IN_PROGRESS,
    WalkStatus.COMPLETED,
}


def _get_walk_or_404(db: Session, walk_id: int) -> Walk:
    walk = db.get(Walk, walk_id)
    if walk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paseo no encontrado",
        )
    return walk


def _ensure_participant(walk: Walk, user: User) -> None:
    """Valida que el user sea duenio o paseador del paseo (o admin)."""
    is_owner = walk.owner_id == user.id
    is_walker = walk.walker_id == user.id
    is_admin = user.role == UserRole.ADMIN
    if not (is_owner or is_walker or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No participas en este paseo",
        )


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def send_message(
    walk_id: int,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    walk = _get_walk_or_404(db, walk_id)
    _ensure_participant(walk, current_user)

    if current_user.role != UserRole.ADMIN and walk.status not in CHAT_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El chat no esta disponible en estado {walk.status.value}",
        )

    filtered, was_blocked, reason = filter_contact_info(payload.text)

    msg = Message(
        walk_id=walk.id,
        sender_id=current_user.id,
        text=payload.text,
        filtered_text=filtered,
        was_blocked=was_blocked,
        block_reason=reason,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.get("", response_model=list[MessageResponse])
def list_messages(
    walk_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Message]:
    walk = _get_walk_or_404(db, walk_id)
    _ensure_participant(walk, current_user)

    return (
        db.query(Message)
        .filter(Message.walk_id == walk.id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )