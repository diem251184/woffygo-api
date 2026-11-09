"""Preparacion persistente de reembolsos totales, sin envio externo."""
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentStatus
from app.models.payment_attempt import PaymentAttempt
from app.models.payment_attempt_charge import PaymentAttemptCharge
from app.models.payment_refund_request import PaymentRefundRequest
from app.models.admin_action import AdminAction
from app.models.payment_status_event import PaymentStatusEvent
from app.services.mercadopago import get_mp_payment
from app.models.user import User


def prepare_persisted_full_refund(
    db: Session,
    payment_id: int,
    admin: User,
) -> PaymentRefundRequest:
    """Registra o reutiliza una solicitud; nunca contacta Mercado Pago.

    El bloqueo del Payment serializa preparaciones de este mismo pago.
    Solo se admite un cobro aprobado e inequivoco.
    """
    if (
        admin is None
        or not isinstance(admin.id, int)
        or admin.id <= 0
        or not isinstance(admin.email, str)
        or not admin.email.strip()
    ):
        raise HTTPException(403, "Administrador no identificable")

    if not isinstance(payment_id, int) or payment_id <= 0:
        raise HTTPException(400, "Identificador de pago invalido")

    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id)
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    if payment is None:
        raise HTTPException(404, "Pago no encontrado")

    if (
        payment.status != PaymentStatus.APPROVED
        or payment.approved_at is None
        or payment.released_at is not None
        or payment.dispute_opened_at is not None
        or payment.dispute_resolved_at is not None
    ):
        raise HTTPException(409, "Pago no elegible para preparar reembolso")

    mp_id = payment.mp_payment_id
    if (
        not isinstance(mp_id, str)
        or not mp_id
        or not mp_id.isascii()
        or not mp_id.isdecimal()
        or int(mp_id) <= 0
    ):
        raise HTTPException(409, "Cobro Mercado Pago no identificable")

    attempts = (
        db.query(PaymentAttempt)
        .filter(PaymentAttempt.payment_id == payment.id)
        .all()
    )
    if len(attempts) != 1:
        raise HTTPException(409, "Intentos financieros ambiguos")

    attempt = attempts[0]
    if attempt.status in (
        "manual_review",
        "duplicate_approved_review",
    ):
        raise HTTPException(409, "Alerta financiera pendiente")

    if attempt.status != PaymentStatus.APPROVED.value:
        raise HTTPException(
            409, "Estado del intento de pago no aprobado"
        )

    if (
        attempt.mp_payment_id is not None
        and attempt.mp_payment_id != mp_id
    ):
        raise HTTPException(409, "Identidad del intento incompatible")

    charges = (
        db.query(PaymentAttemptCharge)
        .filter(PaymentAttemptCharge.attempt_id == attempt.id)
        .all()
    )
    if len(charges) != 1:
        raise HTTPException(409, "Cobros financieros ambiguos")

    charge = charges[0]

    if (
        charge.mp_payment_id != mp_id
        or charge.status != PaymentStatus.APPROVED.value
        or charge.currency != "ARS"
        or attempt.currency != "ARS"
    ):
        raise HTTPException(409, "Cobro original no verificable")

    try:
        amounts = [
            Decimal(str(payment.amount)),
            Decimal(str(attempt.amount)),
            Decimal(str(charge.amount)),
        ]
        valid_amounts = (
            all(a.is_finite() and a > 0 for a in amounts)
            and all(a.as_tuple().exponent >= -2 for a in amounts)
            and amounts[0] == amounts[1] == amounts[2]
        )
    except (ValueError, TypeError, ArithmeticError):
        valid_amounts = False

    if not valid_amounts:
        raise HTTPException(409, "Importes del cobro incompatibles")

    # Rechazar antecedentes incompatibles incluso si Payment
    # figura actualmente como APPROVED.
    historical_events = (
        db.query(PaymentStatusEvent)
        .filter(PaymentStatusEvent.payment_id == payment.id)
        .all()
    )

    incompatible_states = {
        "refunded",
        "partially_refunded",
        "charged_back",
        "chargeback",
        "reimbursed",
        "disputed",
        "refunding",
        "manual_review",
        "duplicate_approved_review",
    }

    for event in historical_events:
        previous_state = str(event.previous_status or "").strip().lower()
        new_state = str(event.new_status or "").strip().lower()

        if (
            previous_state in incompatible_states
            or new_state in incompatible_states
        ):
            raise HTTPException(
                409,
                "Antecedente financiero incompatible; revision manual",
            )

        if (
            event.mp_payment_id is not None
            and event.mp_payment_id != mp_id
        ):
            raise HTTPException(
                409,
                "Identificador historico de cobro incompatible",
            )

    previous = (
        db.query(PaymentRefundRequest)
        .filter(PaymentRefundRequest.payment_id == payment.id)
        .with_for_update()
        .all()
    )

    if previous:
        if (
            len(previous) == 1
            and previous[0].mp_payment_id == mp_id
            and previous[0].status == "prepared"
        ):
            return previous[0]
        raise HTTPException(
            409, "Solicitud previa no reutilizable; revision manual"
        )

    request = PaymentRefundRequest(
        payment_id=payment.id,
        mp_payment_id=mp_id,
        idempotency_key=str(uuid4()),
        status="prepared",
    )
    try:
        db.add(request)
        db.flush()

        audit = AdminAction(
            admin_id=admin.id,
            admin_email=admin.email,
            action="payment_refund_prepared",
            target_type="payment",
            target_id=payment.id,
            description=(
                f"Solicitud de reembolso total #{request.id} "
                f"preparada para pago #{payment.id}; "
                "sin envio a Mercado Pago"
            ),
        )
        db.add(audit)
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(request)
    return request

