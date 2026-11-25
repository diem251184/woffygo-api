from decimal import Decimal, ROUND_HALF_UP
import requests
from fastapi import HTTPException, status
from app.core.config import settings


def get_driving_route_metrics(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> tuple[Decimal, Decimal | None]:
    """
    Calcula distancia y duracion vial mediante Mapbox Directions.
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
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error de conexion con el proveedor de rutas.",
        ) from None

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo calcular la ruta vehicular para los puntos seleccionados.",
        )

    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Respuesta invalida del proveedor de rutas.",
        ) from None

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Respuesta invalida del proveedor de rutas.",
        )

    routes = data.get("routes") or []

    if not isinstance(routes, list) or (
        routes and not isinstance(routes[0], dict)
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Respuesta invalida del proveedor de rutas.",
        )
    if not routes or "distance" not in routes[0]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mapbox no encontró una ruta transitable entre los puntos indicados.",
        )

    try:
        meters = Decimal(str(routes[0]["distance"]))

        if not meters.is_finite() or meters < 0:
            raise ValueError("Distancia invalida")

        km = (meters / Decimal("1000")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    except (ArithmeticError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Distancia vial invalida.",
        ) from None

    duration_seconds: Decimal | None = None

    raw_duration = routes[0].get("duration")

    if raw_duration is not None:
        try:
            parsed_duration = Decimal(str(raw_duration))

            if (
                parsed_duration.is_finite()
                and parsed_duration >= 0
                and (meters == 0 or parsed_duration > 0)
            ):
                duration_seconds = parsed_duration
        except (ArithmeticError, ValueError, TypeError):
            duration_seconds = None

    return km, duration_seconds


def get_driving_distance_km(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> Decimal:
    """Mantiene el contrato utilizado por las cotizaciones existentes."""
    distance_km, _ = get_driving_route_metrics(
        origin_lat,
        origin_lon,
        dest_lat,
        dest_lon,
    )
    return distance_km
