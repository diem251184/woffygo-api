from fastapi import APIRouter

from app.core.config import settings


router = APIRouter(prefix="/app", tags=["app"])


@router.get("/version")
def get_app_version() -> dict:
    """Devuelve info de version de la app movil.

    La app consulta este endpoint al abrir. Si LATEST_APP_VERSION es mayor
    a la version instalada, muestra un cartel con link de descarga.

    No requiere autenticacion: es info publica.
    """
    return {
        "latest_version": settings.LATEST_APP_VERSION,
        "min_supported_version": settings.MIN_SUPPORTED_APP_VERSION,
        "download_url": settings.APP_DOWNLOAD_URL,
        "release_notes": settings.APP_RELEASE_NOTES,
    }