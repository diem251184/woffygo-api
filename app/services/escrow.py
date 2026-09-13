"""Servicio de escrow bilateral para Woffy Go.

Reglas:
- Cuando un paseo se completa, el pago aprobado abre una ventana de
  confirmacion (24h). Si el duenio no hace nada, el pago se libera solo.
- El duenio puede CONFIRMAR (libera inmediato) o DISPUTAR (congela).
- El paseador NO puede liberar el pago: solo el sistema o el admin.
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.models.walk import Walk


ESCROW_WINDOW_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_payment_or_404(db: Session, payment_id: int) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado",
        )
    return payment


def _get_payment_by_walk_or_404(db: Session, walk_id: int) -> Payment:
    payment = db.query(Payment).filter(Payment.walk_id == walk_id).first()
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Este paseo no tiene pago registrado",
        )
    return payment


def start_escrow_window(db: Session, walk_id: int) -> Payment | None:
    """Abre la ventana de confirmacion al finalizar un paseo.

    Solo aplica si hay un Payment en estado APPROVED. Si no existe o esta
    en otro estado, no hace nada (devuelve None).
    """
    payment = db.query(Payment).filter(Payment.walk_id == walk_id).first()
    if payment is None:
        return None
    if payment.status != PaymentStatus.APPROVED:
        return None
    if payment.payment_release_deadline is not None:
        return payment
    payment.payment_release_deadline = _now() + timedelta(hours=ESCROW_WINDOW_HOURS)
    db.commit()
    db.refresh(payment)
    return payment


def confirm_delivery(
    db: Session,
    payment_id: int,
    current_user: User,
) -> Payment:
    """El duenio confirma que recibio la mascota OK. Libera el pago ya."""
    payment = _get_payment_or_404(db, payment_id)

    if payment.payer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el duenio que pago puede confirmar la entrega",
        )
    if payment.status == PaymentStatus.RELEASED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este pago ya fue liberado",
        )
    if payment.status == PaymentStatus.DISPUTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este pago esta en disputa. No se puede confirmar hasta resolverla",
        )
    if payment.status != PaymentStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se pueden confirmar pagos aprobados. Estado actual: {payment.status.value}",
        )

    payment.confirmed_by_owner_at = _now()
    payment.status = PaymentStatus.RELEASED
    payment.released_at = _now()
    db.commit()
    db.refresh(payment)
    return payment


def open_dispute(
    db: Session,
    payment_id: int,
    current_user: User,
    reason: str,
) -> Payment:
    """El duenio abre una disputa. Congela la liberacion automatica."""
    payment = _get_payment_or_404(db, payment_id)

    if payment.payer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el duenio que pago puede abrir una disputa",
        )
    if payment.status == PaymentStatus.DISPUTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya hay una disputa abierta para este pago",
        )
    if payment.status == PaymentStatus.RELEASED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El pago ya fue liberado. No se puede disputar",
        )
    if payment.status != PaymentStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se pueden disputar pagos aprobados. Estado actual: {payment.status.value}",
        )
    if payment.payment_release_deadline is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este pago aun no entro en la ventana de confirmacion",
        )

    payment.status = PaymentStatus.DISPUTED
    payment.dispute_opened_at = _now()
    payment.dispute_reason = reason
    db.commit()
    db.refresh(payment)
    return payment


def release_payment(db: Session, payment_id: int) -> Payment:
    """Libera el pago al paseador. Solo lo llama el worker o un admin."""
    payment = _get_payment_or_404(db, payment_id)

    if payment.status == PaymentStatus.RELEASED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este pago ya fue liberado",
        )
    if payment.status == PaymentStatus.DISPUTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede liberar un pago en disputa",
        )
    if payment.status != PaymentStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se pueden liberar pagos aprobados. Estado actual: {payment.status.value}",
        )

    payment.status = PaymentStatus.RELEASED
    payment.released_at = _now()
    db.commit()
    db.refresh(payment)
    return payment


def release_expired_payments(db: Session) -> list[int]:
    """Libera todos los pagos aprobados cuyo deadline ya venci.

    Devuelve la lista de IDs liberados. La llama el worker periodicamente.
    """
    now = _now()
    expired = (
        db.query(Payment)
        .filter(Payment.status == PaymentStatus.APPROVED)
        .filter(Payment.payment_release_deadline.is_not(None))
        .filter(Payment.payment_release_deadline <= now)
        .all()
    )
    released_ids: list[int] = []
    for payment in expired:
        payment.status = PaymentStatus.RELEASED
        payment.released_at = now
        released_ids.append(payment.id)
    if released_ids:
        db.commit()
    return released_ids


def resolve_dispute(
    db: Session,
    payment_id: int,
    admin_user: User,
    release_to_walker: bool,
    resolution_note: str | None = None,
) -> Payment:
    """Un admin resuelve una disputa.

    - release_to_walker=True -> libera el pago al paseador.
    - release_to_walker=False -> marca el pago como reembolsado al duenio.
    """
    if admin_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador puede resolver disputas",
        )
    payment = _get_payment_or_404(db, payment_id)
    if payment.status != PaymentStatus.DISPUTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El pago no esta en disputa. Estado: {payment.status.value}",
        )

    if release_to_walker:
        payment.status = PaymentStatus.RELEASED
        payment.released_at = _now()
    else:
        payment.status = PaymentStatus.REFUNDED

    if resolution_note:
        payment.mp_status_detail = resolution_note[:120]

    db.commit()
    db.refresh(payment)
    return payment