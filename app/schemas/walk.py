from app.schemas.booking import (
    BookingResponse as WalkResponse,
    BookingCreate as WalkCreate,
    BookingLocationCreate as WalkLocationCreate,
    BookingLocationDetail as WalkLocationDetail,
    BookingStatusUpdateRequest as WalkCancelRequest,
)

class WalkLocationResponse(WalkLocationCreate):
    pass
