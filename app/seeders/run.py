"""Seeder principal de Woffy Go.

Uso:
    python -m app.seeders.run

Carga 1 admin, 2 dueÃ±os, 2 paseadores y 3 mascotas.
Todos los usuarios tienen la contraseÃ±a: test123
"""
from decimal import Decimal

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    Pet,
    User,
    UserRole,
    WalkerProfile,
    WalkLocation,
    Walk,
)


DEFAULT_PASSWORD = "test123"


def wipe_all(db) -> None:
    db.execute(delete(WalkLocation))
    db.execute(delete(Walk))
    db.execute(delete(Pet))
    db.execute(delete(WalkerProfile))
    db.execute(delete(User))
    db.commit()
    print("Datos anteriores eliminados.")


def seed_users(db) -> dict:
    users = {
        "admin": User(
            email="admin@woffygo.com",
            password_hash=hash_password(DEFAULT_PASSWORD),
            full_name="Admin WoffyGo",
            phone="+5491100000000",
            role=UserRole.ADMIN,
        ),
        "owner1": User(
            email="juan@example.com",
            password_hash=hash_password(DEFAULT_PASSWORD),
            full_name="Juan Perez",
            phone="+5491100000001",
            role=UserRole.OWNER,
        ),
        "owner2": User(
            email="maria@example.com",
            password_hash=hash_password(DEFAULT_PASSWORD),
            full_name="Maria Lopez",
            phone="+5491100000002",
            role=UserRole.OWNER,
        ),
        "walker1": User(
            email="carlos@example.com",
            password_hash=hash_password(DEFAULT_PASSWORD),
            full_name="Carlos Rodriguez",
            phone="+5491100000003",
            role=UserRole.WALKER,
        ),
        "walker2": User(
            email="lucia@example.com",
            password_hash=hash_password(DEFAULT_PASSWORD),
            full_name="Lucia Fernandez",
            phone="+5491100000004",
            role=UserRole.WALKER,
        ),
    }
    for u in users.values():
        db.add(u)
    db.flush()
    print(f"Usuarios creados: {len(users)}")
    return users


def seed_walker_profiles(db, users: dict) -> None:
    # Palermo: -58.4287, -34.5795
    # Recoleta: -58.3974, -34.5875
    profiles = [
        WalkerProfile(
            user_id=users["walker1"].id,
            bio="Amante de los perros. 5 aÃ±os de experiencia.",
            hourly_rate=Decimal("6000.00"),
            search_radius_km=5,
            is_online=True,
            current_location=WKTElement("POINT(-58.4287 -34.5795)", srid=4326),
            rating_avg=Decimal("4.80"),
            total_walks=120,
        ),
        WalkerProfile(
            user_id=users["walker2"].id,
            bio="Estudiante de veterinaria. Disponible fines de semana.",
            hourly_rate=Decimal("6500.00"),
            search_radius_km=8,
            is_online=False,
            current_location=WKTElement("POINT(-58.3974 -34.5875)", srid=4326),
            rating_avg=Decimal("4.95"),
            total_walks=340,
        ),
    ]
    for p in profiles:
        db.add(p)
    db.flush()
    print(f"Perfiles de paseador creados: {len(profiles)}")


def seed_pets(db, users: dict) -> None:
    pets = [
        Pet(
            owner_id=users["owner1"].id,
            name="Toby",
            breed="Golden Retriever",
            age_years=3,
            notes="Muy jugueton, tira de la correa.",
        ),
        Pet(
            owner_id=users["owner1"].id,
            name="Luna",
            breed="Beagle",
            age_years=5,
            notes="Tranquila, le gusta caminar despacio.",
        ),
        Pet(
            owner_id=users["owner2"].id,
            name="Rocky",
            breed="Bulldog Frances",
            age_years=2,
            notes="Alergico al pasto alto.",
        ),
    ]
    for p in pets:
        db.add(p)
    db.flush()
    print(f"Mascotas creadas: {len(pets)}")


def main() -> None:
    print("Iniciando seeder de Woffy Go...")
    db = SessionLocal()
    try:
        wipe_all(db)
        users = seed_users(db)
        seed_walker_profiles(db, users)
        seed_pets(db, users)
        db.commit()
        print("Seeder completado.")
        print("")
        print("Usuarios creados (password: test123):")
        print("  admin@woffygo.com    -> ADMIN")
        print("  juan@example.com     -> OWNER (Toby, Luna)")
        print("  maria@example.com    -> OWNER (Rocky)")
        print("  carlos@example.com   -> WALKER (online, Palermo)")
        print("  lucia@example.com    -> WALKER (offline, Recoleta)")
    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