def reserve_refund_dispatch(
    db: Session,
    request_id: int,
    admin: User,
) -> PaymentRefundRequest:
    """Reserva un unico intento de envio; NO contacta Mercado Pago.

    dispatch_reserved significa que el envio puede ocurrir o haber
    ocurrido. Nunca habilita un reintento automatico.
    """
    if not isinstance(request_id, int) or isinstance(request_id, bool) or request_id <= 0:
        raise HTTPException(400, "Solicitud de reembolso invalida")

    if (
        admin is None
        or not isinstance(admin.id, int)
        or isinstance(admin.id, bool)
        or admin.id <= 0
        or not isinstance(admin.email, str)
        or not admin.email.strip()
    ):
        raise HTTPException(403, "Administrador no identificable")

    request = (
        db.query(PaymentRefundRequest)
        .filter(PaymentRefundRequest.id == request_id)
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )

    if request is None:
        raise HTTPException(404, "Solicitud no encontrada")

    if (
        request.status != "prepared"
        or request.submitted_at is not None
        or request.resolved_at is not None
        or request.mp_refund_id is not None
        or request.response_http_status is not None
        or request.response_status is not None
    ):
        raise HTTPException(
            409,
            "Envio ya reservado o solicitud no elegible; conciliar manualmente",
        )

    # No establecer submitted_at: aun NO se envio nada.
    request.status = "dispatch_reserved"

    audit = AdminAction(
        admin_id=admin.id,
        admin_email=admin.email,
        action="payment_refund_dispatch_reserved",
        target_type="payment",
        target_id=request.payment_id,
        description=(
            f"Reserva de envio para solicitud de reembolso #{request.id}; "
            "envio externo no confirmado"
        ),
    )

    try:
        db.add(audit)
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(request)
    return request

def record_uncertain_refund_dispatch(
    db: Session,
    request_id: int,
    admin: User,
    evidence_reference: str,
    reason: str,
) -> PaymentRefundRequest:
    """Registra resultado incierto; no realiza ni reintenta reembolsos."""
    if (
        not isinstance(request_id, int)
        or isinstance(request_id, bool)
        or request_id <= 0
    ):
        raise HTTPException(400, "Identificador de solicitud invalido")

    if (
        admin is None
        or not isinstance(admin.id, int)
        or isinstance(admin.id, bool)
        or admin.id <= 0
        or not isinstance(admin.email, str)
        or not admin.email.strip()
    ):
        raise HTTPException(403, "Administrador no identificable")

    def validate_note(value, minimum, maximum, label):
        if (
            not isinstance(value, str)
            or not minimum <= len(value.strip()) <= maximum
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
        ):
            raise HTTPException(400, label)
        return value.strip()

    reference = validate_note(
        evidence_reference, 6, 120,
        "Referencia de evidencia invalida",
    )
    explanation = validate_note(
        reason, 12, 180,
        "Justificacion insuficiente",
    )

    request = (
        db.query(PaymentRefundRequest)
        .filter(PaymentRefundRequest.id == request_id)
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )

    if request is None:
        raise HTTPException(404, "Solicitud no encontrada")

    if (
        request.status != "dispatch_reserved"
        or request.submitted_at is not None
        or request.resolved_at is not None
        or request.mp_refund_id is not None
        or request.response_http_status is not None
        or request.response_status is not None
    ):
        raise HTTPException(
            409,
            "Solicitud no elegible; no repetir ni inferir un reembolso",
        )

    # Este estado NO acredita envio ni reembolso.
    # Una conciliacion externa sera obligatoria.
    request.status = "dispatch_uncertain"

    audit = AdminAction(
        admin_id=admin.id,
        admin_email=admin.email,
        action="refund_dispatch_uncertain",
        target_type="payment",
        target_id=request.payment_id,
        description=(
            f"Solicitud #{request.id}: resultado de envio incierto. "
            f"Evidencia: {reference}. Motivo: {explanation}"
        )[:500],
    )

    try:
        db.add(audit)
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(request)
    return request

