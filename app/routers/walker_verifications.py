from datetime import datetime, timezone, date
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, UserRole
from app.models.walker_verification import (
    WalkerVerification,
    WalkerVerificationStatus,
    DocumentStatus,
)
from app.schemas.walker_verification import (
    RejectRequest,
    WalkerVerificationOut, WalkerVerificationAdminOut,
    WalkerVerificationStatusOut,
)
from app.services import admin_log, email, push
from app.services.cloudinary_service import upload_kyc_document, delete_kyc_attempt

router = APIRouter(prefix="/walker-verifications", tags=["walker-verifications"])

def _get_or_create_verification(db: Session, user_id: int) -> WalkerVerification:
    v = db.query(WalkerVerification).filter(WalkerVerification.user_id == user_id).first()
    if not v:
        v = WalkerVerification(user_id=user_id)
        db.add(v)
        db.commit()
        db.refresh(v)
    return v

def _fill_user_data(out: WalkerVerificationOut, u: User | None) -> WalkerVerificationOut:
    if u:
        out.user_full_name = u.full_name
        out.user_email = u.email
        out.user_phone = u.phone
        out.user_dni_number = u.dni_number
        out.user_address = u.address
        out.user_birth_date = u.birth_date
        out.user_emergency_contact = u.emergency_contact
    return out

