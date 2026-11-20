from fastapi import APIRouter, Depends, status, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.services.cloudinary_service import upload_pending_user_avatar, delete_pending_user_avatar

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Register profile modifications for administrative review."""

    from app.models.user import UserRole
    from app.services.profile_review import request_profile_review

    if current_user.role not in (UserRole.OWNER, UserRole.WALKER):
        raise HTTPException(
            status_code=403,
            detail="Esta operación no corresponde al perfil de la cuenta",
        )

    changes = payload.model_dump(exclude_unset=True)

    for required_field in ("full_name", "phone"):
        if required_field in changes and changes[required_field] is None:
            raise HTTPException(
                status_code=422,
                detail="Nombre y teléfono son obligatorios",
            )

    try:
        request_profile_review(
            db,
            user_id=current_user.id,
            changes=changes,
        )

        db.commit()
        db.refresh(current_user)
        return current_user

    except Exception:
        db.rollback()
        raise

@router.post("/me/photo", response_model=UserResponse)
@router.post("/me/photo/", response_model=UserResponse)
async def upload_my_photo(
    photo: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from io import BytesIO
    import warnings
    from PIL import Image, UnidentifiedImageError

    # Rechazar revisiones pendientes antes de leer el archivo.
    if current_user.profile_review_status == "pending":
        raise HTTPException(
            status_code=409,
            detail="Ya existe una revisión de perfil pendiente",
        )

    max_file_bytes = 10 * 1024 * 1024
    allowed_formats = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }

    declared_type = (photo.content_type or "").lower()

    if declared_type not in allowed_formats.values():
        raise HTTPException(
            status_code=415,
            detail="Solo se admiten imágenes JPEG, PNG o WebP",
        )

    if photo.size is not None and photo.size > max_file_bytes:
        raise HTTPException(
            status_code=413,
            detail="La fotografía supera el límite de 10 MiB",
        )

    file_bytes = await photo.read(max_file_bytes + 1)

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="El archivo enviado está vacío",
        )

    if len(file_bytes) > max_file_bytes:
        raise HTTPException(
            status_code=413,
            detail="La fotografía supera el límite de 10 MiB",
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(BytesIO(file_bytes)) as image:
                detected_format = image.format
                width, height = image.size

                if (
                    detected_format not in allowed_formats
                    or allowed_formats[detected_format] != declared_type
                    or width < 1
                    or height < 1
                    or width > 10000
                    or height > 10000
                    or width * height > 20000000
                ):
                    raise ValueError("Invalid image")

                image.verify()

            with Image.open(BytesIO(file_bytes)) as image:
                image.load()

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(
            status_code=422,
            detail="La imagen está dañada o no cumple los requisitos",
        )

    uploaded_public_id = None
    commit_attempted = False

    try:
        from app.services.profile_review import request_profile_review

        secure_url, uploaded_public_id = upload_pending_user_avatar(
            file_bytes,
            current_user.id,
        )

        review = request_profile_review(
            db,
            user_id=current_user.id,
            changes={"profile_photo_url": secure_url},
            allow_internal_photo=True,
        )

        if review is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La fotografía no generó cambios verificables",
            )

        commit_attempted = True
        db.commit()
        db.refresh(current_user)
        return current_user

    except HTTPException:
        db.rollback()
        if uploaded_public_id is not None and not commit_attempted:
            try:
                if not delete_pending_user_avatar(uploaded_public_id, current_user.id):
                    print("ADVERTENCIA: limpieza pendiente no confirmada")
            except Exception:
                print("ADVERTENCIA: fallo en limpieza pendiente")
        raise
    except Exception:
        db.rollback()
        if uploaded_public_id is not None and not commit_attempted:
            try:
                if not delete_pending_user_avatar(uploaded_public_id, current_user.id):
                    print("ADVERTENCIA: limpieza pendiente no confirmada")
            except Exception:
                print("ADVERTENCIA: fallo en limpieza pendiente")
        if commit_attempted:
            print("ADVERTENCIA: confirmar estado de transaccion antes de limpiar avatar")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo procesar la fotografía",
        )
