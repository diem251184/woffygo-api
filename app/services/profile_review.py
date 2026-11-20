"""Centralized requests for administrative review of profile changes.

This module does not approve changes, commit transactions, or execute
database migrations. Callers must control the database transaction.
"""

from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_profile_review import UserProfileReview


REVIEWABLE_FIELDS = frozenset(
    {
        "full_name",
        "phone",
        "dni_number",
        "address",
        "birth_date",
        "emergency_contact",
    }
)

INTERNAL_PHOTO_FIELD = "profile_photo_url"


def _json_value(value):
    """Convert supported profile values into JSON-compatible values."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Valor de perfil no admitido",
    )


def request_profile_review(
    db: Session,
    *,
    user_id: int,
    changes: dict,
    allow_internal_photo: bool = False,
) -> UserProfileReview | None:
    """Stage actual changes without overwriting approved user fields.

    Returns None when all supplied values are unchanged.
    Does not commit: the caller must commit or roll back atomically.

    Photo URL updates are excluded from ordinary profile PATCH requests.
    Only a trusted server-side photo workflow may enable that field.
    """
    if not isinstance(changes, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Formato de actualización inválido",
        )

    allowed = set(REVIEWABLE_FIELDS)
    if allow_internal_photo:
        allowed.add(INTERNAL_PHOTO_FIELD)

    unknown = set(changes) - allowed
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La solicitud contiene campos no permitidos",
        )

    # Lock first so concurrent requests by the same user serialize.
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .with_for_update()
        .one_or_none()
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    if user.profile_review_status not in ("clear", "pending", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Estado de revisión de perfil no reconocido",
        )

    previous_values = {}
    proposed_values = {}

    for field, proposed in changes.items():
        old = getattr(user, field)
        if _json_value(old) == _json_value(proposed):
            continue
        previous_values[field] = _json_value(old)
        proposed_values[field] = _json_value(proposed)

    # No-op submissions must never suspend an account.
    if not proposed_values:
        return None

    if user.profile_review_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una revisión de perfil pendiente",
        )

    # Protect the database invariant as well as the status flag.
    existing = (
        db.query(UserProfileReview.id)
        .filter(
            UserProfileReview.user_id == user.id,
            UserProfileReview.status == "pending",
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una solicitud de revisión pendiente",
        )

    review = UserProfileReview(
        user_id=user.id,
        status="pending",
        previous_values=previous_values,
        proposed_values=proposed_values,
    )

    user.profile_review_status = "pending"

    db.add(review)
    db.add(user)
    db.flush()
    return review