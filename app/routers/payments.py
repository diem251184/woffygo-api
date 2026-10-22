import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User
from app.schemas.payment import (
    EscrowReleaseResponse,
    PaymentInitResponse,
    PaymentResponse,
)
from app.services.escrow import (
    dispute_escrow,
    get_payment_by_booking,
    release_escrow,
    release_expired_payments,
)
from app.services.mercadopago import (
    create_checkout,
    sync_payment_from_mp,
)

logger = logging.getLogger("woffygo.payments")
router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/checkout/{booking_id}", response_model=PaymentInitResponse, status_code=status.HTTP_201_CREATED)
def init_checkout(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva no encontrada",
        )

    if booking.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para pagar esta reserva",
        )

    if booking.status not in (BookingStatus.REQUESTED, BookingStatus.ACCEPTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede pagar una reserva en estado {booking.status}",
        )

    return create_checkout(db, booking)


@router.get("/{booking_id}", response_model=PaymentResponse)
def get_payment_status(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva no encontrada",
        )

    is_owner = booking.owner_id == current_user.id
    is_provider = booking.provider_id == current_user.id
    is_admin = current_user.role.value == "admin"

    if not (is_owner or is_provider or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para ver este pago",
        )

    payment = get_payment_by_booking(db, booking_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay registro de pago para esta reserva",
        )
    return payment


@router.post("/webhook")
async def mercadopago_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Webhook robusto de Mercado Pago.
    Actúa como trigger: extrae el ID del recurso y consulta directamente 
    a la API de Mercado Pago con el Access Token privado del servidor 
    para validar autenticidad, moneda, monto y estado real.
    """
    payload: dict = {}
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    params = dict(request.query_params)
    
    # Extraer payment ID según todas las variantes posibles de Mercado Pago
    data_id = (
        (payload.get("data") or {}).get("id")
        or payload.get("id")
        or params.get("data.id")
        or params.get("id")
    )
    
    topic = (
        payload.get("type") 
        or payload.get("topic") 
        or params.get("type") 
        or params.get("topic")
    )

    if not data_id:
        return {"status": "ignored", "reason": "no_data_id"}

    # Ignorar merchant_order u otros tópicos que no impactan directamente el pago
    if topic and topic not in ("payment", "payment.created", "payment.updated"):
        return {"status": "ignored", "reason": f"topic_{topic}"}

    try:
        payment = sync_payment_from_mp(db, str(data_id))
        return {
            "status": "processed", 
            "payment_id": payment.id, 
            "payment_status": payment.status.value,
            "booking_id": payment.booking_id
        }
    except HTTPException as e:
        logger.error("Error validando pago %s contra API de Mercado Pago: %s", data_id, e.detail)
        return {"status": "error", "detail": e.detail}
    except Exception as e:
        logger.exception("Error inesperado procesando webhook para pago %s: %s", data_id, e)
        return {"status": "error", "detail": str(e)}


@router.get("/return/success")
def payment_success_return(
    booking_id: int = Query(...),
    payment_id: Optional[str] = Query(None),
    collection_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Retorno del cliente desde la pasarela.
    Sincroniza de inmediato con la API de Mercado Pago para que 
    la app no dependa exclusivamente de la latencia del webhook.
    """
    mp_id = payment_id or collection_id
    if mp_id:
        try:
            sync_payment_from_mp(db, str(mp_id))
        except Exception as e:
            logger.warning("Fallo sincronización inmediata en retorno de checkout: %s", e)

    payment = db.query(Payment).filter(Payment.booking_id == booking_id).first()
    if payment and payment.status in (PaymentStatus.APPROVED, PaymentStatus.RELEASED):
        return {"result": "success", "booking_id": booking_id, "status": payment.status.value}

    status_val = payment.status.value if payment else "pending"
    return {"result": "pending", "booking_id": booking_id, "status": status_val}


@router.post("/release/{booking_id}", response_model=EscrowReleaseResponse)
def release_payment(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")

    if booking.owner_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Solo el dueño o admin puede liberar el pago")

    return release_escrow(db, booking_id)


@router.post("/dispute/{booking_id}", response_model=PaymentResponse)
def open_dispute(
    booking_id: int,
    reason: str = Query(..., min_length=5, max_length=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")

    if booking.owner_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="No autorizado para abrir disputa")

    return dispute_escrow(db, booking_id, reason)


@router.post("/admin/release-expired")
def trigger_release_expired(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")

    count = release_expired_payments(db, hours)
    return {"released_count": count}