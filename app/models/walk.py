from app.models.booking import Booking, BookingPet, BookingStatus, ServiceType

# Alias de modelos
Walk = Booking
WalkPet = BookingPet

# Adaptador de enum para soportar tanto nombres viejos como nuevos
class WalkStatusCompat:
    PENDING = BookingStatus.REQUESTED
    REQUESTED = BookingStatus.REQUESTED
    ACCEPTED = BookingStatus.ACCEPTED
    IN_PROGRESS = BookingStatus.IN_PROGRESS
    COMPLETED = BookingStatus.COMPLETED
    CANCELLED = BookingStatus.CANCELLED
    REJECTED = BookingStatus.REJECTED

WalkStatus = WalkStatusCompat
