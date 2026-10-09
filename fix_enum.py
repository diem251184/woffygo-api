import os
from sqlalchemy import create_engine, text

with open(r"C:\woffygo\.neon_url.tmp", "r") as f:
    neon_url = f.read().strip()

engine = create_engine(neon_url, pool_pre_ping=True)
with engine.begin() as conn:
    # 1) Ver los valores actuales del enum
    print("===== VALORES ACTUALES DEL ENUM payment_status =====")
    rows = conn.execute(text("""
        SELECT enumlabel
        FROM pg_enum
        JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
        WHERE pg_type.typname = 'payment_status'
        ORDER BY pg_enum.enumsortorder
    """)).fetchall()
    for r in rows:
        print(f"  - {r.enumlabel}")

    valores_actuales = {r.enumlabel for r in rows}

    # 2) Definir los valores que DEBEN estar
    valores_esperados = {
        "pendiente", "aprobado", "rechazado", "reembolsado",
        "cancelado", "liberado", "en_disputa"
    }

    faltantes = valores_esperados - valores_actuales
    print(f"\n===== VALORES FALTANTES =====")
    if not faltantes:
        print("  (ninguno)")
    else:
        for v in faltantes:
            print(f"  - {v}")

    # 3) Agregar los faltantes
    for valor in faltantes:
        print(f"\n[AÑADIENDO] {valor} ...")
        conn.execute(text(f"ALTER TYPE payment_status ADD VALUE IF NOT EXISTS '{valor}'"))
        print(f"  ✅ OK")

    # 4) Verificar
    print("\n===== VALORES DESPUES =====")
    rows = conn.execute(text("""
        SELECT enumlabel
        FROM pg_enum
        JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
        WHERE pg_type.typname = 'payment_status'
        ORDER BY pg_enum.enumsortorder
    """)).fetchall()
    for r in rows:
        print(f"  - {r.enumlabel}")

print("\n[DONE] Enum actualizado")