"""Recuperacion acotada de cargos pendientes mediante el circuito MP definitivo.

No programa tareas, no crea preferencias y no habilita conciliacion.
La ejecucion requiere autorizacion financiera en el servicio existente.
"""

import logging
import os

from fastapi import HTTPException

from app.core.database import SessionLocal
from app.models.payment import Payment
from app.models.payment_attempt import PaymentAttempt
from app.models.payment_attempt_charge import PaymentAttemptCharge
from app.services import mercadopago as mp


logger = logging.getLogger(__name__)


def recover_pending_approved_charges(batch_size: int = 50) -> dict:
    """Reconsulta cargos aprobados cuyo Payment sigue pendiente.

    Reutiliza la sincronizacion existente. Cada cargo se procesa
    en una sesion independiente. Nunca libera ni liquida fondos.
    """

    if not isinstance(batch_size, int) or isinstance(batch_size, bool):
        raise ValueError("batch_size debe ser entero")

    if not 1 <= batch_size <= 100:
        raise ValueError("batch_size fuera del rango permitido")

    # Fail closed: ninguna lectura ni operacion financiera si
    # el circuito de conciliacion todavia no fue autorizado.
    if (
        os.getenv("WOFFY_MP_RECOVERY_ENABLED") != "1"
        or not mp.PAYMENT_RECONCILIATION_READY
    ):
        return {
            "enabled": False,
            "selected": 0,
            "processed": 0,
            "deferred": 0,
            "failed": 0,
        }

    # Solo cargos existentes, vinculados a intentos reales.
    # La consulta no cambia estados ni obtiene credenciales.
    with SessionLocal() as db:
        charge_ids = [
            row[0]
            for row in (
                db.query(PaymentAttemptCharge.id)
                .join(
                    PaymentAttempt,
                    PaymentAttempt.id == PaymentAttemptCharge.attempt_id,
                )
                .join(
                    Payment,
                    Payment.id == PaymentAttempt.payment_id,
                )
                .filter(
                    Payment.status == mp.PaymentStatus.PENDING,
                    PaymentAttemptCharge.status
                    == mp.PaymentStatus.APPROVED.value,
                    PaymentAttempt.mp_preference_id.isnot(None),
                )
                .order_by(PaymentAttemptCharge.id.asc())
                .limit(batch_size)
                .all()
            )
        ]

    processed = 0
    deferred = 0
    failed = 0

    for charge_id in charge_ids:
        # La misma funcion de sincronizacion aplica sus controles
        # de identidad, importes, bloqueos y transiciones.
        with SessionLocal() as db:
            try:
                charge = db.get(PaymentAttemptCharge, charge_id)
                if charge is None:
                    continue

                mp.sync_payment_from_mp(db, charge.mp_payment_id)
                processed += 1

            except HTTPException as exc:
                db.rollback()
                if (
                    exc.status_code == 503
                    and exc.detail
                    == "Transaccion registrada; conciliacion pendiente"
                ):
                    deferred += 1
                    continue
                failed += 1
                logger.warning(
                    "Error de sincronizacion financiera: charge_id=%s",
                    charge_id,
                )

            except Exception:
                db.rollback()
                failed += 1
                logger.warning(
                    "Recuperacion financiera pendiente: charge_id=%s",
                    charge_id,
                )

    result = {
        "enabled": True,
        "selected": len(charge_ids),
        "processed": processed,
        "deferred": deferred,
        "failed": failed,
    }

    if failed:
        raise RuntimeError(
            "Recuperacion financiera incompleta; revisar registros seguros"
        )

    return result


def main() -> int:
    """Punto de entrada para un futuro ejecutor controlado."""
    result = recover_pending_approved_charges()

    if not result["enabled"]:
        logger.warning("Recuperacion financiera deshabilitada")
        return 2

    logger.info(
        "Recuperacion: seleccionados=%d procesados=%d pendientes=%d fallidos=%d",
        result["selected"],
        result["processed"],
        result["deferred"],
        result["failed"],
    )
    if result["deferred"] > 0:
        logger.warning(
            "Recuperacion incompleta: %d cargos pendientes de conciliacion",
            result["deferred"],
        )
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())