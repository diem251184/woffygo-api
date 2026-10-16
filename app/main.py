from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    admin,
    app_info,
    auth,
    bookings,
    messages,
    payments,
    pets,
    reviews,
    safety_reports,
    users,
    walker_verifications,
    walkers,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Woofy Go API",
    version="0.2.0",
    description="Backend de Woffy Go - Modelo unificado Booking",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(pets.router)
app.include_router(walkers.router)
app.include_router(bookings.router)
app.include_router(messages.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(reviews.router)
app.include_router(safety_reports.router)
app.include_router(app_info.router)
app.include_router(walker_verifications.router)


@app.api_route("/health", methods=["GET", "HEAD"], tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": "woffygo-api", "version": "0.2.0"}
