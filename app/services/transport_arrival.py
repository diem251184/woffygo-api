from dataclasses import dataclass
from datetime import datetime, timezone
import math

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.booking import (
    Booking,
    BookingStatus,
    ServiceType,
)


ARRIVAL_RADIUS_METERS = 40.0
ARRIVAL_MAX_ACCURACY_METERS = 20.0
ARRIVAL_MAX_SPEED_KMH = 5.0
ARRIVAL_MAX_AGE_SECONDS = 15.0
ARRIVAL_MIN_SAMPLES = 3
ARRIVAL_MIN_DWELL_SECONDS = 20.0

# Maximum acceptable interruption between samples.
ARRIVAL_MAX_SAMPLE_GAP_SECONDS = 10.0

# Maximum transmission delay for delivery evidence.
ARRIVAL_MAX_TRANSMISSION_DELAY_SECONDS = 15.0

# Small device/server clock tolerance.
ARRIVAL_MAX_CLOCK_SKEW_SECONDS = 5.0

ARRIVAL_SAMPLE_LIMIT = 120


@dataclass(frozen=True)
class TransportArrivalEvidence:
    eligible: bool
    reason: str
    distance_meters: float | None = None
    valid_samples: int = 0
    dwell_seconds: float = 0.0


def _aware(value):
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _bounded_number(value, minimum, maximum):
    if value is None or isinstance(value, bool):
        return False

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False

    return (
        math.isfinite(number)
        and minimum <= number <= maximum
    )


