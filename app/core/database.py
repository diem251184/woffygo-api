import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings


# Permitir override de la URL por variable de entorno.
# - Si NEON_DATABASE_URL esta seteada, se usa (para Neon / produccion).
# - Si no, se usa settings.DATABASE_URL (base local del .env).
_database_url = os.environ.get("NEON_DATABASE_URL") or settings.DATABASE_URL

engine = create_engine(
    _database_url,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()