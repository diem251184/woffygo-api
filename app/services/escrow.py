from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.models.payment_status_event import PaymentStatusEvent
from app.models.payment_attempt import PaymentAttempt
from app.models.payment_attempt_charge import PaymentAttemptCharge
from app.models.user import User, UserRole

ESCROW_WINDOW_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_payment_or_404(db: Session, payment_id: int) -> Payment:
    payment = db.get(Payment, payment_id, with_for_update=True, populate_existing=True)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado",
        )
    return payment


def start_escrow_window(db: Session, booking_id: int) -> Payment | None:
    payment = db.query(Payment).filter(Payment.booking_id == booking_id).first()
    if payment is None or payment.status != PaymentStatus.APPROVED:
        return None
    if payment.payment_release_deadline is not None:
        return payment
    payment.payment_release_deadline = _now() + timedelta(hours=ESCROW_WINDOW_HOURS)
    db.commit()
    db.refresh(payment)
    return payment


def _record_internal_payment_transition(
    db: Session,
    payment: Payment,
    previous_status: PaymentStatus,
    event_source: str,
) -> None:
    if payment.status == previous_status:
        return
    db.add(
        PaymentStatusEvent(
            payment_id=payment.id,
            previous_status=previous_status.value,
            new_status=payment.status.value,
            event_source=event_source,
            event_key=None,
            mp_payment_id=payment.mp_payment_id,
        )
    )



def _assert_no_financial_alerts(db: Session, payment: Payment) -> None:
    """Impide liberaciones contables con alertas financieras pendientes."""
    unsafe = (
        db.query(PaymentAttempt.id)
        .outerjoin(
            PaymentAttemptCharge,
            PaymentAttemptCharge.attempt_id == PaymentAttempt.id,
        )
        .filter(
            PaymentAttempt.payment_id == payment.id,
            or_(
                PaymentAttempt.status.in_(
                    ("manual_review", "duplicate_approved_review")
                ),
                PaymentAttemptCharge.status.in_(
                    (
                        PaymentStatus.REFUNDED.value,
                        PaymentStatus.CHARGED_BACK.value,
                    )
                ),
            ),
        )
        .first()
    )

    if unsafe is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Liberacion bloqueada: existen reembolsos, "
                "contracargos o alertas financieras pendientes"
            ),
        )


def confirm_delivery(db: Session, payment_id: int, current_user: User) -> Payment:
    payment = _get_payment_or_404(db, payment_id)
    if payment.payer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el usuario que pagó puede confirmar la entrega",
        )
    if payment.status != PaymentStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se pueden confirmar pagos aprobados. Estado actual: {payment.status.value}",
        )

    # Validar que el servicio este completado
    if payment.dispute_opened_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede liberar un pago con una disputa registrada",
        )

    booking = db.get(Booking, payment.booking_id)
    if booking is None or booking.status != BookingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede confirmar la entrega de un servicio que no figura como completado",
        )

    payment.confirmed_by_owner_at = _now()
    _assert_no_financial_alerts(db, payment)
    payment.status = PaymentStatus.RELEASED
    _record_internal_payment_transition(db, payment, PaymentStatus.APPROVED, "escrow_owner_confirm")
    payment.released_at = _now()
    db.commit()
    db.refresh(payment)
    return payment


def open_dispute(db: Session, payment_id: int, current_user: User, reason: str) -> Payment:
    payment = _get_payment_or_404(db, payment_id)
    if payment.payer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el usuario que pagó puede abrir una disputa",
        )
    if payment.status != PaymentStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden disputar pagos aprobados",
        )

    payment.status = PaymentStatus.DISPUTED
    _record_internal_payment_transition(db, payment, PaymentStatus.APPROVED, "escrow_dispute_open")
    payment.dispute_opened_at = _now()
    payment.dispute_reason = reason
    db.commit()
    db.refresh(payment)
    return payment


def release_payment(db: Session, payment_id: int) -> Payment:
    payment = _get_payment_or_404(db, payment_id)
    if payment.status != PaymentStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden liberar pagos aprobados",
        )

    if payment.dispute_opened_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede liberar un pago con una disputa registrada",
        )

    booking = db.get(Booking, payment.booking_id)
    if booking is None or booking.status != BookingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El servicio debe estar completado para liberar los fondos contables",
        )

    _assert_no_financial_alerts(db, payment)
    payment.status = PaymentStatus.RELEASED
    _record_internal_payment_transition(db, payment, PaymentStatus.APPROVED, "escrow_manual_release")
    payment.released_at = _now()
    db.commit()
    db.refresh(payment)
    return payment


def release_expired_payments(db: Session) -> list[int]:
    """
    Liberación contable automática por vencimiento de plazo de custodia (24h).
    Requiere obligatoriamente que el servicio este COMPLETED y sin disputas abiertas.
    """
    now = _now()
    expired = (
        db.query(Payment)
        .join(Booking, Payment.booking_id == Booking.id)
        .filter(Payment.status == PaymentStatus.APPROVED)
        .filter(Payment.dispute_opened_at.is_(None))
        .filter(Booking.status == BookingStatus.COMPLETED)
        .filter(Payment.payment_release_deadline.is_not(None))
        .filter(Payment.payment_release_deadline <= now)
        .with_for_update(of=Payment, skip_locked=True)
        .all()
    )
    released_ids: list[int] = []
    for payment in expired:
        _assert_no_financial_alerts(db, payment)
        payment.status = PaymentStatus.RELEASED
        _record_internal_payment_transition(db, payment, PaymentStatus.APPROVED, "escrow_expiry_release")
        payment.released_at = now
        released_ids.append(payment.id)
    if released_ids:
        db.commit()
    return released_ids


def resolve_dispute(
    db: Session,
    payment_id: int,
    admin_user: User,
    release_to_provider: bool,
    resolution_note: str | None = None,
) -> Payment:
    if admin_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador puede resolver disputas",
        )
    payment = _get_payment_or_404(db, payment_id)
    if payment.status != PaymentStatus.DISPUTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El pago no está en disputa",
        )

    if release_to_provider:
        resolved_at = _now()
        _assert_no_financial_alerts(db, payment)
        payment.status = PaymentStatus.RELEASED
        _record_internal_payment_transition(db, payment, PaymentStatus.DISPUTED, "escrow_admin_resolution")
        payment.released_at = resolved_at
        payment.dispute_resolved_at = resolved_at
        payment.dispute_resolved_by_id = admin_user.id
        payment.dispute_resolution_result = "released_to_provider"
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No se puede marcar un pago como reembolsado "
                "sin confirmacion externa de Mercado Pago. "
                "La disputa permanece abierta."
            ),
        )

    if resolution_note:
        payment.dispute_resolution_note = resolution_note[:120]

    db.commit()
    db.refresh(payment)
    return payment