def evaluate_transport_arrival(
    db: Session,
    booking: Booking,
) -> TransportArrivalEvidence:
    """
    Evaluate persisted delivery evidence.

    This function never changes booking or payment state.

    The caller must authenticate and authorize the user.

    For finalization, the caller must hold a booking
    row lock until arrival, PIN and status are committed.
    """

    if booking.service_type != ServiceType.TRANSPORT:
        return TransportArrivalEvidence(
            False, "NOT_TRANSPORT"
        )

    if booking.status != BookingStatus.IN_PROGRESS:
        return TransportArrivalEvidence(
            False, "NOT_IN_PROGRESS"
        )

    if booking.provider_id is None:
        return TransportArrivalEvidence(
            False, "PROVIDER_MISSING"
        )

    if not _aware(booking.started_at):
        return TransportArrivalEvidence(
            False, "START_TIME_MISSING"
        )

    if booking.dropoff_location is None:
        return TransportArrivalEvidence(
            False, "DESTINATION_MISSING"
        )

    # Do not filter out inaccurate or mocked samples
    # before checking the consecutive evidence chain.
    #
    # Such samples must interrupt the chain rather
    # than silently disappear from the evaluation.

    statement = text("""
        SELECT
            wl.id,
            wl.captured_at,
            wl.recorded_at,
            wl.accuracy_meters,
            wl.speed_kmh,
            wl.is_mocked,
            ST_Distance(
                CAST(wl.location AS geography),
                CAST(b.dropoff_location AS geography)
            ) AS distance_meters

        FROM walk_locations AS wl

        INNER JOIN bookings AS b
            ON b.id = wl.walk_id

        WHERE wl.walk_id = :booking_id
          AND wl.recorded_at >= :started_at

        ORDER BY
            wl.recorded_at DESC,
            wl.id DESC

        LIMIT :sample_limit
    """)

    rows = db.execute(
        statement,
        {
            "booking_id": booking.id,
            "started_at": booking.started_at,
            "sample_limit": ARRIVAL_SAMPLE_LIMIT,
        },
    ).mappings().all()

    now = datetime.now(timezone.utc)

    if not rows:
        return TransportArrivalEvidence(
            False, "GPS_MISSING"
        )

    latest = rows[0]

    latest_capture = latest["captured_at"]
    latest_receipt = latest["recorded_at"]

    if not (
        _aware(latest_capture)
        and _aware(latest_receipt)
    ):
        return TransportArrivalEvidence(
            False, "GPS_METADATA_MISSING"
        )

    capture_age = (
        now - latest_capture
    ).total_seconds()

    receipt_age = (
        now - latest_receipt
    ).total_seconds()

    if (
        capture_age < 0
        or capture_age > ARRIVAL_MAX_AGE_SECONDS
        or receipt_age < 0
        or receipt_age > ARRIVAL_MAX_AGE_SECONDS
    ):
        return TransportArrivalEvidence(
            False, "GPS_STALE"
        )

    latest_distance = None

    if _bounded_number(
        latest["distance_meters"],
        0,
        21000000,
    ):
        latest_distance = float(
            latest["distance_meters"]
        )

    def invalid_reason(row):
        captured = row["captured_at"]
        received = row["recorded_at"]

        if not (
            _aware(captured)
            and _aware(received)
        ):
            return "GPS_METADATA_MISSING"

        if (
            captured < booking.started_at
            or received < booking.started_at
            or captured > now
            or received > now
        ):
            return "GPS_TIME_INVALID"

        delay = (
            received - captured
        ).total_seconds()

        if not (
            -ARRIVAL_MAX_CLOCK_SKEW_SECONDS
            <= delay
            <= ARRIVAL_MAX_TRANSMISSION_DELAY_SECONDS
        ):
            return "GPS_TRANSMISSION_DELAY"

        # Missing mock metadata does not establish
        # that the location was obtained normally.

        if row["is_mocked"] is not False:
            return "GPS_AUTHENTICITY_UNESTABLISHED"

        if not _bounded_number(
            row["accuracy_meters"],
            0,
            ARRIVAL_MAX_ACCURACY_METERS,
        ):
            return "GPS_ACCURACY_INSUFFICIENT"

        if not _bounded_number(
            row["speed_kmh"],
            0,
            ARRIVAL_MAX_SPEED_KMH,
        ):
            return "VEHICLE_NOT_STOPPED"

        if not _bounded_number(
            row["distance_meters"],
            0,
            ARRIVAL_RADIUS_METERS,
        ):
            return "OUTSIDE_DESTINATION"

        return None

    latest_error = invalid_reason(latest)

    if latest_error is not None:
        return TransportArrivalEvidence(
            False,
            latest_error,
            latest_distance,
        )

    count = 1

    previous_capture = latest_capture
    previous_receipt = latest_receipt

    capture_span = 0.0
    receipt_span = 0.0

    for row in rows[1:]:
        if invalid_reason(row) is not None:
            break

        captured = row["captured_at"]
        received = row["recorded_at"]

        capture_gap = (
            previous_capture - captured
        ).total_seconds()

        receipt_gap = (
            previous_receipt - received
        ).total_seconds()

        # Repeated native timestamps, simultaneous
        # receipts and out-of-order samples cannot
        # extend the consecutive evidence chain.

        if (
            capture_gap <= 0
            or receipt_gap <= 0
            or capture_gap >
                ARRIVAL_MAX_SAMPLE_GAP_SECONDS
            or receipt_gap >
                ARRIVAL_MAX_SAMPLE_GAP_SECONDS
        ):
            break

        count += 1

        previous_capture = captured
        previous_receipt = received

        capture_span = (
            latest_capture - captured
        ).total_seconds()

        receipt_span = (
            latest_receipt - received
        ).total_seconds()

        dwell = min(
            capture_span,
            receipt_span,
        )

        if (
            count >= ARRIVAL_MIN_SAMPLES
            and dwell >= ARRIVAL_MIN_DWELL_SECONDS
        ):
            return TransportArrivalEvidence(
                True,
                "ARRIVAL_ESTABLISHED",
                latest_distance,
                count,
                dwell,
            )

    dwell = min(
        capture_span,
        receipt_span,
    )

    return TransportArrivalEvidence(
        False,
        "INSUFFICIENT_DWELL",
        latest_distance,
        count,
        dwell,
    )
