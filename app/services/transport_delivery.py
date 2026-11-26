import hashlib
import hmac
import re
import secrets

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from app.core.config import settings
from sqlalchemy.orm import Session

from app.models.booking import (
    Booking,
    BookingStatus,
    ServiceType,
)

from app.models.transport_delivery_credential import (
    TransportDeliveryCredential,
)


DELIVERY_PIN_LENGTH = 6
DELIVERY_MAX_ATTEMPTS = 5
DELIVERY_LOCK_MINUTES = 15
DELIVERY_KEY_VERSION = 1

PIN_PATTERN = re.compile(r"[0-9]{6}", re.ASCII)
HEX_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


def _now():
    return datetime.now(timezone.utc)


def _delivery_key(version: int) -> bytes:
    if version != DELIVERY_KEY_VERSION:
        raise HTTPException(
            status_code=503,
            detail="Credencial de entrega no disponible",
        )

    configured = (
        settings.WOFFY_TRANSPORT_DELIVERY_KEY_V1
    )

    raw = (
        configured.get_secret_value()
        if configured is not None
        else ""
    )

    if not HEX_PATTERN.fullmatch(raw):
        raise HTTPException(
            status_code=503,
            detail="Seguridad de entrega no disponible",
        )

    key = bytes.fromhex(raw)

    if len(key) != 32 or len(set(key)) < 2:
        raise HTTPException(
            status_code=503,
            detail="Seguridad de entrega no disponible",
        )

    return key


def _validate_booking(booking: Booking):
    if (
        booking.service_type != ServiceType.TRANSPORT
        or booking.status != BookingStatus.IN_PROGRESS
        or booking.provider_id is None
        or booking.started_at is None
    ):
        raise HTTPException(
            status_code=409,
            detail="Entrega no disponible para esta reserva",
        )


def _credential_context(
    booking: Booking,
    nonce: str,
    version: int,
) -> bytes:
    if not HEX_PATTERN.fullmatch(nonce):
        raise HTTPException(
            status_code=503,
            detail="Credencial de entrega no disponible",
        )

    return (
        f"woffygo:transport-delivery:v{version}:"
        f"{booking.id}:{booking.owner_id}:"
        f"{booking.provider_id}:{nonce}"
    ).encode("ascii")


def _derive_pin(
    key: bytes,
    context: bytes,
) -> str:
    # Rejection sampling avoids modulo bias.
    space = 10 ** DELIVERY_PIN_LENGTH
    maximum = 1 << 256
    cutoff = maximum - maximum % space

    for counter in range(128):
        digest = hmac.new(
            key,
            b"PIN:" + context + b":" +
            counter.to_bytes(4, "big"),
            hashlib.sha256,
        ).digest()

        number = int.from_bytes(digest, "big")

        if number < cutoff:
            return str(number % space).zfill(
                DELIVERY_PIN_LENGTH
            )

    raise HTTPException(
        status_code=503,
        detail="No se pudo preparar la entrega",
    )


def _pin_verifier(
    key: bytes,
    context: bytes,
    pin: str,
) -> str:
    return hmac.new(
        key,
        b"VERIFY:" + context + b":" +
        pin.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def _credential_locked(
    db: Session,
    booking_id: int,
):
    return (
        db.query(TransportDeliveryCredential)
        .filter(
            TransportDeliveryCredential.booking_id
            == booking_id
        )
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )


def _ensure_unused(credential):
    if (
        credential.used_at is not None
        or credential.invalidated_at is not None
    ):
        raise HTTPException(
            status_code=409,
            detail="Credencial de entrega no disponible",
        )


def get_or_create_owner_delivery_pin(
    db: Session,
    booking: Booking,
    owner_id: int,
) -> str:
    """
    Private owner-only PIN retrieval.

    Caller must authenticate OWNER, lock the booking
    row and commit successfully before returning PIN.
    Never include this PIN in generic booking responses.
    """

    if booking.owner_id != owner_id:
        raise HTTPException(
            status_code=404,
            detail="Reserva no encontrada",
        )

    _validate_booking(booking)

    credential = _credential_locked(
        db, booking.id
    )

    if credential is None:
        version = DELIVERY_KEY_VERSION
        key = _delivery_key(version)

        nonce = secrets.token_hex(32)

        context = _credential_context(
            booking, nonce, version
        )

        pin = _derive_pin(key, context)

        credential = TransportDeliveryCredential(
            booking_id=booking.id,
            pin_verifier=_pin_verifier(
                key, context, pin
            ),
            generation_nonce=nonce,
            key_version=version,
            failed_attempts=0,
        )

        db.add(credential)
        db.flush()

        return pin

    _ensure_unused(credential)

    key = _delivery_key(
        credential.key_version
    )

    context = _credential_context(
        booking,
        credential.generation_nonce,
        credential.key_version,
    )

    pin = _derive_pin(
        key, context
    )

    expected = _pin_verifier(
        key, context, pin
    )

    if not hmac.compare_digest(
        credential.pin_verifier,
        expected,
    ):
        raise HTTPException(
            status_code=503,
            detail="Credencial de entrega no disponible",
        )

    return pin


def verify_delivery_pin(
    db: Session,
    booking: Booking,
    provider_id: int,
    submitted_pin: str,
):
    """
    Caller must hold booking row lock.

    Caller must first validate GPS arrival.

    Failed attempts MUST be committed before sending
    an error response. A successful result MUST be
    consumed atomically with booking completion.

    Returns credential on success, None on wrong PIN.
    Does not commit or complete the booking.
    """

    if booking.provider_id != provider_id:
        raise HTTPException(
            status_code=403,
            detail="No asignado a esta reserva",
        )

    _validate_booking(booking)

    credential = _credential_locked(
        db, booking.id
    )

    if credential is None:
        raise HTTPException(
            status_code=409,
            detail="El propietario debe preparar el PIN",
        )

    _ensure_unused(credential)

    now = _now()

    if credential.locked_until is not None:
        if credential.locked_until > now:
            raise HTTPException(
                status_code=429,
                detail="Validacion de entrega temporalmente bloqueada",
            )

        credential.locked_until = None
        credential.failed_attempts = 0

    key = _delivery_key(
        credential.key_version
    )

    context = _credential_context(
        booking,
        credential.generation_nonce,
        credential.key_version,
    )

    valid = False

    if (
        isinstance(submitted_pin, str)
        and PIN_PATTERN.fullmatch(submitted_pin)
    ):
        candidate = _pin_verifier(
            key,
            context,
            submitted_pin,
        )

        valid = hmac.compare_digest(
            credential.pin_verifier,
            candidate,
        )

    if not valid:
        credential.failed_attempts += 1

        if (
            credential.failed_attempts
            >= DELIVERY_MAX_ATTEMPTS
        ):
            credential.locked_until = (
                now + timedelta(
                    minutes=DELIVERY_LOCK_MINUTES
                )
            )

        db.flush()

        return None

    return credential


def consume_delivery_pin(
    db: Session,
    credential: TransportDeliveryCredential,
):
    """
    Must be called only after successful PIN and GPS
    validation, in the booking completion transaction.
    """

    _ensure_unused(credential)

    credential.used_at = _now()

    db.flush()


def invalidate_delivery_pin(
    db: Session,
    booking_id: int,
):
    """
    Caller must hold booking row lock.
    Cancellation and invalidation must commit together.
    """

    credential = _credential_locked(
        db, booking_id
    )

    if credential is None:
        return

    if (
        credential.used_at is None
        and credential.invalidated_at is None
    ):
        credential.invalidated_at = _now()
        db.flush()
