import os, sys
sys.path.insert(0, r"C:\woffygo")
from dotenv import load_dotenv
load_dotenv(r"C:\woffygo\.env")

from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Carlos user_id = 15
sql = text("""
    SELECT id, token, platform, is_active, created_at, updated_at
    FROM device_tokens
    WHERE user_id = 15
    ORDER BY updated_at DESC
""")

rows = db.execute(sql).all()
print(f"Total tokens de Carlos (user_id=15): {len(rows)}\n")
for r in rows:
    estado = "ACTIVO" if r.is_active else "INACTIVO"
    tok = r.token[:35] + "..." if len(r.token) > 35 else r.token
    print(f"id={r.id:3d} | {estado:8s} | {tok} | updated={r.updated_at}")

db.close()