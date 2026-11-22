"""Criterio operativo KYC para prestadores de Woffy Go.

No altera verificaciones ni concede aprobaciones.
"""
from app.models.walker_verification import (
    WalkerVerificationStatus,
    DocumentStatus,
)


def is_kyc_operationally_approved(verification, service_type) -> bool:
    if verification is None:
        return False

    if verification.status != WalkerVerificationStatus.APPROVED:
        return False

    if verification.identity_status != DocumentStatus.APPROVED:
        return False

    if service_type == "walk":
        return True

    if service_type == "transport":
        return (
            verification.license_status == DocumentStatus.APPROVED
            and verification.vehicle_status == DocumentStatus.APPROVED
        )

    return False