def assess_full_refund_reconciliation_candidate(
    request: PaymentRefundRequest,
    payment: Payment,
    mp_payment: dict,
) -> dict:
    """Evalua evidencia candidata; NUNCA confirma una devolucion.

    El llamador debera verificar independientemente la procedencia
    del dato externo antes de cualquier transicion financiera.
    No modifica objetos, no consulta la red y no escribe en la DB.
    """
    def reject(reason: str) -> dict:
        return {
            "classification": "insufficient_evidence",
            "reason": reason,
            "refund_confirmed": False,
        }

    if request is None or payment is None:
        return reject("missing_local_record")

    if getattr(request, "status", None) not in (
        "dispatch_reserved",
        "dispatch_uncertain",
        "manual_review_required",
    ):
        return reject("request_state_not_reconcilable")

    if not isinstance(mp_payment, dict):
        return reject("invalid_external_payload")

    local_mp_id = getattr(request, "mp_payment_id", None)
    payment_mp_id = getattr(payment, "mp_payment_id", None)
    external_mp_id = mp_payment.get("id")

    if (
        not isinstance(local_mp_id, str)
        or not local_mp_id.isascii()
        or not local_mp_id.isdecimal()
        or int(local_mp_id) <= 0
        or payment_mp_id != local_mp_id
        or str(external_mp_id) != local_mp_id
        or getattr(request, "payment_id", None) !=
            getattr(payment, "id", None)
    ):
        return reject("payment_identity_mismatch")

    if (
        mp_payment.get("status") != "refunded"
        or mp_payment.get("status_detail")
            not in ("refunded", "by_admin")
    ):
        return reject("non_terminal_refund_status")

    if mp_payment.get("currency_id") != "ARS":
        return reject("currency_mismatch")

    try:
        values = [
            Decimal(str(getattr(payment, "amount", None))),
            Decimal(str(mp_payment.get("transaction_amount"))),
            Decimal(str(
                mp_payment.get("transaction_amount_refunded")
            )),
        ]

        valid = (
            all(
                value.is_finite()
                and value > 0
                and value.as_tuple().exponent >= -2
                for value in values
            )
            and values[0] == values[1] == values[2]
        )
    except (ValueError, TypeError, ArithmeticError):
        valid = False

    if not valid:
        return reject("full_amount_not_proven")

    refunds = mp_payment.get("refunds")
    if refunds is not None and not isinstance(refunds, list):
        return reject("invalid_refund_details")

    return {
        "classification": "candidate_for_manual_verification",
        "reason": "matching_terminal_full_refund_fields",
        "refund_confirmed": False,
    }

