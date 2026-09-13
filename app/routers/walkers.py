from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.walker_profile import WalkerProfile
from app.schemas.walker import (
    WalkerLocationUpdate,
    WalkerNearbyResult,
    WalkerOnlineToggle,
    WalkerProfileCreate,
    WalkerProfileResponse,
    WalkerProfileUpdate,
)
from app.services.geo import (
    find_nearby_walkers,
    set_walker_online,
    update_walker_location,
)


router = APIRouter(prefix="/walkers", tags=["walkers"])


def _get_or_404_profile(db: Session, user: User) -> WalkerProfile:
    profile = db.query(WalkerProfile).filter(WalkerProfile.user_id == user.id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tenes perfil de paseador. Crealo primero con POST /walkers/profile",
        )
    return profile


@router.post(
    "/profile",
    response_model=WalkerProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
    payload: WalkerProfileCreate,
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
) -> WalkerProfile:
    existing = (
        db.query(WalkerProfile).filter(WalkerProfile.user_id == current_user.id).first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya tenes un perfil de paseador",
        )
    profile = WalkerProfile(
        user_id=current_user.id,
        bio=payload.bio,
        hourly_rate=payload.hourly_rate,
        search_radius_km=payload.search_radius_km,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/profile/me", response_model=WalkerProfileResponse)
def get_my_profile(
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
) -> WalkerProfile:
    return _get_or_404_profile(db, current_user)


@router.patch("/profile/me", response_model=WalkerProfileResponse)
def update_my_profile(
    payload: WalkerProfileUpdate,
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
) -> WalkerProfile:
    profile = _get_or_404_profile(db, current_user)
    if payload.bio is not None:
        profile.bio = payload.bio
    if payload.hourly_rate is not None:
        profile.hourly_rate = payload.hourly_rate
    if payload.search_radius_km is not None:
        profile.search_radius_km = payload.search_radius_km
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/location", response_model=WalkerProfileResponse)
def update_location(
    payload: WalkerLocationUpdate,
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
) -> WalkerProfile:
    profile = _get_or_404_profile(db, current_user)
    return update_walker_location(db, profile, payload.latitude, payload.longitude)


@router.post("/online", response_model=WalkerProfileResponse)
def toggle_online(
    payload: WalkerOnlineToggle,
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
) -> WalkerProfile:
    profile = _get_or_404_profile(db, current_user)
    return set_walker_online(db, profile, payload.is_online)


@router.get("/nearby", response_model=list[WalkerNearbyResult])
def nearby_walkers(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(5.0, gt=0, le=50),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return find_nearby_walkers(db, latitude, longitude, radius_km, limit)