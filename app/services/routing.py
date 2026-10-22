from decimal import Decimal, ROUND_HALF_UP
import requests
from fastapi import HTTPException, status
from app.core.config import settings


def get_driving_distance_km(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> Decimal:
    """
    Calcula la distancia vehicular real mediante Mapbox Directions.
    Si la API falla, NO inventa kilómetros ni usa línea recta: falla explícitamente.
    """
    token = (getattr(settings, "MAPBOX_ACCESS_TOKEN", None) or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de rutas Mapbox no configurado en el servidor.",
        )

    url = (
        f"https://api.mapbox.com/directions/v5/mapbox/driving/"
        f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        f"?access_token={token}&overview=false"
    )

    try:
        resp = requests.get(url, timeout=6.0)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error de conexión con el proveedor de rutas (Mapbox): {e}",
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo calcular la ruta vehicular para los puntos seleccionados.",
        )

    data = resp.json()
    routes = data.get("routes") or []
    if not routes or "distance" not in routes[0]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mapbox no encontró una ruta transitable entre los puntos indicados.",
        )

    meters = Decimal(str(routes[0]["distance"]))
    km = (meters / Decimal("1000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return km