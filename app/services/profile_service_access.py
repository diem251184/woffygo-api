"""Service access rules during administrative profile review.

This module does not alter accounts, KYC, bookings, payments or
authentication. Callers must explicitly invoke the guard before
creating new service obligations.

Existing bookings require separate handling to preserve animal
safety and avoid automatic cancellations or payment changes.
"""

from fastapi import HTTPException, status

from app.models.user import User, UserRole


def ensure_profile_services_enabled(user: User) -> None:
    """Reject new service operations while profile review is unresolved.

    This is an additional requirement, not a replacement for:
    role checks, KYC approval, provider availability, pet compatibility,
    booking status transitions, or financial security controls.
    """

    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta operación no corresponde a una cuenta administrativa",
        )

    if user.role not in (UserRole.OWNER, UserRole.WALKER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rol de usuario no autorizado para este servicio",
        )

    review_status = user.profile_review_status

    if review_status == "clear":
        return

    if review_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Tu cuenta está en revisión administrativa. "
                "No podés iniciar nuevos servicios hasta que "
                "se aprueben tus datos personales."
            ),
        )

    if review_status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "La revisión de tus datos personales fue rechazada. "
                "Debés regularizar la información y recibir "
                "una nueva aprobación administrativa."
            ),
        )

    # Fail closed on unknown or inconsistent states.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="El estado de revisión de tu cuenta requiere intervención administrativa",
    )