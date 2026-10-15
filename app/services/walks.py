from app.services.bookings import (
    create_booking as create_walk,
    accept_booking as accept_walk,
    start_booking as start_walk,
    finish_booking as finish_walk,
    cancel_booking as cancel_walk,
    get_booking_or_404 as _get_walk_or_404,
)
from app.models.booking import Booking, BookingStatus

def list_walks_for_user(db, user, status_filter=None):
    from app.services.bookings import list_mine
    # consulta basica
    query = db.query(Booking)
    if user.role.value == "owner":
        query = query.filter(Booking.owner_id == user.id)
    elif user.role.value == "walker":
        query = query.filter(Booking.provider_id == user.id)
    if status_filter:
        query = query.filter(Booking.status == status_filter)
    return query.order_by(Booking.created_at.desc()).all()

def list_available_walks(db):
    return (
        db.query(Booking)
        .filter(Booking.status == BookingStatus.REQUESTED)
        .filter(Booking.provider_id.is_(None))
        .all()
    )

def get_latest_walk_location(db, walk_id, user):
    return None

def list_walk_locations(db, walk_id, user, limit=500):
    return []
