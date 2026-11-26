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

def _parse_navigation_steps(route: dict) -> list[dict] | None:
    import math

    def valid_number(value):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
        ):
            return None

        try:
            number = float(value)
        except (ArithmeticError, ValueError, TypeError):
            return None

        if not math.isfinite(number) or number < 0:
            return None

        return number

    def valid_coordinate(value):
        if not isinstance(value, list) or len(value) != 2:
            return None

        lon, lat = value

        if (
            isinstance(lon, bool)
            or isinstance(lat, bool)
            or not isinstance(lon, (int, float))
            or not isinstance(lat, (int, float))
        ):
            return None

        if not (
            math.isfinite(lon)
            and math.isfinite(lat)
            and -180 <= lon <= 180
            and -90 <= lat <= 90
        ):
            return None

        return [float(lon), float(lat)]

    def valid_geometry(value):
        if (
            not isinstance(value, dict)
            or value.get("type") != "LineString"
        ):
            return None

        raw = value.get("coordinates")

        if (
            not isinstance(raw, list)
            or not 2 <= len(raw) <= 50000
        ):
            return None

        coordinates = []

        for point in raw:
            parsed = valid_coordinate(point)

            if parsed is None:
                return None

            coordinates.append(parsed)

        return coordinates

    def valid_text(value, limit=500):
        if not isinstance(value, str):
            return None

        text = value.strip()

        if not text or len(text) > limit:
            return None

        return text

    if not isinstance(route, dict):
        return None

    legs = route.get("legs")

    if (
        not isinstance(legs, list)
        or not legs
        or len(legs) > 10
    ):
        return None

    result = []
    total_geometry_points = 0

    for leg in legs:
        if not isinstance(leg, dict):
            return None

        steps = leg.get("steps")

        if (
            not isinstance(steps, list)
            or not steps
        ):
            return None

        for step in steps:
            if len(result) >= 1000:
                return None

            if not isinstance(step, dict):
                return None

            maneuver = step.get("maneuver")

            if not isinstance(maneuver, dict):
                return None

            instruction = valid_text(
                maneuver.get("instruction")
            )

            maneuver_type = valid_text(
                maneuver.get("type"), 80
            )

            modifier = valid_text(
                maneuver.get("modifier"), 80
            )

            location = valid_coordinate(
                maneuver.get("location")
            )

            distance = valid_number(
                step.get("distance")
            )

            duration = valid_number(
                step.get("duration")
            )

            geometry = valid_geometry(
                step.get("geometry")
            )

            if (
                instruction is None
                or maneuver_type is None
                or location is None
                or distance is None
                or duration is None
            ):
                return None

            if geometry is None:
                if not (
                    maneuver_type == "arrive"
                    and distance == 0
                ):
                    return None
            else:
                total_geometry_points += len(geometry)

                if total_geometry_points > 100000:
                    return None

            voice = []

            raw_voice = step.get("voiceInstructions", [])

            if not isinstance(raw_voice, list):
                return None

            if len(raw_voice) > 30:
                return None

            for item in raw_voice:
                if not isinstance(item, dict):
                    continue

                announcement = valid_text(
                    item.get("announcement")
                )

                trigger = valid_number(
                    item.get("distanceAlongGeometry")
                )

                if (
                    announcement is None
                    or trigger is None
                    or trigger > distance + 1
                ):
                    continue

                voice.append({
                    "announcement": announcement,
                    "distance_along_geometry_m": trigger,
                })

            voice.sort(
                key=lambda item:
                    item["distance_along_geometry_m"],
                reverse=True,
            )

            result.append({
                "instruction": instruction,
                "type": maneuver_type,
                "modifier": modifier,
                "street_name": valid_text(
                    step.get("name"), 300
                ),
                "location": location,
                "distance_m": distance,
                "duration_seconds": duration,
                "geometry": geometry,
                "voice_instructions": voice,
            })

    if (
        not result
        or result[-1]["type"] != "arrive"
    ):
        return None

    return result


def get_driving_navigation_details(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float, *, include_geometry: bool=False) -> tuple[Decimal, Decimal | None, list[list[float]] | None, list[dict] | None]:
    """
    Calcula distancia y duracion vial mediante Mapbox Directions.
    Si la API falla, NO inventa kilómetros ni usa línea recta: falla explícitamente.
    """
    token = (getattr(settings, 'MAPBOX_ACCESS_TOKEN', None) or '').strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Servicio de rutas Mapbox no configurado en el servidor.')
    url = f'https://api.mapbox.com/directions/v5/mapbox/driving/{origin_lon},{origin_lat};{dest_lon},{dest_lat}?access_token={token}&overview=false'
    try:
        if include_geometry:
            from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
            parts = urlsplit(url)
            parameters = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key.lower() not in ('geometries', 'overview')]
            parameters.extend([('geometries', 'geojson'), ('overview', 'full'), ('steps', 'true'), ('language', 'es'), ('voice_instructions', 'true'), ('voice_units', 'metric'), ('banner_instructions', 'true')])
            url = urlunsplit(parts._replace(query=urlencode(parameters)))
        resp = requests.get(url, timeout=6.0)
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Error de conexion con el proveedor de rutas.') from None
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='No se pudo calcular la ruta vehicular para los puntos seleccionados.')
    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Respuesta invalida del proveedor de rutas.') from None
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Respuesta invalida del proveedor de rutas.')
    routes = data.get('routes') or []
    if not isinstance(routes, list) or (routes and (not isinstance(routes[0], dict))):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Respuesta invalida del proveedor de rutas.')
    if not routes or 'distance' not in routes[0]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Mapbox no encontró una ruta transitable entre los puntos indicados.')
    try:
        meters = Decimal(str(routes[0]['distance']))
        if not meters.is_finite() or meters < 0:
            raise ValueError('Distancia invalida')
        km = (meters / Decimal('1000')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ArithmeticError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Distancia vial invalida.') from None
    duration_seconds: Decimal | None = None
    raw_duration = routes[0].get('duration')
    if raw_duration is not None:
        try:
            parsed_duration = Decimal(str(raw_duration))
            if parsed_duration.is_finite() and parsed_duration >= 0 and (meters == 0 or parsed_duration > 0):
                duration_seconds = parsed_duration
        except (ArithmeticError, ValueError, TypeError):
            duration_seconds = None
    coordinates = None
    if include_geometry:
        geometry = routes[0].get('geometry')
        if isinstance(geometry, dict) and geometry.get('type') == 'LineString':
            raw = geometry.get('coordinates')
            if isinstance(raw, list) and 2 <= len(raw) <= 50000:
                parsed = []
                valid = True
                for point in raw:
                    if not isinstance(point, list) or len(point) != 2 or type(point[0]) not in (int, float) or (type(point[1]) not in (int, float)):
                        valid = False
                        break
                    lon, lat = point
                    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
                        valid = False
                        break
                    parsed.append([float(lon), float(lat)])
                if valid:
                    coordinates = parsed
    maneuvers = _parse_navigation_steps(routes[0])
    return (km, duration_seconds, coordinates, maneuvers)
