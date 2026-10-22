import logging
from datetime import datetime, timezone
from decimal import Decimal
import mercadopago
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentInitResponse

logger = logging.getLogger("woffygo.payments")


def _get_mp_sdk() -> mercadopago.SDK:
    token = (settings.MERCADOPAGO_ACCESS_TOKEN or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MERCADOPAGO_ACCESS_TOKEN no configurado en el servidor",
        )
    return mercadopago.SDK(token)


def create_checkout(db: Session, booking: Booking) -> PaymentInitResponse:
    """Crea una preferencia de pago en Mercado Pago."""
    sdk = _get_mp_sdk()
    amount = float(booking.agreed_price)
    public_base = (settings.PUBLIC_BASE_URL or "").rstrip("/")
    if not public_base:
        public_base = "https://woffygo-api.onrender.com"

    service_title = "Paseo de Mascota" if booking.service_type.value == "WALK" else "Traslado Pet Taxi"

    preference_data = {
        "items": [
            {
                "id": f"booking-{booking.id}",
                "title": f"Woffy - {service_title} #{booking.id}",
                "quantity": 1,
                "currency_id": "ARS",
                "unit_price": amount,
            }
        ],
        "payer": {
            "email": booking.owner.email if booking.owner else "cliente@woffygo.com",
            "name": booking.owner.full_name if booking.owner else "Cliente Woffy",
        },
        "external_reference": str(booking.id),
        "back_urls": {
            "success": f"{public_base}/payments/return/success?booking_id={booking.id}",
            "pending": f"{public_base}/payments/return/pending?booking_id={booking.id}",
            "failure": f"{public_base}/payments/return/failure?booking_id={booking.id}",
        },
        "auto_return": "approved",
        "notification_url": f"{public_base}/payments/webhook",
        "statement_descriptor": "WOFFY GO",
    }

    res = sdk.preference().create(preference_data)
    response = res.get("response") or {}
    init_point = response.get("init_point")
    pref_id = response.get("id")

    if not init_point:
        logger.error("Error creando preferencia en Mercado Pago: %s", res)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al iniciar la pasarela de pago en Mercado Pago",
        )

    payment = db.query(Payment).filter(Payment.booking_id == booking.id).first()
    if not payment:
        payment = Payment(
            booking_id=booking.id,
            amount=booking.agreed_price,
            mp_preference_id=pref_id,
            status=PaymentStatus.PENDING,
        )
        db.add(payment)
    else:
        payment.mp_preference_id = pref_id
        payment.amount = booking.agreed_price

    db.commit()
    db.refresh(payment)

    return PaymentInitResponse(
        checkout_url=init_point,
        preference_id=pref_id,
        booking_id=booking.id,
        amount=payment.amount,
    )


def sync_payment_from_mp(db: Session, mp_payment_id: str) -> Payment:
    """
    Sincroniza el estado real de un pago consultando a la API de Mercado Pago.
    Valida moneda, monto, external_reference y evita regresión de estados.
    """
    sdk = _get_mp_sdk()
    res = sdk.payment().get(str(mp_payment_id))
    mp_data = res.get("response") or {}

    if not mp_data or "status" not in mp_data:
        logger.error("Respuesta invalida de MP para pago %s: %s", mp_payment_id, res)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo obtener la informacion del pago desde Mercado Pago",
        )

    external_ref = mp_data.get("external_reference")
    mp_status = mp_data.get("status")
    currency = mp_data.get("currency_id")
    transaction_amount = Decimal(str(mp_data.get("transaction_amount") or "0.00"))

    if not external_ref or not str(external_ref).isdigit():
        logger.error("Pago MP %s no tiene external_reference valido: %s", mp_payment_id, external_ref)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El pago no tiene una reserva asociada valida",
        )

    booking_id = int(external_ref)
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reserva #{booking_id} asociada al pago no encontrada",
        )

    if currency != "ARS":
        logger.error("Moneda invalida en pago %s: %s", mp_payment_id, currency)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Moneda invalida, solo se acepta ARS",
        )

    payment = db.query(Payment).filter(Payment.booking_id == booking_id).first()
    if not payment:
        payment = Payment(
            booking_id=booking_id,
            amount=booking.agreed_price,
            mp_payment_id=str(mp_payment_id),
            status=PaymentStatus.PENDING,
        )
        db.add(payment)
        db.flush()

    # Protección contra regresión de estados finales
    if payment.status in (PaymentStatus.RELEASED, PaymentStatus.DISPUTED):
        logger.info("Pago %s ya en estado final %s. No se modifica.", payment.id, payment.status.value)
        return payment

    payment.mp_payment_id = str(mp_payment_id)
    now = datetime.now(timezone.utc)

    if mp_status == "approved":
        if transaction_amount < booking.agreed_price:
            logger.error(
                "Monto insuficiente en pago %s: cobrado %s, requerido %s",
                mp_payment_id, transaction_amount, booking.agreed_price
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El importe cobrado no cubre el total de la reserva",
            )

        payment.status = PaymentStatus.APPROVED
        payment.approved_at = now
        logger.info("Pago %s aprobado exitosamente para reserva %s", payment.id, booking_id)

    elif mp_status in ("rejected", "cancelled"):
        if payment.status != PaymentStatus.APPROVED:
            payment.status = PaymentStatus.REJECTED

    db.commit()
    db.refresh(payment)
    return payment