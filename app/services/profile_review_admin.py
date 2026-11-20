"""Administrative decisions for user profile review requests.

The caller owns the transaction and must commit or roll back.
This service never changes walker KYC approval or existing bookings.
"""

from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.user_profile_review import UserProfileReview
from app.services.profile_review import (
    INTERNAL_PHOTO_FIELD,
    REVIEWABLE_FIELDS,
)


def resolve_profile_review(
    db: Session,
    *,
    review_id: int,
    admin_id: int,
    approve: bool,
    note: str | None = None,
) -> UserProfileReview:
    """Resolve exactly one pending review under database row locks."""

    if review_id <= 0 or admin_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Identificadores inválidos",
        )

    # Verify administrator server-side, even when caller already did so.
    admin = (
        db.query(User)
        .filter(User.id == admin_id)
        .one_or_none()
    )
    if admin is None or admin.role != UserRole.ADMIN or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere autorización administrativa",
        )

    # Obtain the request owner without mutating or trusting client data.
    review_owner = (
        db.query(UserProfileReview.user_id)
        .filter(UserProfileReview.id == review_id)
        .one_or_none()
    )

    if review_owner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud de revisión inexistente",
        )

    # Lock ordering matches submission: user first, review second.
    user = (
        db.query(User)
        .filter(User.id == review_owner[0])
        .with_for_update()
        .one_or_none()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario de la solicitud inexistente",
        )

    review = (
        db.query(UserProfileReview)
        .filter(UserProfileReview.id == review_id)
        .with_for_update()
        .one_or_none()
    )

    if review is None or review.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La solicitud cambió durante la revisión",
        )

    if review.status != "pending" or user.profile_review_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La solicitud ya fue resuelta o no está pendiente",
        )

    reason = note.strip() if isinstance(note, str) else None

    if not approve and not reason:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Es obligatorio indicar el motivo del rechazo",
        )

    if reason is not None and len(reason) > 2000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La observación administrativa es demasiado extensa",
        )

    allowed = REVIEWABLE_FIELDS | {INTERNAL_PHOTO_FIELD}

    proposed = review.proposed_values

    if not isinstance(proposed, dict) or not proposed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La solicitud no contiene cambios válidos",
        )

    if set(proposed) - allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La solicitud contiene campos no autorizados",
        )

    previous = review.previous_values
    if not isinstance(previous, dict) or set(previous) != set(proposed):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El historial de la solicitud es inconsistente",
        )

    # Detect changes introduced by another workflow after submission.
    for field, earlier_value in previous.items():
        current_value = getattr(user, field)

        if isinstance(current_value, (date, datetime)):
            current_value = current_value.isoformat()

        if current_value != earlier_value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Los datos vigentes cambiaron y requieren revisión manual",
            )

    if approve:
        for field, value in proposed.items():
            if field == "birth_date" and value is not None:
                if not isinstance(value, str):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Formato de fecha pendiente inválido",
                    )
                try:
                    value = date.fromisoformat(value)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Fecha pendiente inválida",
                    )

            if field in ("full_name", "phone"):
                if not isinstance(value, str) or not value.strip():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Datos obligatorios pendientes inválidos",
                    )

            if field == INTERNAL_PHOTO_FIELD:
                if not isinstance(value, str) or not value.startswith("https://"):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Referencia de fotografía pendiente inválida",
                    )

            setattr(user, field, value)

        review.status = "approved"
        user.profile_review_status = "clear"
    else:
        review.status = "rejected"
        user.profile_review_status = "rejected"

    review.reviewed_by_admin_id = admin.id
    review.reviewed_at = datetime.now(timezone.utc)
    review.review_note = reason

    db.add(user)
    db.add(review)
    db.flush()

    return review