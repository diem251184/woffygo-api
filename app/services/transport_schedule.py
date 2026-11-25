"""Conservative scheduling rules for assigned transport services."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


MAX_SECONDS = 2147483647


class ScheduleConflict(str, Enum):

    NONE = "none"
    INVALID_DATA = "invalid_data"
    EXPIRED_PICKUP = "expired_pickup"
    OVERLAPPING = "overlapping"
    TRANSFER_UNKNOWN = "transfer_unknown"
    INSUFFICIENT_TRANSFER = "insufficient_transfer"
    ACTIVE_SERVICE = "active_service"


@dataclass(frozen=True)
class TransportWindow:

    pickup_at: datetime
    road_seconds: int
    pickup_handling_seconds: int
    delivery_handling_seconds: int


def _valid_seconds(value: object) -> bool:

    return (
        type(value) is int
        and 0 <= value <= MAX_SECONDS
    )


def _utc(value: object) -> datetime | None:

    if not isinstance(value, datetime):
        return None

    try:

        if value.utcoffset() is None:
            return None

        return value.astimezone(timezone.utc)

    except (ValueError, OverflowError, TypeError):
        return None


def transport_window_bounds(
    window: TransportWindow,
) -> tuple[datetime, datetime] | None:

    start = _utc(window.pickup_at)

    if start is None:
        return None

    values = (
        window.road_seconds,
        window.pickup_handling_seconds,
        window.delivery_handling_seconds,
    )

    if not all(_valid_seconds(value) for value in values):
        return None

    total_seconds = sum(values)

    # A reservation cannot occupy a zero-length window.
    if total_seconds <= 0:
        return None

    try:

        end = start + timedelta(seconds=total_seconds)

    except (ValueError, OverflowError):
        return None

    return start, end


def evaluate_transport_pair(
    first: TransportWindow,
    second: TransportWindow,
    *,
    transfer_seconds: int | None,
) -> ScheduleConflict:
    """Evaluate two bookings in chronological order.

    transfer_seconds must describe the real road route
    from the earlier booking's delivery point to the
    later booking's pickup point.
    """

    first_bounds = transport_window_bounds(first)
    second_bounds = transport_window_bounds(second)

    if first_bounds is None or second_bounds is None:
        return ScheduleConflict.INVALID_DATA

    earlier, later = sorted(
        (first_bounds, second_bounds),
        key=lambda bounds: bounds[0],
    )

    earlier_end = earlier[1]
    later_start = later[0]

    if earlier_end > later_start:
        return ScheduleConflict.OVERLAPPING

    # An unknown transfer is not equivalent to zero.
    if transfer_seconds is None:
        return ScheduleConflict.TRANSFER_UNKNOWN

    if not _valid_seconds(transfer_seconds):
        return ScheduleConflict.INVALID_DATA

    try:

        arrival = earlier_end + timedelta(
            seconds=transfer_seconds
        )

    except (ValueError, OverflowError):
        return ScheduleConflict.INVALID_DATA

    if arrival > later_start:
        return ScheduleConflict.INSUFFICIENT_TRANSFER

    return ScheduleConflict.NONE


def evaluate_transport_candidate(
    candidate: TransportWindow,
    *,
    now: datetime,
    has_service_in_progress: bool,
) -> ScheduleConflict:
    """Validate the minimum scheduling prerequisites."""

    if type(has_service_in_progress) is not bool:
        return ScheduleConflict.INVALID_DATA

    bounds = transport_window_bounds(candidate)
    current = _utc(now)

    if bounds is None or current is None:
        return ScheduleConflict.INVALID_DATA

    if bounds[0] <= current:
        return ScheduleConflict.EXPIRED_PICKUP

    # Conservative policy until active-service
    # remaining duration can be reliably established.
    if has_service_in_progress:
        return ScheduleConflict.ACTIVE_SERVICE

    return ScheduleConflict.NONE
