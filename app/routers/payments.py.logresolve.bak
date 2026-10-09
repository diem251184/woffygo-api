from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.models.walk import Walk
from app.schemas.payment import (
    PaymentDisputeRequest,
    PaymentResolveRequest,
    PaymentResponse,
)
from app.services.escrow import (
    confirm_delivery,
    open_dispute,
    release_expired_payments,
    release_payment,
    resolve_dispute,
)
from app.services.mercadopago import create_checkout, sync_payment_from_mp


router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "/checkout/{walk_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_checkout(
    walk_id: int,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
) -> Payment:
    walk = db.get(Walk, walk_id)
    if walk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paseo no encontrado",
        )
    return create_checkout(db, walk, current_user)


@router.get("/{walk_id}", response_model=PaymentResponse)
def get_payment_by_walk(
    walk_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Payment:
    walk = db.get(Walk, walk_id)
    if walk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paseo no encontrado",
        )

    is_owner = walk.owner_id == current_user.id
    is_walker = walk.walker_id == current_user.id
    is_admin = current_user.role == UserRole.ADMIN
    if not (is_owner or is_walker or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenes acceso al pago de este paseo",
        )

    payment = db.query(Payment).filter(Payment.walk_id == walk_id).first()
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Este paseo no tiene pago iniciado",
        )
    return payment


@router.post("/{payment_id}/confirm", response_model=PaymentResponse)
def confirm_payment(
    payment_id: int,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
) -> Payment:
    return confirm_delivery(db, payment_id, current_user)


@router.post("/{payment_id}/dispute", response_model=PaymentResponse)
def dispute_payment(
    payment_id: int,
    payload: PaymentDisputeRequest,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
) -> Payment:
    return open_dispute(db, payment_id, current_user, payload.reason)


@router.post("/admin/{payment_id}/resolve", response_model=PaymentResponse)
def admin_resolve_payment(
    payment_id: int,
    payload: PaymentResolveRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> Payment:
    return resolve_dispute(
        db,
        payment_id,
        current_user,
        payload.release_to_walker,
        payload.resolution_note,
    )


@router.post("/admin/release-expired")
def admin_release_expired(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    ids = release_expired_payments(db)
    return {"released_ids": ids, "count": len(ids)}


@router.post("/admin/{payment_id}/release", response_model=PaymentResponse)
def admin_release_payment(
    payment_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> Payment:
    return release_payment(db, payment_id)


@router.post("/webhook")
async def mercadopago_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    payload: dict = {}
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            payload = await request.json()
    except Exception:
        payload = {}

    topic = (
        payload.get("type")
        or payload.get("topic")
        or request.query_params.get("type")
        or request.query_params.get("topic")
    )

    data_id = (
        (payload.get("data") or {}).get("id")
        or request.query_params.get("data.id")
        or request.query_params.get("id")
    )

    if topic != "payment" or not data_id:
        return {"status": "ignored", "reason": "no es un evento de pago"}

    try:
        sync_payment_from_mp(db, str(data_id))
    except HTTPException as e:
        return {"status": "error", "detail": e.detail}

    return {"status": "ok"}


@router.get("/return/success")
def return_success(
    walk_id: int = Query(...),
    payment_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    if payment_id:
        try:
            sync_payment_from_mp(db, payment_id)
        except HTTPException:
            pass
    return {
        "result": "success",
        "walk_id": walk_id,
        "payment_id": payment_id,
        "mp_status": status,
    }


@router.get("/return/failure")
def return_failure(
    walk_id: int = Query(...),
    payment_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict:
    return {
        "result": "failure",
        "walk_id": walk_id,
        "payment_id": payment_id,
        "mp_status": status,
    }


@router.get("/return/pending")
def return_pending(
    walk_id: int = Query(...),
    payment_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict:
    return {
        "result": "pending",
        "walk_id": walk_id,
        "payment_id": payment_id,
        "mp_status": status,
    }