def inspect_refund_with_authenticated_mp_lookup(
    db: Session,
    request_id: int,
) -> dict:
    """Consulta el cobro mediante el SDK; no confirma ni persiste reembolsos.

    Una respuesta coincidente es solamente candidata a revision.
    Nunca modifica Payment ni PaymentRefundRequest.
    """
    if (
        not isinstance(request_id, int)
        or isinstance(request_id, bool)
        or request_id <= 0
    ):
        raise HTTPException(400, "Identificador de solicitud invalido")

    request = (
        db.query(PaymentRefundRequest)
        .filter(PaymentRefundRequest.id == request_id)
        .one_or_none()
    )
    if request is None:
        raise HTTPException(404, "Solicitud de reembolso inexistente")

    if request.status not in (
        "dispatch_reserved",
        "dispatch_uncertain",
        "manual_review_required",
    ):
        raise HTTPException(
            409, "La solicitud no admite conciliacion externa"
        )

    payment = (
        db.query(Payment)
        .filter(Payment.id == request.payment_id)
        .one_or_none()
    )
    if payment is None:
        raise HTTPException(409, "Pago principal inexistente")

    mp_id = request.mp_payment_id
    if (
        not isinstance(mp_id, str)
        or not mp_id.isascii()
        or not mp_id.isdecimal()
        or int(mp_id) <= 0
        or payment.mp_payment_id != mp_id
        or payment.id != request.payment_id
    ):
        raise HTTPException(409, "Identidad del cobro incompatible")

    # No usar sync_payment_from_mp: esa funcion puede escribir en DB.
    try:
        external_payment = get_mp_payment(mp_id)
    except HTTPException as exc:
        if exc.status_code not in (502, 503, 504):
            raise

        # Fallo de consulta != reembolso rechazado.
        # No divulgar mensajes internos del SDK ni modificar la DB.
        return {
            "request_id": request.id,
            "classification": "lookup_unavailable",
            "reason": "provider_lookup_failed",
            "refund_confirmed": False,
            "requires_manual_verification": True,
        }

    if not isinstance(external_payment, dict):
        raise HTTPException(
            502, "Respuesta de consulta externa invalida"
        )

    result = assess_full_refund_reconciliation_candidate(
        request, payment, external_payment
    )

    # Defensa adicional: esta consulta nunca confirma devoluciones.
    return {
        "request_id": request.id,
        "classification": result["classification"],
        "reason": result["reason"],
        "refund_confirmed": False,
        "requires_manual_verification": True,
    }

def require_manual_refund_reconciliation_review(
    db: Session,
    request_id: int,
    admin: User,
    reason: str,
) -> PaymentRefundRequest:
    """Deriva una solicitud a revision; NO acredita reembolso ni envio."""
    if (
        not isinstance(request_id, int)
        or isinstance(request_id, bool)
        or request_id <= 0
    ):
        raise HTTPException(400, "Solicitud invalida")

    if (
        admin is None
        or not isinstance(admin.id, int)
        or isinstance(admin.id, bool)
        or admin.id <= 0
        or not isinstance(admin.email, str)
        or not admin.email.strip()
    ):
        raise HTTPException(403, "Administrador no identificable")

    if (
        not isinstance(reason, str)
        or not 12 <= len(reason.strip()) <= 180
        or any(ord(c) < 32 or ord(c) == 127 for c in reason)
    ):
        raise HTTPException(400, "Justificacion de revision invalida")

    request = (
        db.query(PaymentRefundRequest)
        .filter(PaymentRefundRequest.id == request_id)
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )

    if request is None:
        raise HTTPException(404, "Solicitud inexistente")

    if (
        request.status not in (
            "dispatch_reserved",
            "dispatch_uncertain",
        )
        or request.submitted_at is not None
        or request.resolved_at is not None
        or request.mp_refund_id is not None
        or request.response_http_status is not None
        or request.response_status is not None
    ):
        raise HTTPException(
            409, "Solicitud ya derivada o no elegible",
        )

    # Verificar el pago bajo bloqueo en la misma transaccion.
    # No cambiar el estado del pago ni inferir un reembolso.
    payment = (
        db.query(Payment)
        .filter(Payment.id == request.payment_id)
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    if (
        payment is None
        or payment.status != PaymentStatus.APPROVED
        or payment.released_at is not None
        or payment.dispute_opened_at is not None
        or payment.dispute_resolved_at is not None
        or payment.mp_payment_id != request.mp_payment_id
        or payment.id != request.payment_id
    ):
        raise HTTPException(
            409, "Pago incompatible; revisar sin alterar la solicitud",
        )

    # La revision manual NO acredita un reembolso.
    # No habilitar un nuevo despacho ni modificar Payment.status.
    request.status = "manual_review_required"

    audit = AdminAction(
        admin_id=admin.id,
        admin_email=admin.email.strip(),
        action="refund_manual_review_required",
        target_type="payment",
        target_id=request.payment_id,
        description=(
            f"Solicitud #{request.id}: revision manual obligatoria. "
            f"Motivo: {reason.strip()}. "
            "Envio y devolucion externa no confirmados."
        )[:500],
    )

    try:
        db.add(audit)
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(request)
    return request
