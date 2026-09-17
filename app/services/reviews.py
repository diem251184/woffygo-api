"""Servicio de reviews con recalculo automatico de rating_avg."""
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.review import Review
from app.models.user import User, UserRole
from app.models.walk import Walk, WalkStatus
from app.models.walker_profile import WalkerProfile
from app.schemas.review import ReviewCreate


def _recalculate_walker_rating(db: Session, walker_id: int) -> None:
    """Recalcula rating_avg del WalkerProfile a partir de las reviews."""
    profile = (
        db.query(WalkerProfile).filter(WalkerProfile.user_id == walker_id).first()
    )
    if profile is None:
        return

    avg = (
        db.query(func.avg(Review.rating))
        .filter(Review.walker_id == walker_id)
        .scalar()
    )

    if avg is None:
        profile.rating_avg = Decimal("0.00")
    else:
        profile.rating_avg = Decimal(str(round(float(avg), 2)))

    db.commit()


def create_review(
    db: Session,
    walk_id: int,
    owner: User,
    payload: ReviewCreate,
) -> Review:
    walk = db.get(Walk, walk_id)
    if walk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paseo no encontrado",
        )

    if walk.owner_id != owner.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el duenio del paseo puede dejar una review",
        )

    if walk.status != WalkStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se pueden calificar paseos completados. Estado actual: {walk.status.value}",
        )

    if walk.walker_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El paseo no tiene paseador asignado",
        )

    existing = db.query(Review).filter(Review.walk_id == walk_id).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya calificaste este paseo",
        )

    review = Review(
        walk_id=walk_id,
        owner_id=owner.id,
        walker_id=walk.walker_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    _recalculate_walker_rating(db, walk.walker_id)
    return review


def get_review_by_walk(db: Session, walk_id: int, user: User) -> Review | None:
    walk = db.get(Walk, walk_id)
    if walk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paseo no encontrado",
        )

    is_owner = walk.owner_id == user.id
    is_walker = walk.walker_id == user.id
    is_admin = user.role == UserRole.ADMIN

    if not (is_owner or is_walker or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenes acceso a las reviews de este paseo",
        )

    return db.query(Review).filter(Review.walk_id == walk_id).first()


def list_walker_reviews(
    db: Session,
    walker_id: int,
    limit: int = 50,
) -> list[Review]:
    return (
        db.query(Review)
        .filter(Review.walker_id == walker_id)
        .order_by(Review.created_at.desc())
        .limit(limit)
        .all()
    )
