"""Road-based compatibility of consecutive transport bookings."""

import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING

from fastapi import HTTPException

from app.services.routing import get_driving_route_metrics
from app.services.transport_schedule import (
    MAX_SECONDS,
    ScheduleConflict,
    TransportWindow,
    evaluate_transport_pair,
    transport_window_bounds,
)


@dataclass(frozen=True)
class RoadPoint:

    latitude: float
    longitude: float


@dataclass(frozen=True)
class ScheduledTransport:

    window: TransportWindow
    pickup: RoadPoint
    dropoff: RoadPoint


def valid_road_point(point: RoadPoint) -> bool:

    if not isinstance(point, RoadPoint):
        return False

    lat = point.latitude
    lon = point.longitude

    if (
        type(lat) not in (int, float)
        or type(lon) not in (int, float)
    ):
        return False

    return (
        -90 <= lat <= 90
        and -180 <= lon <= 180
        and math.isfinite(lat)
        and math.isfinite(lon)
    )


def get_transfer_seconds(
    origin: RoadPoint,
    destination: RoadPoint,
) -> int | None:
    """Calculate road travel time between consecutive services."""

    if (
        not valid_road_point(origin)
        or not valid_road_point(destination)
    ):
        return None

    # Identical official coordinates require no road travel.
    # Handling and delivery times remain in the schedule window.
    if origin == destination:
        return 0

    try:

        distance, duration = get_driving_route_metrics(
            origin.latitude,
            origin.longitude,
            destination.latitude,
            destination.longitude,
        )

    except HTTPException:
        return None

    if (
        not isinstance(distance, Decimal)
        or not distance.is_finite()
        or distance < 0
        or not isinstance(duration, Decimal)
        or not duration.is_finite()
        or duration <= 0
        or duration > MAX_SECONDS
    ):
        return None

    return int(
        duration.to_integral_value(
            rounding=ROUND_CEILING
        )
    )


def evaluate_road_compatibility(
    first: ScheduledTransport,
    second: ScheduledTransport,
) -> ScheduleConflict:
    """Evaluate a pair without inventing travel times."""

    first_bounds = transport_window_bounds(first.window)
    second_bounds = transport_window_bounds(second.window)

    if first_bounds is None or second_bounds is None:
        return ScheduleConflict.INVALID_DATA

    if not all(
        valid_road_point(point)
        for point in (
            first.pickup,
            first.dropoff,
            second.pickup,
            second.dropoff,
        )
    ):
        return ScheduleConflict.INVALID_DATA

    # Zero is used only to detect an existing overlap.
    # It is not assumed to be the actual transfer duration.
    preliminary = evaluate_transport_pair(
        first.window,
        second.window,
        transfer_seconds=0,
    )

    if preliminary != ScheduleConflict.NONE:
        return preliminary

    if first_bounds[0] <= second_bounds[0]:

        earlier = first
        later = second

    else:

        earlier = second
        later = first

    transfer_seconds = get_transfer_seconds(
        earlier.dropoff,
        later.pickup,
    )

    return evaluate_transport_pair(
        earlier.window,
        later.window,
        transfer_seconds=transfer_seconds,
    )
