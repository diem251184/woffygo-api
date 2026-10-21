from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin_or_cron, require_role
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.models.booking import Booking
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
from app.services.mercadopago import (
    create_checkout,
    sync_payment_from_mp,
    verify_mercadopago_signature,
)


router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "/checkout/{booking_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_checkout(
    booking_id: int,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
) -> Payment:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva no encontrada",
        )
    return create_checkout(db, booking, current_user)


@router.get("/{booking_id}", response_model=PaymentResponse)
def get_payment_by_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Payment:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva no encontrada",
        )

    is_owner = booking.owner_id == current_user.id
    is_provider = booking.provider_id == current_user.id
    is_admin = current_user.role == UserRole.ADMIN
    if not (is_owner or is_provider or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso al pago de esta reserva",
        )

    payment = db.query(Payment).filter(Payment.booking_id == booking_id).first()
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Esta reserva no tiene pago iniciado",
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
    current_user: User | None = Depends(require_admin_or_cron),
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

    # Validacion criptografica de firma HMAC
    x_signature = request.headers.get("x-signature")
    x_request_id = request.headers.get("x-request-id")
    if not verify_mercadopago_signature(x_signature, x_request_id, str(data_id)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma de webhook de Mercado Pago invalida",
        )

    try:
        sync_payment_from_mp(db, str(data_id))
    except HTTPException as e:
        return {"status": "error", "detail": e.detail}

    return {"status": "ok"}


@router.get("/return/success")
def return_success(
    booking_id: int = Query(...),
    payment_id: str | None = Query(default=None),
    status_param: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> dict:
    # La URL del navegador nunca confirma el pago por si sola.
    # Se intenta sincronizar si llego payment_id, pero se informa el estado real en BD.
    if payment_id:
        try:
            sync_payment_from_mp(db, payment_id)
        except HTTPException:
            pass

    payment = db.query(Payment).filter(Payment.booking_id == booking_id).first()
    real_status = payment.status.value if payment else "desconocido"
    is_approved = payment is not None and payment.status == PaymentStatus.APPROVED

    return {
        "result": "success" if is_approved else "pending",
        "booking_id": booking_id,
        "payment_id": payment_id,
        "payment_status": real_status,
        "is_approved": is_approved,
    }