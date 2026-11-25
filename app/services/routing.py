from decimal import Decimal, ROUND_HALF_UP
import requests
from fastapi import HTTPException, status
from app.core.config import settings


def get_driving_route_details(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    include_geometry: bool = False,
) -> tuple[
    Decimal,
    Decimal | None,
    list[list[float]] | None,
]:
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
        if include_geometry:
            from urllib.parse import (
                urlsplit,
                urlunsplit,
                parse_qsl,
                urlencode,
            )

            parts = urlsplit(url)

            parameters = [
                (key, value)
                for key, value in parse_qsl(
                    parts.query,
                    keep_blank_values=True,
                )
                if key.lower() not in (
                    "geometries",
                    "overview",
                )
            ]

            parameters.extend([
                ("geometries", "geojson"),
                ("overview", "full"),
            ])

            url = urlunsplit(
                parts._replace(
                    query=urlencode(parameters)
                )
            )

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

    coordinates = None

    if include_geometry:

        geometry = routes[0].get("geometry")

        if (
            isinstance(geometry, dict)
            and geometry.get("type") == "LineString"
        ):

            raw = geometry.get("coordinates")

            if (
                isinstance(raw, list)
                and 2 <= len(raw) <= 50000
            ):

                parsed = []
                valid = True

                for point in raw:

                    if (
                        not isinstance(point, list)
                        or len(point) != 2
                        or type(point[0]) not in (int, float)
                        or type(point[1]) not in (int, float)
                    ):
                        valid = False
                        break

                    lon, lat = point

                    if (
                        not -180 <= lon <= 180
                        or not -90 <= lat <= 90
                    ):
                        valid = False
                        break

                    parsed.append([
                        float(lon),
                        float(lat),
                    ])

                if valid:
                    coordinates = parsed

    return km, duration_seconds, coordinates


def get_driving_route_metrics(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> tuple[Decimal, Decimal | None]:
    """Conserva el contrato original de distancia y duracion."""

    km, duration, _ = get_driving_route_details(
        origin_lat,
        origin_lon,
        dest_lat,
        dest_lon,
        include_geometry=False,
    )

    return km, duration


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
