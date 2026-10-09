import os, sys
sys.path.insert(0, r"C:\woffygo")
from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
sql = text("""
    SELECT wp.user_id, u.email, wp.is_online,
           wp.current_location IS NULL AS loc_es_null,
           ST_Y(CAST(wp.current_location AS geometry)) AS lat,
           ST_X(CAST(wp.current_location AS geometry)) AS lon,
           wp.last_location_update
    FROM walker_profiles wp
    JOIN users u ON u.id = wp.user_id
    WHERE u.email = 'carlos@example.com'
""")
row = db.execute(sql).first()
if row:
    print(f"user_id:            {row.user_id}")
    print(f"email:              {row.email}")
    print(f"is_online:          {row.is_online}")
    print(f"loc_es_null:        {row.loc_es_null}")
    print(f"lat:                {row.lat}")
    print(f"lon:                {row.lon}")
    print(f"last_location_upd:  {row.last_location_update}")
else:
    print("No se encontro a Carlos")
db.close()