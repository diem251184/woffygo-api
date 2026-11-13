from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4, UUID
import hmac
import hashlib
from typing import Any
from urllib.parse import urlparse

import mercadopago
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payment import Payment, PaymentStatus
from app.models.payment_status_event import PaymentStatusEvent
from app.models.payment_attempt import PaymentAttempt
from app.models.payment_attempt_charge import PaymentAttemptCharge
from app.models.user import User
from app.models.booking import Booking, BookingStatus

# No habilitar hasta validar webhooks por intento.
PAYMENT_ATTEMPT_WEBHOOK_READY = False
LEGACY_PAYMENT_SYNC_READY = False
PAYMENT_RECONCILIATION_READY = False


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
        "charged_back": PaymentStatus.CHARGED_BACK,
    }
    if mp_status not in mapping:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Estado de Mercado Pago desconocido",
        )
    return mapping[mp_status]


def _is_public_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if host in ("127.0.0.1", "localhost", "0.0.0.0", "::1") or host.endswith(".local"):
        return False
    return True


def verify_mercadopago_signature(
    x_signature: str | None,
    x_request_id: str | None,
    data_id: str | None,
) -> bool:
    """Valida la firma HMAC-SHA256 enviada por Mercado Pago en el webhook."""
    import logging
    hmac_log = logging.getLogger(__name__)
    secret = (getattr(settings, "MERCADOPAGO_WEBHOOK_SECRET", None) or "").strip()
    if not secret:
        # Sin secreto configurado, ninguna firma puede validarse.
        hmac_log.warning("MP_WEBHOOK_HMAC_REJECT: SECRET_MISSING")
        return False

    if not x_signature or not data_id:
        hmac_log.warning("MP_WEBHOOK_HMAC_REJECT: SIGNATURE_OR_ID_MISSING")
        return False

    parts = {}
    for item in x_signature.split(","):
        if "=" in item:
            k, v = item.strip().split("=", 1)
            parts[k] = v

    ts = parts.get("ts")
    v1 = parts.get("v1")
    if not ts or not v1:
        hmac_log.warning("MP_WEBHOOK_HMAC_REJECT: SIGNATURE_PARTS_MISSING")
        return False

    # Validacion temporal conservadora de webhooks.
    # MP puede reenviar notificaciones dias despues.
    # La idempotencia persistente se controla aparte.
    if not ts.isascii() or not ts.isdecimal():
        hmac_log.warning("MP_WEBHOOK_HMAC_REJECT: TIMESTAMP_FORMAT")
        return False
    if len(ts) not in (10, 13):
        hmac_log.warning("MP_WEBHOOK_HMAC_REJECT: TIMESTAMP_LENGTH")
        return False

    timestamp = int(ts)
    if len(ts) == 13:
        timestamp /= 1000

    now_timestamp = datetime.now(timezone.utc).timestamp()
    max_past_seconds = 30 * 24 * 60 * 60
    max_future_seconds = 5 * 60

    if not (
        now_timestamp - max_past_seconds <= timestamp
        <= now_timestamp + max_future_seconds
    ):
        hmac_log.warning("MP_WEBHOOK_HMAC_REJECT: TIMESTAMP_OUT_OF_RANGE")
        return False

    manifest = f"id:{data_id};"
    if x_request_id:
        manifest += f"request-id:{x_request_id};"
    manifest += f"ts:{ts};"
    computed = hmac.new(
        secret.encode("utf-8"),
        manifest.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    valid = hmac.compare_digest(computed, v1)
    if not valid:
        hmac_log.warning("MP_WEBHOOK_HMAC_REJECT: DIGEST_MISMATCH")
        if not x_request_id:
            hmac_log.warning("MP_WEBHOOK_HMAC_DIAG: REQUEST_ID_ABSENT")
        else:
            alt_manifest = f"id:{data_id};ts:{ts};"
            alt_digest = hmac.new(
                secret.encode("utf-8"),
                alt_manifest.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if hmac.compare_digest(alt_digest, v1):
                hmac_log.warning("MP_WEBHOOK_HMAC_DIAG: ALT_NO_REQUEST_MATCH")
            else:
                hmac_log.warning("MP_WEBHOOK_HMAC_DIAG: ALT_NO_REQUEST_MISMATCH")
    return valid


def create_checkout(
    db: Session,
    booking: Booking,
    owner: User,
    base_url: str | None = None,
) -> Payment:
    # Bloqueo temporal: el webhook todavia no entiende
    # referencias individuales por intento.
    if not PAYMENT_ATTEMPT_WEBHOOK_READY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Checkout temporalmente suspendido durante la integracion segura",
        )

    # Acceso adicional y cerrado por defecto para checkout TEST.
    from os import environ
    qa_enabled = environ.get("WOFFY_MP_TEST_CHECKOUT_ENABLED") == "1"
    qa_raw_ids = environ.get("WOFFY_MP_TEST_OWNER_IDS", "")
    qa_ids = [item.strip() for item in qa_raw_ids.split(",")]
    qa_ids_valid = (
        bool(qa_raw_ids)
        and all(item.isascii() and item.isdecimal() for item in qa_ids)
    )
    if (
        not qa_enabled
        or not qa_ids_valid
        or str(owner.id) not in qa_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Checkout restringido a pruebas autorizadas",
        )

    if base_url is None:
        base_url = settings.PUBLIC_BASE_URL

    # Serializar checkouts de una reserva y releer su estado actual.
    booking_id = booking.id
    booking = (
        db.query(Booking)
        .filter(Booking.id == booking_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva no encontrada",
        )

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

    existing = (
        db.query(Payment)
        .filter(Payment.booking_id == booking.id)
        .populate_existing()
        .first()
    )
    if existing is not None and existing.status in (
        PaymentStatus.APPROVED,
        PaymentStatus.RELEASED,
        PaymentStatus.DISPUTED,
        PaymentStatus.REFUNDED,
        PaymentStatus.CHARGED_BACK,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta reserva tiene un pago aprobado, liberado, en disputa o reembolsado",
        )

    # No reutilizar intentos externos rechazados o cancelados.
    # La reemision segura requiere historial por intento.
    if existing is not None and existing.status in (
        PaymentStatus.REJECTED,
        PaymentStatus.CANCELLED,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El intento anterior no puede reutilizarse; requiere un nuevo intento de pago seguro",
        )
    # Reutilizar un checkout pendiente para evitar preferencias duplicadas.
    if existing is not None and existing.status == PaymentStatus.PENDING:
        if (
            existing.amount != booking.price_total
            or existing.platform_fee != booking.platform_fee
            or existing.walker_earnings != booking.provider_earnings
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Checkout pendiente con importes diferentes a la reserva",
            )
        if existing.mp_preference_id and existing.init_point:
            return existing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pago pendiente sin enlace verificable; requiere revision",
        )

    sdk = _sdk()
    amount_float = float(booking.price_total)
    attempt_key = uuid4().hex

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
        "external_reference": f"{booking.id}:{attempt_key}",
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
            detail="No se pudo crear la preferencia de pago",
        )

    if result.get("status") not in (200, 201):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo crear la preferencia de pago",
        )

    preference = result["response"]
    raw_preference_id = preference.get("id")
    init_point = preference.get("init_point") or preference.get("sandbox_init_point")
    if not raw_preference_id or not isinstance(init_point, str) or not init_point:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Mercado Pago devolvio una preferencia incompleta",
        )
    preference_id = str(raw_preference_id)

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

    db.flush()
    db.add(
        PaymentAttempt(
            payment_id=payment.id,
            attempt_key=attempt_key,
            mp_preference_id=preference_id,
            mp_payment_id=None,
            status="created",
            amount=booking.price_total,
            currency="ARS",
        )
    )
    db.commit()
    db.refresh(payment)
    return payment


