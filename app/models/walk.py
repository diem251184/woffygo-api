from app.models.booking import Booking, BookingPet, BookingStatus, ServiceType

# Herencia directa para que SQLAlchemy registre 'Walk' en su Class Registry
class Walk(Booking):
    __tablename__ = None
    __table__ = Booking.__table__

class WalkPet(BookingPet):
    __tablename__ = None
    __table__ = BookingPet.__table__

class WalkStatusCompat:
    PENDING = BookingStatus.REQUESTED
    REQUESTED = BookingStatus.REQUESTED
    ACCEPTED = BookingStatus.ACCEPTED
    IN_PROGRESS = BookingStatus.IN_PROGRESS
    COMPLETED = BookingStatus.COMPLETED
    CANCELLED = BookingStatus.CANCELLED
    REJECTED = BookingStatus.REJECTED

WalkStatus = WalkStatusCompat
