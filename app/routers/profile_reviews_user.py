"""User endpoints for administrative review of profile changes.

Do not register this router before database migration and coordinated
replacement of existing direct profile PATCH handlers.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, UserRole
from app.models.user_profile_review import UserProfileReview
from app.schemas.user import UserUpdate
from app.services.profile_review import request_profile_review


router = APIRouter(
    prefix="/profile-reviews",
    tags=["profile-reviews"],
)


@router.post("", status_code=status.HTTP_200_OK)
def submit_profile_review(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Stage personal changes; never immediately replace approved data."""

    if current_user.role not in (UserRole.OWNER, UserRole.WALKER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta operación no corresponde al perfil de la cuenta",
        )

    changes = payload.model_dump(exclude_unset=True)

    # Profile photographs require their own trusted upload process.
    # Never accept arbitrary Cloudinary URLs from a client PATCH.
    if "profile_photo_url" in changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fotografía debe actualizarse mediante el proceso seguro",
        )

    # Required values must never become null.
    for field in ("full_name", "phone"):
        if field in changes and changes[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Nombre y teléfono son obligatorios",
            )

    try:
        review = request_profile_review(
            db,
            user_id=current_user.id,
            changes=changes,
        )

        if review is None:
            # Existing pending state remains unchanged after a no-op.
            account_status = current_user.profile_review_status
            db.commit()
            return {
                "changed": False,
                "review_id": None,
                "profile_review_status": account_status,
            }

        review_id = review.id
        db.commit()

        return {
            "changed": True,
            "review_id": review_id,
            "profile_review_status": "pending",
        }

    except Exception:
        db.rollback()
        raise


@router.get("/me")
def my_profile_review_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Return account status and the user's latest review result."""

    latest = (
        db.query(UserProfileReview)
        .filter(UserProfileReview.user_id == current_user.id)
        .order_by(UserProfileReview.id.desc())
        .first()
    )

    return {
        "profile_review_status": current_user.profile_review_status,
        "latest_review": (
            {
                "id": latest.id,
                "status": latest.status,
                "submitted_at": latest.submitted_at,
                "reviewed_at": latest.reviewed_at,
                "review_note": latest.review_note,
            }
            if latest is not None
            else None
        ),
    }