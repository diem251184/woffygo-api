from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.database import engine
from app.routers import (
    admin,
    app_info,
    auth,
    messages,
    pets,
    reviews,
    walkers,
    walks,
    payments,
    safety_reports,
    walker_verifications,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Asegurar que las columnas existan en la BD conectada (Neon / Producción)
    try:
        with engine.connect() as conn:
            queries = [
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS dni_number VARCHAR(30);",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS address VARCHAR(255);",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS birth_date DATE;",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS emergency_contact VARCHAR(150);",
            ]
            for q in queries:
                conn.execute(text(q))
            conn.commit()
            print("[startup] Columnas de perfil verificadas en base de datos.")
    except Exception as e:
        print(f"[startup] Error verificando columnas: {e}")
    yield


app = FastAPI(
    title="Woofy Go API",
    version="0.1.0",
    description="Backend de Woffy Go - paseo de perros en tiempo real",
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
app.include_router(pets.router)
app.include_router(walkers.router)
app.include_router(walks.router)
app.include_router(messages.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(reviews.router)
app.include_router(safety_reports.router)
app.include_router(app_info.router)
app.include_router(walker_verifications.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": "woffygo-api"}