def prepare_mp_full_refund_request(
    mp_payment_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    """Prepara un reembolso total; nunca lo envia a Mercado Pago.

    La clave debe proceder de una solicitud registrada previamente.
    No generar una clave nueva al reintentar la misma operacion.
    """
    if (
        not isinstance(mp_payment_id, str)
        or not mp_payment_id
        or not mp_payment_id.isascii()
        or not mp_payment_id.isdecimal()
        or int(mp_payment_id) <= 0
    ):
        raise ValueError("Identificador de cobro invalido")

    if not isinstance(idempotency_key, str):
        raise ValueError("Clave de idempotencia invalida")

    try:
        parsed_key = UUID(idempotency_key)
    except (ValueError, AttributeError):
        raise ValueError("Clave de idempotencia invalida") from None

    if parsed_key.version != 4 or str(parsed_key) != idempotency_key:
        raise ValueError("Se requiere una clave UUID v4 canonica")

    return {
        "method": "POST",
        "path": f"/v1/payments/{mp_payment_id}/refunds",
        "headers": {"X-Idempotency-Key": idempotency_key},
        "json": {},
    }


def get_mp_payment(mp_payment_id: str) -> dict:
    """Consulta un cobro sin exponer detalles internos del proveedor."""
    try:
        sdk = _sdk()
        result = sdk.payment().get(mp_payment_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo consultar Mercado Pago",
        ) from None

    if (
        not isinstance(result, dict)
        or type(result.get("status")) is not int
        or result.get("status") != 200
        or not isinstance(result.get("response"), dict)
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Respuesta invalida de Mercado Pago",
        )

    return result["response"]


FINAL_OR_PROTECTED_STATUSES = {
    PaymentStatus.APPROVED,
    PaymentStatus.RELEASED,
    PaymentStatus.DISPUTED,
    PaymentStatus.REFUNDED,
    PaymentStatus.CHARGED_BACK,
}


def _parse_mp_external_reference(
    external_reference: str,
) -> tuple[int, str | None]:
    """Interpreta referencias antiguas o individuales.

    Formato anterior: booking_id
    Formato nuevo: booking_id:uuid_hex
    """
    if not isinstance(external_reference, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Referencia externa invalida",
        )

    parts = external_reference.split(":")

    if len(parts) not in (1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de referencia externa invalido",
        )

    booking_text = parts[0]

    if (
        not booking_text
        or len(booking_text) > 20
        or not all("0" <= char <= "9" for char in booking_text)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identificador de reserva invalido",
        )

    booking_id = int(booking_text)

    if booking_id <= 0 or booking_id > 9223372036854775807:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identificador de reserva fuera de rango",
        )

    if len(parts) == 1:
        return booking_id, None

    attempt_key = parts[1]

    if (
        len(attempt_key) != 32
        or not all(
            char in "0123456789abcdef"
            for char in attempt_key
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identificador de intento invalido",
        )

    return booking_id, attempt_key


def _classify_payment_charge_statuses(
    charge_statuses: list[str],
) -> str:
    """Clasificacion conservadora; no modifica estados contables.

    Devuelve:
      no_approval
      single_approved_candidate
      duplicate_approved_review
      manual_review

    La candidatura no autoriza actualizar Payment.
    """
    statuses = list(charge_statuses)

    recognized = {
        PaymentStatus.PENDING.value,
        PaymentStatus.APPROVED.value,
        PaymentStatus.REJECTED.value,
        PaymentStatus.CANCELLED.value,
        PaymentStatus.REFUNDED.value,
        PaymentStatus.CHARGED_BACK.value,
    }

    if any(
        not isinstance(item, str) or item not in recognized
        for item in statuses
    ):
        return "manual_review"

    approved_count = statuses.count(PaymentStatus.APPROVED.value)

    if approved_count > 1:
        return "duplicate_approved_review"

    if any(
        item in (
            PaymentStatus.REFUNDED.value,
            PaymentStatus.CHARGED_BACK.value,
        )
        for item in statuses
    ):
        return "manual_review"

    if approved_count == 1:
        if len(statuses) == 1:
            return "single_approved_candidate"
        return "manual_review"

    return "no_approval"


def _stage_reconciled_approval(
    db,
    payment: Payment,
    attempt: PaymentAttempt,
    charge: PaymentAttemptCharge,
    decision: str,
) -> bool:
    """Prepara una aprobacion y su evento sin ejecutar commit."""
    if decision != "single_approved_candidate":
        return False

    if (
        payment.status != PaymentStatus.PENDING
        or payment.mp_payment_id is not None
        or payment.approved_at is not None
    ):
        return False

    if (
        attempt.payment_id != payment.id
        or charge.attempt_id != attempt.id
        or not attempt.mp_preference_id
        or attempt.status in ("manual_review", "duplicate_approved_review")
    ):
        return False

    if (
        charge.status != PaymentStatus.APPROVED.value
        or charge.currency != "ARS"
        or charge.amount is None
        or charge.amount != payment.amount
        or charge.amount != attempt.amount
        or attempt.currency != "ARS"
    ):
        return False

    mp_id = charge.mp_payment_id
    if not isinstance(mp_id, str) or not mp_id or len(mp_id) > 120:
        return False

    event_key = "mp-approved:" + mp_id
    if len(event_key) > 160:
        return False

    existing_event = (
        db.query(PaymentStatusEvent)
        .filter(
            PaymentStatusEvent.payment_id == payment.id,
            PaymentStatusEvent.event_key == event_key,
        )
        .first()
    )
    if existing_event is not None:
        return False

    event = PaymentStatusEvent(
        payment_id=payment.id,
        previous_status=payment.status.value,
        new_status=PaymentStatus.APPROVED.value,
        event_source="mercadopago",
        event_key=event_key,
        mp_payment_id=mp_id,
    )

    payment.mp_payment_id = mp_id
    payment.status = PaymentStatus.APPROVED
    payment.approved_at = datetime.now(timezone.utc)
    db.add(event)
    return True


def sync_payment_from_mp(db: Session, mp_payment_id: str) -> Payment | None:
    """Sincroniza el estado del pago validando correspondencia, importe, moneda y protegiendo de regresiones."""
    mp_payment = get_mp_payment(mp_payment_id)
    external_reference = mp_payment.get("external_reference")

    # Identificar los nuevos intentos sin reconocer aun cobros.
    # Esta rama permanece cerrada hasta incorporar el historial
    # individual PaymentAttemptCharge.
    if isinstance(external_reference, str) and ":" in external_reference:
        booking_id, attempt_key = _parse_mp_external_reference(
            external_reference
        )

        payment_for_attempt = (
            db.query(Payment)
            .filter(Payment.booking_id == booking_id)
            .populate_existing()
            .with_for_update(of=Payment)
            .one_or_none()
        )

        if payment_for_attempt is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No existe un pago principal para el intento notificado",
            )

        attempt = (
            db.query(PaymentAttempt)
            .filter(
                PaymentAttempt.attempt_key == attempt_key,
                PaymentAttempt.payment_id == payment_for_attempt.id,
            )
            .populate_existing()
            .with_for_update(of=PaymentAttempt)
            .one_or_none()
        )

        if attempt is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El intento notificado no pertenece al pago principal",
            )

        if (
            not attempt.mp_preference_id
            or attempt.amount != payment_for_attempt.amount
            or attempt.currency != "ARS"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Los datos del intento no coinciden con el pago principal",
            )

        # Verificar que la consulta de Mercado Pago corresponda
        # exactamente al identificador de cobro notificado.
        returned_id = mp_payment.get("id")
        if (
            returned_id is None
            or str(returned_id) != str(mp_payment_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Identificador del cobro notificado no coincide",
            )

        # Rechazar estados que el sistema no conoce.
        new_status = _map_mp_status(mp_payment.get("status"))

        # Un cobro aprobado debe coincidir en moneda e importe.
        if new_status == PaymentStatus.APPROVED:
            if mp_payment.get("currency_id") != "ARS":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Moneda del cobro distinta de ARS",
                )

            try:
                paid_amount = Decimal(
                    str(mp_payment.get("transaction_amount"))
                )
            except (ValueError, TypeError, ArithmeticError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Importe de Mercado Pago invalido",
                )

            if (
                not paid_amount.is_finite()
                or paid_amount <= 0
                or paid_amount != attempt.amount
                or paid_amount != payment_for_attempt.amount
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Importe aprobado distinto del esperado",
                )

        # Guardar cada cobro por su identidad individual.
        # Esta persistencia NO reconoce ingresos ni libera fondos.
        raw_amount = mp_payment.get("transaction_amount")
        charge_amount = None

        if raw_amount is not None:
            try:
                charge_amount = Decimal(str(raw_amount))
            except (ValueError, TypeError, ArithmeticError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Importe de transaccion invalido",
                )

            if (
                not charge_amount.is_finite()
                or charge_amount < 0
                or charge_amount > Decimal("99999999.99")
                or charge_amount.as_tuple().exponent < -2
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Importe de transaccion fuera de formato",
                )

        raw_currency = mp_payment.get("currency_id")
        if raw_currency is not None:
            if (
                not isinstance(raw_currency, str)
                or len(raw_currency) != 3
                or not raw_currency.isascii()
                or not raw_currency.isalpha()
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Moneda de transaccion invalida",
                )

        charge = (
            db.query(PaymentAttemptCharge)
            .filter(
                PaymentAttemptCharge.mp_payment_id
                == str(mp_payment_id)
            )
            .populate_existing()
            .with_for_update(of=PaymentAttemptCharge)
            .one_or_none()
        )

        if charge is not None and charge.attempt_id != attempt.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El cobro ya pertenece a otro intento",
            )

        if charge is None:
            charge = PaymentAttemptCharge(
                attempt_id=attempt.id,
                mp_payment_id=str(mp_payment_id),
                status=new_status.value,
                amount=charge_amount,
                currency=raw_currency,
            )
            db.add(charge)
        else:
            # Una notificacion antigua no debe deshacer una
            # aprobacion ni un estado financiero terminal.
            stale_approved = (
                charge.status == PaymentStatus.APPROVED.value
                and new_status not in (
                    PaymentStatus.APPROVED,
                    PaymentStatus.REFUNDED,
                    PaymentStatus.CHARGED_BACK,
                )
            )
            stale_terminal = (
                charge.status in (
                    PaymentStatus.REFUNDED.value,
                    PaymentStatus.CHARGED_BACK.value,
                )
                and charge.status != new_status.value
            )

            if not (stale_approved or stale_terminal) and (
                charge.status != new_status.value
                or charge.amount != charge_amount
                or charge.currency != raw_currency
            ):
                charge.status = new_status.value
                charge.amount = charge_amount
                charge.currency = raw_currency
                charge.updated_at = datetime.now(timezone.utc)

        # Detectar varios cobros aprobados para el mismo pago,
        # incluso cuando provienen de intentos diferentes.
        # El bloqueo del Payment padre serializa esta rama.
        db.flush()

        charge_status_rows = (
            db.query(PaymentAttemptCharge.status)
            .join(
                PaymentAttempt,
                PaymentAttempt.id == PaymentAttemptCharge.attempt_id,
            )
            .filter(
                PaymentAttempt.payment_id == payment_for_attempt.id,
            )
            .all()
        )

        decision = _classify_payment_charge_statuses(
            [row[0] for row in charge_status_rows]
        )

        # Un cobro aun aprobado puede tener devoluciones parciales.
        # No reconocerlo automaticamente si MP informa devoluciones
        # o metadatos financieros ambiguos.
        if (
            decision == "single_approved_candidate"
            and new_status == PaymentStatus.APPROVED
        ):
            refunded_raw = mp_payment.get("transaction_amount_refunded")
            refunds_raw = mp_payment.get("refunds")
            refund_review = False

            if refunds_raw is not None:
                if not isinstance(refunds_raw, list) or refunds_raw:
                    refund_review = True

            if refunded_raw is not None:
                try:
                    refunded_amount = Decimal(str(refunded_raw))
                    if (
                        not refunded_amount.is_finite()
                        or refunded_amount < 0
                        or refunded_amount.as_tuple().exponent < -2
                        or charge_amount is None
                        or refunded_amount > charge_amount
                        or refunded_amount > 0
                    ):
                        refund_review = True
                except (InvalidOperation, ValueError, TypeError):
                    refund_review = True

            if refund_review:
                decision = "manual_review"

        previous_attempt_alert = attempt.status in (
            "manual_review",
            "duplicate_approved_review",
        )

        if decision == "duplicate_approved_review":
            # Conservar la alerta hasta su resolucion controlada.
            attempt.status = "duplicate_approved_review"
        elif (
            decision == "manual_review"
            and attempt.status != "duplicate_approved_review"
        ):
            attempt.status = "manual_review"

        # Preparar el reconocimiento solo cuando se autorice
        # expresamente este camino tras las verificaciones.
        reconciled = False
        if (
            PAYMENT_RECONCILIATION_READY
            and decision == "single_approved_candidate"
        ):
            # Una alerta de CUALQUIER intento del mismo pago
            # bloquea el reconocimiento contable automatico.
            # La revision no se elimina por recibir otro webhook.
            outstanding_review = (
                db.query(PaymentAttempt.id)
                .filter(
                    PaymentAttempt.payment_id == payment_for_attempt.id,
                    PaymentAttempt.status.in_(
                        ("manual_review", "duplicate_approved_review")
                    ),
                )
                .first()
            )

            if outstanding_review is None:
                reconciled = _stage_reconciled_approval(
                    db,
                    payment_for_attempt,
                    attempt,
                    charge,
                    decision,
                )

        # Transiciones terminales conservadoras.
        # No operan mientras la conciliacion permanezca bloqueada.
        if (
            PAYMENT_RECONCILIATION_READY
            and not reconciled
            and new_status in (
                PaymentStatus.REFUNDED,
                PaymentStatus.CHARGED_BACK,
            )
            and not previous_attempt_alert
            and payment_for_attempt.status == PaymentStatus.APPROVED
            and payment_for_attempt.approved_at is not None
            and payment_for_attempt.released_at is None
            and payment_for_attempt.dispute_opened_at is None
            and payment_for_attempt.dispute_resolved_at is None
            and payment_for_attempt.mp_payment_id == str(mp_payment_id)
            and charge.mp_payment_id == str(mp_payment_id)
            and charge.attempt_id == attempt.id
            and charge.status == new_status.value
            and charge.currency == "ARS"
            and charge.amount is not None
            and charge.amount > 0
            and charge.amount == payment_for_attempt.amount
            and charge.amount == attempt.amount
            and len(charge_status_rows) == 1
        ):
            # No admitir otros intentos, aun sin cobros asociados.
            attempt_count = (
                db.query(PaymentAttempt.id)
                .filter(
                    PaymentAttempt.payment_id == payment_for_attempt.id
                )
                .count()
            )

            # Las alertas de otros intentos tampoco se resuelven.
            outstanding_alert = (
                db.query(PaymentAttempt.id)
                .filter(
                    PaymentAttempt.payment_id == payment_for_attempt.id,
                    PaymentAttempt.id != attempt.id,
                    PaymentAttempt.status.in_(
                        ("manual_review", "duplicate_approved_review")
                    ),
                )
                .first()
            )

            detail = mp_payment.get("status_detail")
            evidence_ok = False

            if new_status == PaymentStatus.REFUNDED:
                raw_refunded = mp_payment.get(
                    "transaction_amount_refunded"
                )
                if (
                    detail in ("refunded", "by_admin")
                    and raw_refunded is not None
                ):
                    try:
                        refunded = Decimal(str(raw_refunded))
                        evidence_ok = (
                            refunded.is_finite()
                            and refunded > 0
                            and refunded.as_tuple().exponent >= -2
                            and refunded == charge.amount
                        )
                    except (ValueError, TypeError, ArithmeticError):
                        evidence_ok = False

            elif new_status == PaymentStatus.CHARGED_BACK:
                # settled: retencion por contracargo.
                # reimbursed: fondos acreditados al vendedor.
                # No son equivalentes.
                evidence_ok = detail == "settled"

            if (
                attempt_count == 1
                and outstanding_alert is None
                and evidence_ok
            ):
                mp_id = str(mp_payment_id)
                prefix = (
                    "mp-terminal-refund:"
                    if new_status == PaymentStatus.REFUNDED
                    else "mp-terminal-chargeback:"
                )
                event_key = prefix + mp_id

                if len(event_key) <= 160:
                    previous_event = (
                        db.query(PaymentStatusEvent.id)
                        .filter(
                            PaymentStatusEvent.payment_id
                            == payment_for_attempt.id,
                            PaymentStatusEvent.event_key == event_key,
                        )
                        .first()
                    )

                    if previous_event is None:
                        old_status = payment_for_attempt.status

                        db.add(
                            PaymentStatusEvent(
                                payment_id=payment_for_attempt.id,
                                previous_status=old_status.value,
                                new_status=new_status.value,
                                event_source="mercadopago",
                                event_key=event_key,
                                mp_payment_id=mp_id,
                            )
                        )

                        payment_for_attempt.status = new_status
                        payment_for_attempt.mp_status_detail = detail
                        reconciled = True

        # Charge, Payment y PaymentStatusEvent participan de
        # una sola transaccion. El helper no hace commit.
        db.commit()

        if reconciled:
            db.refresh(payment_for_attempt)
            return payment_for_attempt

        # El webhook recibira HTTP 503 hasta implementar
        # reconocimiento y conciliacion seguros.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transaccion registrada; conciliacion pendiente",
        )

    # Bloqueo temporal del camino financiero anterior.
    # Requiere integracion con el historial de transacciones.
    if not LEGACY_PAYMENT_SYNC_READY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sincronizacion financiera anterior suspendida",
        )

    payment: Payment | None = None
    if external_reference is not None:
        try:
            booking_id = int(external_reference)
        except (TypeError, ValueError):
            booking_id = None
        if booking_id is not None:
            payment = db.query(Payment).filter(Payment.booking_id == booking_id).populate_existing().with_for_update(of=Payment).first()

    if payment is None:
        payment = (
            db.query(Payment)
            .filter(Payment.mp_payment_id == mp_payment_id)
            .populate_existing().with_for_update(of=Payment).first()
        )
    if payment is None:
        return None

    # El identificador consultado debe coincidir con el devuelto por MP.
    returned_id = mp_payment.get("id")
    if returned_id is None or str(returned_id) != str(mp_payment_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El identificador de Mercado Pago no coincide con el consultado",
        )

    # La referencia externa no puede apuntar a otra reserva.
    if external_reference is not None:
        try:
            reference_booking_id = int(external_reference)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Referencia externa de pago invalida",
            )
        if reference_booking_id != payment.booking_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El pago no corresponde a la reserva asociada",
            )

    # No sustituir un pago previamente vinculado a la reserva.
    if (
        payment.mp_payment_id is not None
        and str(payment.mp_payment_id) != str(mp_payment_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La reserva ya tiene otro pago de Mercado Pago asociado",
        )

    # No asociar el mismo pago financiero a dos reservas diferentes.
    associated_payment = (
        db.query(Payment)
        .filter(Payment.mp_payment_id == str(mp_payment_id))
        .first()
    )
    if associated_payment is not None and associated_payment.id != payment.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El pago de Mercado Pago ya pertenece a otra reserva",
        )

    # Verificacion de integridad financiera si viene con aprobacion
    raw_status = mp_payment.get("status")
    new_status = _map_mp_status(raw_status)

    if new_status == PaymentStatus.APPROVED:
        # 1. Validar moneda
        currency = mp_payment.get("currency_id")
        if currency != "ARS":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Moneda invalida recibida de MercadoPago: {currency}",
            )

        # 2. Validar que el monto cobrado coincida con el importe de la reserva
        paid_amount = Decimal(str(mp_payment.get("transaction_amount", 0)))
        if paid_amount != payment.amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Importe de Mercado Pago distinto del importe esperado",
            )

    # No revertir estados contables por notificaciones antiguas.
    # Un reembolso confirmado por Mercado Pago puede actualizar otros estados.
    if payment.status in FINAL_OR_PROTECTED_STATUSES:
        allowed_transition = (
            payment.status not in (PaymentStatus.REFUNDED, PaymentStatus.CHARGED_BACK)
            and (
                new_status in (PaymentStatus.REFUNDED, PaymentStatus.CHARGED_BACK)
                or (
                    payment.status == PaymentStatus.APPROVED
                    and new_status == PaymentStatus.APPROVED
                )
            )
        )
        if not allowed_transition:
            return payment

    previous_status = payment.status
    payment.mp_payment_id = str(mp_payment.get("id"))
    payment.mp_status_detail = mp_payment.get("status_detail")
    payment.status = new_status
    if previous_status != new_status:
        db.add(
            PaymentStatusEvent(
                payment_id=payment.id,
                previous_status=previous_status.value,
                new_status=new_status.value,
                event_source="mercadopago",
                event_key=None,
                mp_payment_id=str(mp_payment.get("id")),
            )
        )


    if new_status == PaymentStatus.APPROVED and payment.approved_at is None:
        payment.approved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(payment)
    return payment