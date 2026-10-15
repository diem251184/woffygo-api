from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import mercadopago
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payment import Payment, PaymentStatus
from app.models.user import User
from app.models.booking import Booking, BookingStatus


def _sdk() -> mercadopago.SDK:
    if not settings.MERCADOPAGO_ACCESS_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MercadoPago no está configurado. Falta MERCADOPAGO_ACCESS_TOKEN.",
        )
    return mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)


def _map_mp_status(mp_status: str) -> PaymentStatus:
    mapping = {
        "approved": PaymentStatus.APPROVED,
        "pending": PaymentStatus.PENDING,
        "in_process": PaymentStatus.PENDING,
        "authorized": PaymentStatus.PENDING,
        "rejected": PaymentStatus.REJECTED,
        "cancelled": PaymentStatus.CANCELLED,
        "refunded": PaymentStatus.REFUNDED,
        "charged_back": PaymentStatus.REFUNDED,
    }
    return mapping.get(mp_status, PaymentStatus.PENDING)


def _is_public_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if host in ("127.0.0.1", "localhost", "0.0.0.0", "::1") or host.endswith(".local"):
        return False
    return True


def create_checkout(
    db: Session,
    booking: Booking,
    owner: User,
    base_url: str | None = None,
) -> Payment:
    if base_url is None:
        base_url = settings.PUBLIC_BASE_URL

    if booking.owner_id != owner.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el dueño de la reserva puede iniciar el pago",
        )
    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede pagar una reserva cancelada",
        )
    if booking.provider_id is None or booking.price_total <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La reserva aún no tiene proveedor asignado o precio cotizado",
        )

    existing = db.query(Payment).filter(Payment.booking_id == booking.id).first()
    if existing is not None and existing.status == PaymentStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta reserva ya tiene un pago aprobado",
        )

    sdk = _sdk()
    amount_float = float(booking.price_total)

    preference_data: dict[str, Any] = {
        "items": [
            {
                "title": f"Servicio Woffy Go #{booking.id} ({booking.service_type.value})",
                "description": booking.pickup_address,
                "quantity": 1,
                "currency_id": "ARS",
                "unit_price": amount_float,
            }
        ],
        "external_reference": str(booking.id),
        "statement_descriptor": "WOFFYGO",
    }

    if _is_public_url(base_url):
        preference_data["back_urls"] = {
            "success": f"{base_url}/payments/return/success?booking_id={booking.id}",
            "failure": f"{base_url}/payments/return/failure?booking_id={booking.id}",
            "pending": f"{base_url}/payments/return/pending?booking_id={booking.id}",
        }
        preference_data["auto_return"] = "approved"
        preference_data["notification_url"] = f"{base_url}/payments/webhook"

    try:
        result = sdk.preference().create(preference_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error comunicándose con MercadoPago: {e}",
        )

    if result.get("status") not in (200, 201):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"MercadoPago rechazó la creación de la preferencia: {result}",
        )

    preference = result["response"]
    preference_id = str(preference.get("id"))
    init_point = preference.get("init_point") or preference.get("sandbox_init_point")

    if existing is not None:
        payment = existing
        payment.amount = booking.price_total
        payment.platform_fee = booking.platform_fee
        payment.walker_earnings = booking.provider_earnings
        payment.mp_preference_id = preference_id
        payment.init_point = init_point
        payment.status = PaymentStatus.PENDING
        payment.mp_payment_id = None
        payment.mp_status_detail = None
        payment.approved_at = None
    else:
        payment = Payment(
            booking_id=booking.id,
            payer_id=owner.id,
            amount=booking.price_total,
            platform_fee=booking.platform_fee,
            walker_earnings=booking.provider_earnings,
            status=PaymentStatus.PENDING,
            mp_preference_id=preference_id,
            init_point=init_point,
        )
        db.add(payment)

    db.commit()
    db.refresh(payment)
    return payment


def get_mp_payment(mp_payment_id: str) -> dict:
    sdk = _sdk()
    try:
        result = sdk.payment().get(mp_payment_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error consultando el pago en MercadoPago: {e}",
        )
    if result.get("status") != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"MercadoPago no encontró el pago {mp_payment_id}",
        )
    return result["response"]


def sync_payment_from_mp(db: Session, mp_payment_id: str) -> Payment | None:
    mp_payment = get_mp_payment(mp_payment_id)
    external_reference = mp_payment.get("external_reference")

    payment: Payment | None = None
    if external_reference is not None:
        try:
            booking_id = int(external_reference)
        except (TypeError, ValueError):
            booking_id = None
        if booking_id is not None:
            payment = db.query(Payment).filter(Payment.booking_id == booking_id).first()

    if payment is None:
        payment = (
            db.query(Payment)
            .filter(Payment.mp_payment_id == mp_payment_id)
            .first()
        )
    if payment is None:
        return None

    payment.mp_payment_id = str(mp_payment.get("id"))
    payment.mp_status_detail = mp_payment.get("status_detail")
    new_status = _map_mp_status(mp_payment.get("status", "pending"))
    payment.status = new_status
    if new_status == PaymentStatus.APPROVED and payment.approved_at is None:
        payment.approved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(payment)
    return payment
