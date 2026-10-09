from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, UserRole
from app.models.walker_verification import (
    WalkerVerification,
    WalkerVerificationStatus,
)
from app.schemas.walker_verification import (
    RejectRequest,
    WalkerVerificationOut,
    WalkerVerificationStatusOut,
)
from app.services import admin_log, cloudinary_service, email, push


router = APIRouter(prefix="/walker-verifications", tags=["walker-verifications"])


@router.post(
    "/upload",
    response_model=WalkerVerificationOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_verification(
    dni_front: UploadFile = File(...),
    dni_back: UploadFile = File(...),
    selfie: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(WalkerVerification)
        .filter(WalkerVerification.user_id == current_user.id)
        .first()
    )
    if existing and existing.status == WalkerVerificationStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail="Ya tenes la verificacion aprobada",
        )

    try:
        front_bytes = await dni_front.read()
        back_bytes = await dni_back.read()
        selfie_bytes = await selfie.read()

        front_url = cloudinary_service.upload_kyc_image(
            front_bytes, dni_front.content_type, current_user.id, "dni_front"
        )
        back_url = cloudinary_service.upload_kyc_image(
            back_bytes, dni_back.content_type, current_user.id, "dni_back"
        )
        selfie_url = cloudinary_service.upload_kyc_image(
            selfie_bytes, selfie.content_type, current_user.id, "selfie"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if existing:
        existing.dni_front_url = front_url
        existing.dni_back_url = back_url
        existing.selfie_url = selfie_url
        existing.status = WalkerVerificationStatus.PENDING
        existing.rejection_reason = None
        existing.reviewed_by_admin_id = None
        existing.reviewed_at = None
        verification = existing
    else:
        verification = WalkerVerification(
            user_id=current_user.id,
            dni_front_url=front_url,
            dni_back_url=back_url,
            selfie_url=selfie_url,
            status=WalkerVerificationStatus.PENDING,
        )
        db.add(verification)

    db.commit()
    db.refresh(verification)

    # Notificar a los administradores vía Push Notification
    try:
        push.send_to_admins(
            db=db,
            title="Nueva verificación pendiente 📋",
            body=f"{current_user.full_name} envió sus documentos de identidad.",
            data={"type": "kyc_pending", "verification_id": verification.id},
        )
    except Exception as e:
        print(f"[kyc] Error enviando push a admins: {e}")

    out = WalkerVerificationOut.model_validate(verification)
    out.user_full_name = current_user.full_name
    out.user_email = current_user.email
    out.user_phone = current_user.phone
    return out


@router.get("/me", response_model=WalkerVerificationStatusOut)
def get_my_verification(
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    v = (
        db.query(WalkerVerification)
        .filter(WalkerVerification.user_id == current_user.id)
        .first()
    )
    if not v:
        return WalkerVerificationStatusOut(
            has_verification=False, status=None, rejection_reason=None
        )
    return WalkerVerificationStatusOut(
        has_verification=True,
        status=v.status.value,
        rejection_reason=v.rejection_reason,
    )


@router.get("/admin/pending", response_model=list[WalkerVerificationOut])
def list_pending(
    status_filter: str | None = Query(default="pending"),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    query = db.query(WalkerVerification, User).join(User, WalkerVerification.user_id == User.id)

    if status_filter == "pending":
        query = query.filter(WalkerVerification.status == WalkerVerificationStatus.PENDING)
    elif status_filter == "approved":
        query = query.filter(WalkerVerification.status == WalkerVerificationStatus.APPROVED)
    elif status_filter == "rejected":
        query = query.filter(WalkerVerification.status == WalkerVerificationStatus.REJECTED)

    results = query.order_by(WalkerVerification.updated_at.desc()).all()

    items = []
    for verif, u in results:
        out = WalkerVerificationOut.model_validate(verif)
        out.user_full_name = u.full_name
        out.user_email = u.email
        out.user_phone = u.phone
        items.append(out)

    return items


@router.post(
    "/admin/{verification_id}/approve",
    response_model=WalkerVerificationOut,
)
def approve_verification(
    verification_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    v = db.get(WalkerVerification, verification_id)
    if not v:
        raise HTTPException(status_code=404, detail="Verificacion no encontrada")
    if v.status == WalkerVerificationStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Ya estaba aprobada")

    v.status = WalkerVerificationStatus.APPROVED
    v.rejection_reason = None
    v.reviewed_by_admin_id = current_user.id
    v.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(v)

    target_user = db.get(User, v.user_id)

    # Registrar acción en Audit Log
    try:
        user_info = target_user.full_name if target_user else f"ID {v.user_id}"
        admin_log.log_action(
            db=db,
            admin=current_user,
            action="KYC_APPROVE",
            target_type="WALKER_VERIFICATION",
            target_id=v.id,
            description=f"Aprobó la verificación de identidad del paseador {user_info}",
        )
    except Exception as e:
        print(f"[kyc] Error registrando audit log: {e}")

    if target_user:
        # Push al Paseador
        try:
            push.send_to_user(
                db=db,
                user_id=target_user.id,
                title="Verificación Aprobada 🎉",
                body="¡Tu identidad fue verificada! Ya podés recibir solicitudes y aceptar paseos.",
                data={"type": "kyc_approved"},
            )
        except Exception as e:
            print(f"[kyc] Error enviando push: {e}")

        # Email por Resend
        try:
            email.send_email(
                to_email=target_user.email,
                subject="Woofy Go - ¡Tu cuenta fue verificada!",
                body=(
                    f"Hola {target_user.full_name},\n\n"
                    "¡Buenas noticias! Tu documentación fue revisada y aprobada por nuestro equipo.\n\n"
                    "A partir de este momento tenés acceso completo para ponerte online y aceptar paseos.\n\n"
                    "El equipo de Woofy Go 🐾"
                ),
            )
        except Exception as e:
            print(f"[kyc] Error enviando email: {e}")

    out = WalkerVerificationOut.model_validate(v)
    if target_user:
        out.user_full_name = target_user.full_name
        out.user_email = target_user.email
        out.user_phone = target_user.phone
    return out


@router.post(
    "/admin/{verification_id}/reject",
    response_model=WalkerVerificationOut,
)
def reject_verification(
    verification_id: int,
    body: RejectRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    v = db.get(WalkerVerification, verification_id)
    if not v:
        raise HTTPException(status_code=404, detail="Verificacion no encontrada")

    v.status = WalkerVerificationStatus.REJECTED
    v.rejection_reason = body.reason
    v.reviewed_by_admin_id = current_user.id
    v.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(v)

    target_user = db.get(User, v.user_id)

    # Registrar acción en Audit Log
    try:
        user_info = target_user.full_name if target_user else f"ID {v.user_id}"
        admin_log.log_action(
            db=db,
            admin=current_user,
            action="KYC_REJECT",
            target_type="WALKER_VERIFICATION",
            target_id=v.id,
            description=f"Rechazó la verificación del paseador {user_info}. Motivo: {body.reason}",
        )
    except Exception as e:
        print(f"[kyc] Error registrando audit log: {e}")

    if target_user:
        # Push al Paseador
        try:
            push.send_to_user(
                db=db,
                user_id=target_user.id,
                title="Verificación Rechazada ❌",
                body=f"Motivo: {body.reason}. Revisá tus fotos y volvé a intentarlo.",
                data={"type": "kyc_rejected"},
            )
        except Exception as e:
            print(f"[kyc] Error enviando push: {e}")

        # Email por Resend
        try:
            email.send_email(
                to_email=target_user.email,
                subject="Woofy Go - Actualización sobre tu verificación",
                body=(
                    f"Hola {target_user.full_name},\n\n"
                    "No pudimos aprobar tu verificación por el siguiente motivo:\n\n"
                    f"👉 {body.reason}\n\n"
                    "Por favor, volvé a ingresar a la app y subí nuevamente las fotos.\n\n"
                    "El equipo de Woofy Go 🐾"
                ),
            )
        except Exception as e:
            print(f"[kyc] Error enviando email: {e}")

    out = WalkerVerificationOut.model_validate(v)
    if target_user:
        out.user_full_name = target_user.full_name
        out.user_email = target_user.email
        out.user_phone = target_user.phone
    return out
