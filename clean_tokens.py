import os, sys
sys.path.insert(0, r"C:\woffygo")
from dotenv import load_dotenv
load_dotenv(r"C:\woffygo\.env")

# Leer URL de Neon desde archivo temporal
with open(r"C:\woffygo\.neon_url.tmp", "r") as f:
    neon_url = f.read().strip()

# Override la URL de la DB
os.environ["NEON_DATABASE_URL"] = neon_url

# Ahora importar y crear sesion (va a usar NEON_DATABASE_URL)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

engine = create_engine(neon_url, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# Ver tokens de Carlos
sql = text("""
    SELECT id, token, platform, is_active, created_at, updated_at
    FROM device_tokens
    WHERE user_id = 15
    ORDER BY updated_at DESC
""")
rows = db.execute(sql).all()
print(f"Total tokens de Carlos (user_id=15): {len(rows)}\n")
for r in rows:
    estado = "ACTIVO  " if r.is_active else "inactivo"
    tok = r.token[:45] + "..." if len(r.token) > 45 else r.token
    print(f"id={r.id:3d} | {estado} | {tok} | upd={r.updated_at}")

# Marcar todos menos el mas reciente como inactivos
if len(rows) > 1:
    ultimo_id = rows[0].id
    print(f"\nManteniendo activo solo id={ultimo_id}, desactivando el resto...")
    db.execute(
        text("UPDATE device_tokens SET is_active = false WHERE user_id = 15 AND id != :ultimo"),
        {"ultimo": ultimo_id}
    )
    db.commit()
    print("[OK] Tokens viejos desactivados")
else:
    print("\n[SKIP] Ya hay uno solo o ninguno")

# Verificar
rows2 = db.execute(sql).all()
print(f"\nEstado final:")
for r in rows2:
    estado = "ACTIVO  " if r.is_active else "inactivo"
    print(f"id={r.id:3d} | {estado} | {r.token[:45]}...")

db.close()