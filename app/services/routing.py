"""Distancia por calles usando Mapbox Directions. El token vive solo en el servidor."""
import os
from decimal import Decimal

import httpx
from fastapi import HTTPException, status

MAX_ROUTE_KM = Decimal("100")


def _valid_coords(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180


def get_driving_distance_km(
    origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float
) -> Decimal:
    token = os.environ.get("MAPBOX_ACCESS_TOKEN", "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El calculo de rutas no esta configurado",
        )
    if not (_valid_coords(origin_lat, origin_lon) and _valid_coords(dest_lat, dest_lon)):
        raise HTTPException(status_code=400, detail="Coordenadas invalidas")

    url = (
        "https://api.mapbox.com/directions/v5/mapbox/driving/"
        f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    )
    params = {"access_token": token, "overview": "false", "alternatives": "false"}

    try:
        response = httpx.get(url, params=params, timeout=8.0)
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo calcular la ruta. Intenta nuevamente.",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo calcular la ruta. Intenta nuevamente.",
        )

    data = response.json()
    routes = data.get("routes") or []
    if data.get("code") != "Ok" or not routes:
        raise HTTPException(status_code=400, detail="No se encontro una ruta entre origen y destino")

    meters = routes[0].get("distance")
    if meters is None:
        raise HTTPException(status_code=502, detail="Respuesta de ruta invalida")

    km = (Decimal(str(meters)) / Decimal(1000)).quantize(Decimal("0.01"))
    if km <= 0:
        raise HTTPException(status_code=400, detail="Origen y destino son el mismo lugar")
    if km > MAX_ROUTE_KM:
        raise HTTPException(status_code=400, detail="La distancia supera el maximo permitido")
    return km