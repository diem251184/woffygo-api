from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.schemas.review import ReviewCreate, ReviewResponse
from app.services import reviews as reviews_service


router = APIRouter(tags=["reviews"])


@router.post(
    "/walks/{walk_id}/review",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    walk_id: int,
    payload: ReviewCreate,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    return reviews_service.create_review(db, walk_id, current_user, payload)


@router.get("/walks/{walk_id}/review", response_model=ReviewResponse | None)
def get_review_by_walk(
    walk_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return reviews_service.get_review_by_walk(db, walk_id, current_user)


@router.get("/walkers/{walker_id}/reviews", response_model=list[ReviewResponse])
def list_walker_reviews(
    walker_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return reviews_service.list_walker_reviews(db, walker_id, limit)
