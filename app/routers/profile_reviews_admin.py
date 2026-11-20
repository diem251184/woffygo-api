"""Administrator-only endpoints for personal profile review.

Do not include this router in the application until the database
migration and the complete account review workflow are ready.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, UserRole
from app.models.user_profile_review import UserProfileReview
from app.services.profile_review_admin import resolve_profile_review
from app.services.cloudinary_service import pending_avatar_id_from_url, delete_pending_user_avatar


router = APIRouter(
    prefix="/admin/profile-reviews",
    tags=["admin-profile-reviews"],
)


class RejectProfileReviewRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


def _review_response(review: UserProfileReview) -> dict:
    return {
        "id": review.id,
        "user_id": review.user_id,
        "status": review.status,
        "previous_values": review.previous_values,
        "proposed_values": review.proposed_values,
        "submitted_at": review.submitted_at,
        "reviewed_at": review.reviewed_at,
        "reviewed_by_admin_id": review.reviewed_by_admin_id,
        "review_note": review.review_note,
    }


@router.get("")
def list_pending_profile_reviews(
    limit: int = Query(default=30, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """List pending requests for authorized administrators only."""

    query = db.query(UserProfileReview).filter(
        UserProfileReview.status == "pending"
    )

    total = query.count()

    reviews = (
        query
        .order_by(
            UserProfileReview.submitted_at.asc(),
            UserProfileReview.id.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_review_response(review) for review in reviews],
    }


@router.post("/{review_id}/approve")
def approve_profile_review(
    review_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """Approve one pending request and apply its proposed values."""

    try:
        review = resolve_profile_review(
            db,
            review_id=review_id,
            admin_id=current_user.id,
            approve=True,
        )

        response = _review_response(review)
        db.commit()
        return response

    except Exception:
        db.rollback()
        raise


@router.post("/{review_id}/reject")
def reject_profile_review(
    review_id: int,
    payload: RejectProfileReviewRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """Reject a pending request without applying proposed changes."""

    reason = payload.reason.strip()

    if not reason:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Debe indicarse un motivo de rechazo",
        )

    try:
        review = resolve_profile_review(
            db,
            review_id=review_id,
            admin_id=current_user.id,
            approve=False,
            note=reason,
        )

        response = _review_response(review)

        proposed = review.proposed_values
        photo_url = proposed.get("profile_photo_url") if isinstance(proposed, dict) else None
        review_user_id = review.user_id

        # Confirm the rejection before attempting external deletion.
        db.commit()

        response["photo_cleanup_status"] = "not_applicable"

        if photo_url is not None:
            response["photo_cleanup_status"] = "manual_required"

            try:
                public_id = pending_avatar_id_from_url(photo_url, review_user_id)

                if public_id is not None:
                    if delete_pending_user_avatar(public_id, review_user_id):
                        response["photo_cleanup_status"] = "deleted"
            except Exception:
                import logging
                logging.getLogger(__name__).warning(
                    "Pending profile photo cleanup failed after rejection",
                    exc_info=False,
                )

        return response

    except Exception:
        db.rollback()
        raise

@router.post("/{review_id}/retry-photo-cleanup")
def retry_rejected_profile_photo_cleanup(
    review_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """Retry deletion of a rejected pending avatar.

    The rejected review remains the durable recovery record.
    This endpoint does not modify profile or review status.
    """
    import logging

    if review_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Identificador de revisión inválido",
        )

    review = db.get(UserProfileReview, review_id)

    if review is None:
        raise HTTPException(
            status_code=404,
            detail="Solicitud de revisión inexistente",
        )

    if review.status != "rejected":
        raise HTTPException(
            status_code=409,
            detail="Solo se pueden limpiar fotografías de solicitudes rechazadas",
        )

    proposed = review.proposed_values

    if not isinstance(proposed, dict):
        raise HTTPException(
            status_code=409,
            detail="La solicitud no contiene datos válidos",
        )

    photo_url = proposed.get("profile_photo_url")

    if not isinstance(photo_url, str) or not photo_url:
        raise HTTPException(
            status_code=409,
            detail="La solicitud no contiene una fotografía pendiente",
        )

    user = db.get(User, review.user_id)

    if user is None:
        raise HTTPException(
            status_code=409,
            detail="El usuario ya no está disponible",
        )

    # Never delete an image that is currently approved.
    if user.profile_photo_url == photo_url:
        raise HTTPException(
            status_code=409,
            detail="La fotografía está actualmente aprobada y protegida",
        )

    public_id = pending_avatar_id_from_url(
        photo_url,
        review.user_id,
    )

    if public_id is None:
        logging.getLogger(__name__).warning(
            "Rejected profile photo has invalid pending reference"
        )
        return {
            "review_id": review.id,
            "photo_cleanup_status": "manual_required",
        }

    try:
        deleted = delete_pending_user_avatar(
            public_id,
            review.user_id,
        )
    except Exception:
        logging.getLogger(__name__).warning(
            "Rejected pending profile photo cleanup retry failed",
            exc_info=False,
        )
        deleted = False

    return {
        "review_id": review.id,
        "photo_cleanup_status": (
            "deleted" if deleted else "manual_required"
        ),
    }