@router.post("/upload/identity", response_model=WalkerVerificationOut)
async def upload_identity(
    dni_front: UploadFile = File(...),
    dni_back: UploadFile = File(...),
    selfie: UploadFile = File(...),
    dni_number: str = None,
    address: str = None,
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    v = _get_or_create_verification(db, current_user.id)
    if dni_number:
        current_user.dni_number = dni_number
    if address:
        current_user.address = address
    uploaded_attempts = []
    commit_attempted = False
    try:
        v.dni_front_url = upload_kyc_document(await dni_front.read(), current_user.id, "dni_front", register_attempt=uploaded_attempts.append)
        v.dni_back_url = upload_kyc_document(await dni_back.read(), current_user.id, "dni_back", register_attempt=uploaded_attempts.append)
        v.selfie_url = upload_kyc_document(await selfie.read(), current_user.id, "selfie", register_attempt=uploaded_attempts.append)
        v.identity_status = DocumentStatus.PENDING
        v.status = WalkerVerificationStatus.PENDING
        v.identity_rejection_reason = None
        commit_attempted = True
        db.commit()
    except Exception as e:
        db.rollback()
        for attempt_id in (uploaded_attempts if not commit_attempted else ()):
            try:
                cleaned = delete_kyc_attempt(attempt_id, current_user.id)
                if not cleaned:
                    print("ADVERTENCIA KYC: limpieza no confirmada")
            except Exception:
                print("ADVERTENCIA KYC: fallo de limpieza compensatoria")
        raise HTTPException(status_code=500, detail=f"Error subiendo identidad: {e}")

    db.refresh(v)
    return _fill_user_data(WalkerVerificationOut.model_validate(v), current_user)

@router.post("/upload/license", response_model=WalkerVerificationOut)
async def upload_license(
    license_number: str,
    license_class: str,
    license_jurisdiction: str,
    license_expiration: str,
    license_front: UploadFile = File(...),
    license_back: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    v = _get_or_create_verification(db, current_user.id)
    uploaded_attempts = []
    commit_attempted = False
    try:
        v.license_number = license_number
        v.license_class = license_class
        v.license_jurisdiction = license_jurisdiction
        v.license_expiration = datetime.strptime(license_expiration, "%Y-%m-%d").date()
        v.license_front_url = upload_kyc_document(await license_front.read(), current_user.id, "license_front", register_attempt=uploaded_attempts.append)
        v.license_back_url = upload_kyc_document(await license_back.read(), current_user.id, "license_back", register_attempt=uploaded_attempts.append)
        v.license_status = DocumentStatus.PENDING
        v.status = WalkerVerificationStatus.PENDING
        v.license_rejection_reason = None
        commit_attempted = True
        db.commit()
    except Exception as e:
        db.rollback()
        for attempt_id in (uploaded_attempts if not commit_attempted else ()):
            try:
                cleaned = delete_kyc_attempt(attempt_id, current_user.id)
                if not cleaned:
                    print("ADVERTENCIA KYC: limpieza no confirmada")
            except Exception:
                print("ADVERTENCIA KYC: fallo de limpieza compensatoria")
        raise HTTPException(status_code=500, detail=f"Error subiendo licencia: {e}")

    db.refresh(v)
    return _fill_user_data(WalkerVerificationOut.model_validate(v), current_user)

@router.post("/upload/vehicle", response_model=WalkerVerificationOut)
async def upload_vehicle(
    vehicle_plate: str,
    vehicle_brand: str,
    vehicle_model: str,
    vehicle_year: int,
    vehicle_photo: UploadFile = File(...),
    vehicle_cedula: UploadFile = File(...),
    vehicle_insurance: UploadFile = File(None),
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    if current_user.service_type == "transport" and vehicle_insurance is None:
        raise HTTPException(status_code=422, detail="El seguro del vehículo es obligatorio para Pet Taxi.")
    v = _get_or_create_verification(db, current_user.id)
    uploaded_attempts = []
    commit_attempted = False
    try:
        v.vehicle_plate = vehicle_plate
        v.vehicle_brand = vehicle_brand
        v.vehicle_model = vehicle_model
        v.vehicle_year = vehicle_year
        v.vehicle_photo_url = upload_kyc_document(await vehicle_photo.read(), current_user.id, "vehicle_photo", register_attempt=uploaded_attempts.append)
        v.vehicle_cedula_url = upload_kyc_document(await vehicle_cedula.read(), current_user.id, "vehicle_cedula", register_attempt=uploaded_attempts.append)
        if vehicle_insurance:
            v.vehicle_insurance_url = upload_kyc_document(await vehicle_insurance.read(), current_user.id, "vehicle_insurance", register_attempt=uploaded_attempts.append)

        v.vehicle_status = DocumentStatus.PENDING
        v.status = WalkerVerificationStatus.PENDING
        v.vehicle_rejection_reason = None
        commit_attempted = True
        db.commit()
    except Exception as e:
        db.rollback()
        for attempt_id in (uploaded_attempts if not commit_attempted else ()):
            try:
                cleaned = delete_kyc_attempt(attempt_id, current_user.id)
                if not cleaned:
                    print("ADVERTENCIA KYC: limpieza no confirmada")
            except Exception:
                print("ADVERTENCIA KYC: fallo de limpieza compensatoria")
        raise HTTPException(status_code=500, detail=f"Error subiendo vehiculo: {e}")

    db.refresh(v)
    return _fill_user_data(WalkerVerificationOut.model_validate(v), current_user)

@router.get("/me", response_model=WalkerVerificationStatusOut)
def get_my_verification(
    current_user: User = Depends(require_role(UserRole.WALKER)),
    db: Session = Depends(get_db),
):
    v = db.query(WalkerVerification).filter(WalkerVerification.user_id == current_user.id).first()
    if not v:
        return WalkerVerificationStatusOut(has_verification=False)

    return WalkerVerificationStatusOut(
        has_verification=True,
        status=v.status.value,
        identity_status=v.identity_status.value,
        license_status=v.license_status.value,
        vehicle_status=v.vehicle_status.value,
        rejection_reason=v.rejection_reason,
    )

@router.get("/admin/pending", response_model=list[WalkerVerificationAdminOut])
def list_pending(
    status_filter: str | None = Query(default="pending"),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    query = db.query(WalkerVerification, User).join(User, WalkerVerification.user_id == User.id)
    if status_filter == "pending":
        query = query.filter(WalkerVerification.status == WalkerVerificationStatus.PENDING)

    results = query.order_by(WalkerVerification.updated_at.desc()).all()
    return [WalkerVerificationAdminOut.model_validate(_fill_user_data(WalkerVerificationOut.model_validate(v), u).model_dump()) for v, u in results]

@router.post("/admin/{verification_id}/approve/{block}", response_model=WalkerVerificationOut)
def approve_block(
    verification_id: int,
    block: str,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    v = db.get(WalkerVerification, verification_id)
    if not v:
        raise HTTPException(status_code=404, detail="Verificacion no encontrada")

    if block == "identity":
        if not all([v.dni_front_url, v.dni_back_url, v.selfie_url]):
            raise HTTPException(status_code=422, detail="No se puede aprobar la identidad sin DNI frente, DNI dorso y selfie.")
        v.identity_status = DocumentStatus.APPROVED
    elif block == "license":
        required_license = [
            v.license_number,
            v.license_class,
            v.license_jurisdiction,
            v.license_expiration,
            v.license_front_url,
            v.license_back_url,
        ]
        if not all(
            value is not None
            and (not isinstance(value, str) or bool(value.strip()))
            for value in required_license
        ):
            raise HTTPException(
                status_code=422,
                detail="No se puede aprobar la licencia sin todos los datos y documentos.",
            )
        if v.license_expiration < date.today():
            raise HTTPException(
                status_code=422,
                detail="No se puede aprobar una licencia vencida.",
            )
        v.license_status = DocumentStatus.APPROVED
    elif block == "vehicle":
        vehicle_user = db.get(User, v.user_id)
        if vehicle_user is None:
            raise HTTPException(status_code=404, detail="Usuario del prestador no encontrado.")

        required_vehicle = [
            v.vehicle_plate,
            v.vehicle_brand,
            v.vehicle_model,
            v.vehicle_year,
            v.vehicle_photo_url,
            v.vehicle_cedula_url,
        ]
        if not all(
            value is not None
            and (not isinstance(value, str) or bool(value.strip()))
            for value in required_vehicle
        ):
            raise HTTPException(
                status_code=422,
                detail="No se puede aprobar el vehículo sin todos los datos y documentos.",
            )
        if vehicle_user.service_type == "transport" and (
            not v.vehicle_insurance_url or not v.vehicle_insurance_url.strip()
        ):
            raise HTTPException(
                status_code=422,
                detail="No se puede aprobar el vehículo de Pet Taxi sin seguro registrado.",
            )
        v.vehicle_status = DocumentStatus.APPROVED
    else:
        raise HTTPException(status_code=400, detail="Bloque invalido")

    # Si todos los bloques aplicables estan aprobados, aprobamos el global
    target_user = db.get(User, v.user_id)
    is_approved = (v.identity_status == DocumentStatus.APPROVED)
    if target_user and target_user.service_type == "transport":
        is_approved = is_approved and (v.license_status == DocumentStatus.APPROVED) and (v.vehicle_status == DocumentStatus.APPROVED)

    if is_approved:
        v.status = WalkerVerificationStatus.APPROVED
        v.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(v)

    if is_approved and target_user:
        try:
            push.send_to_user(db=db, user_id=target_user.id, title="Cuenta Aprobada", body="Tu cuenta esta 100% verificada. Ya podes operar.", data={"type": "kyc_approved"})
        except Exception:
            # La aprobacion confirmada no depende del servicio push.
            pass

    return _fill_user_data(WalkerVerificationOut.model_validate(v), db.get(User, v.user_id))

@router.post("/admin/{verification_id}/reject/{block}", response_model=WalkerVerificationOut)
def reject_block(
    verification_id: int,
    block: str,
    body: RejectRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    v = db.get(WalkerVerification, verification_id)
    if not v:
        raise HTTPException(status_code=404, detail="Verificacion no encontrada")

    if block == "identity":
        v.identity_status = DocumentStatus.REJECTED
        v.identity_rejection_reason = body.reason
    elif block == "license":
        v.license_status = DocumentStatus.REJECTED
        v.license_rejection_reason = body.reason
    elif block == "vehicle":
        v.vehicle_status = DocumentStatus.REJECTED
        v.vehicle_rejection_reason = body.reason
    else:
        raise HTTPException(status_code=400, detail="Bloque invalido")

    v.status = WalkerVerificationStatus.REJECTED
    v.rejection_reason = body.reason
    db.commit()
    db.refresh(v)

    target_user = db.get(User, v.user_id)
    if target_user:
        push.send_to_user(db=db, user_id=target_user.id, title="Documento Rechazado", body=f"Motivo: {body.reason}.", data={"type": "kyc_rejected"})

    return _fill_user_data(WalkerVerificationOut.model_validate(v), target_user)


@router.get(
    "/admin/{verification_id}/document/{document_type}/temporary-url"
)
async def get_admin_kyc_document_temporary_url(
    verification_id: int,
    document_type: str,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Prepara una URL temporal para documentos KYC authenticated."""
    from time import time
    from fastapi.responses import JSONResponse
    from cloudinary.utils import private_download_url
    from app.core.config import settings
    from app.services.kyc_document_access import (
        KYCDocumentAccessError,
        select_authenticated_kyc_document,
    )

    if verification_id <= 0:
        raise HTTPException(status_code=404, detail="Documento no disponible")

    verification = db.get(WalkerVerification, verification_id)
    if verification is None:
        raise HTTPException(status_code=404, detail="Documento no disponible")

    try:
        public_id, file_format = select_authenticated_kyc_document(
            verification,
            document_type,
            settings.CLOUDINARY_CLOUD_NAME,
        )
    except KYCDocumentAccessError:
        raise HTTPException(status_code=404, detail="Documento no disponible")

    expires_in = 60
    expires_at = int(time()) + expires_in

    try:
        signed_url = private_download_url(
            public_id,
            file_format,
            type="authenticated",
            expires_at=expires_at,
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="No se pudo generar el acceso temporal",
        )

    if (
        not isinstance(signed_url, str)
        or not signed_url.startswith("https://")
    ):
        raise HTTPException(
            status_code=503,
            detail="No se pudo generar el acceso temporal",
        )

    return JSONResponse(
        content={
            "url": signed_url,
            "expires_in": expires_in,
        },
        headers={
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )
