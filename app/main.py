from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.database import engine
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
    walker_verifications,
    walkers,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
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

            conn.execute(text("""
                DO $$ BEGIN
                    CREATE TYPE service_type_enum AS ENUM ('WALK', 'TRANSPORT', 'DAYCARE');
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """))

            conn.execute(text("""
                DO $$ BEGIN
                    CREATE TYPE booking_status_enum AS ENUM ('REQUESTED', 'ACCEPTED', 'REJECTED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED');
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """))

            table_check = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'walks');"
            )).scalar()

            if table_check:
                conn.execute(text("ALTER TABLE walks RENAME TO bookings;"))
                conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS service_type service_type_enum NOT NULL DEFAULT 'WALK';"))
                conn.execute(text("DO $$ BEGIN ALTER TABLE bookings RENAME COLUMN walker_id TO provider_id; EXCEPTION WHEN undefined_column THEN null; END $$;"))
                conn.execute(text("DO $$ BEGIN ALTER TABLE bookings RENAME COLUMN walker_earnings TO provider_earnings; EXCEPTION WHEN undefined_column THEN null; END $$;"))
                
                walk_pets_check = conn.execute(text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'walk_pets');"
                )).scalar()
                if walk_pets_check:
                    conn.execute(text("ALTER TABLE walk_pets RENAME TO booking_pets;"))
                    conn.execute(text("DO $$ BEGIN ALTER TABLE booking_pets RENAME COLUMN walk_id TO booking_id; EXCEPTION WHEN undefined_column THEN null; END $$;"))

                conn.execute(text("DO $$ BEGIN ALTER TABLE payments RENAME COLUMN walk_id TO booking_id; EXCEPTION WHEN undefined_column THEN null; END $$;"))

            # Columnas requeridas en bookings
            booking_cols = [
                "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS cancellation_reason VARCHAR(255);",
                "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS cancelled_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL;",
                "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS notes TEXT;",
                "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS duration_minutes INTEGER DEFAULT 60;",
                "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS price_total NUMERIC(10, 2) DEFAULT 0;",
                "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS platform_fee NUMERIC(10, 2) DEFAULT 0;",
                "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS provider_earnings NUMERIC(10, 2) DEFAULT 0;",
            ]
            for col in booking_cols:
                conn.execute(text(col))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS provider_services (
                    id SERIAL PRIMARY KEY,
                    provider_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    service_type service_type_enum NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT true,
                    base_price NUMERIC(10, 2) NOT NULL DEFAULT 0,
                    price_per_km NUMERIC(10, 2) NOT NULL DEFAULT 0,
                    price_per_day NUMERIC(10, 2) NOT NULL DEFAULT 0,
                    service_radius_km INTEGER NOT NULL DEFAULT 3,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
                );
            """))
            conn.commit()
    except Exception as e:
        print(f"[startup] Error inicializando esquema: {e}")
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
app.include_router(pets.router)
app.include_router(walkers.router)

app.include_router(bookings.router)
app.include_router(bookings.router, prefix="/walks", tags=["walks-compat"])

app.include_router(messages.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(reviews.router)
app.include_router(safety_reports.router)
app.include_router(app_info.router)
app.include_router(walker_verifications.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": "woffygo-api", "version": "0.2.0"}
