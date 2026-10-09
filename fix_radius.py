import os, sys, shutil

PATH = r"C:\woffygo\app\services\walks.py"

backup = PATH + ".radius.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

orig = src
nl = b"\r\n" if b"\r\n" in src[:5000] else b"\n"

# Reemplazar el 10000 hardcodeado por el radio del walker
viejo = b'''          AND ST_DWithin(
              wp.current_location,
              (SELECT pickup_location FROM walks WHERE id = :walk_id),
              10000
          )'''

nuevo = b'''          AND ST_DWithin(
              wp.current_location,
              (SELECT pickup_location FROM walks WHERE id = :walk_id),
              wp.search_radius_km * 1000
          )'''

if viejo not in src:
    print("[FAIL] no encontre el bloque ST_DWithin exacto")
    print("Buscando alternativas...")
    import re
    # Buscar cualquier ST_DWithin con 10000
    pat = re.compile(rb'10000')
    count = len(pat.findall(src))
    print(f"[INFO] apariciones de '10000': {count}")
    sys.exit(1)

src = src.replace(viejo, nuevo, 1)

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] Query ahora usa wp.search_radius_km * 1000")