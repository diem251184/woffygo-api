from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, UserRole
from app.models.walk import Walk
from app.schemas.admin import FlagClearRequest, WalkVerificationDetail
from app.schemas.walk import WalkResponse
from app.services.verification import get_verification_summary


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/walks/flagged", response_model=list[WalkResponse])
def list_flagged_walks(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return (
        db.query(Walk)
        .filter(Walk.flagged_for_review.is_(True))
        .order_by(Walk.finished_at.desc().nullslast(), Walk.created_at.desc())
        .all()
    )


@router.get("/walks/{walk_id}/verification", response_model=WalkVerificationDetail)
def get_walk_verification(
    walk_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    walk = db.get(Walk, walk_id)
    if walk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paseo no encontrado",
        )

    summary = get_verification_summary(walk)
    return WalkVerificationDetail(
        walk_id=walk.id,
        owner_id=walk.owner_id,
        walker_id=walk.walker_id,
        status=walk.status.value,
        started_at=walk.started_at,
        finished_at=walk.finished_at,
        duration_minutes_expected=walk.duration_minutes,
        duration_real_minutes=summary["duration_real_minutes"],
        distance_meters=walk.distance_meters,
        avg_speed_kmh=summary["avg_speed_kmh"],
        flagged=summary["flagged"],
        reason=summary["reason"],
    )


@router.post("/walks/{walk_id}/clear-flag", response_model=WalkResponse)
def clear_walk_flag(
    walk_id: int,
    payload: FlagClearRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    walk = db.get(Walk, walk_id)
    if walk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paseo no encontrado",
        )
    if not walk.flagged_for_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este paseo no esta marcado para revision",
        )

    walk.flagged_for_review = False
    if payload.note:
        walk.flag_reason = f"[REVISADO POR ADMIN] {payload.note}"[:500]
    db.commit()
    db.refresh(walk)
    return walk