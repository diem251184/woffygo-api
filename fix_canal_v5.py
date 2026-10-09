import io, os, sys, shutil

ARCHIVOS = [
    r"C:\woffy-mobile\src\contexts\NotificationContext.tsx",
    r"C:\woffygo\app\services\push.py",
]

VIEJO = b"walks-v4"
NUEVO = b"walks-v5"

for path in ARCHIVOS:
    if not os.path.exists(path):
        print("[FAIL] no existe: " + path)
        sys.exit(1)

    backup = path + ".channel.bak"
    if not os.path.exists(backup):
        shutil.copyfile(path, backup)
        print("[BACKUP] " + backup)

    with open(path, "rb") as f:
        src = f.read()

    if VIEJO not in src:
        print("[SKIP] sin cambios: " + path)
        continue

    count = src.count(VIEJO)
    src = src.replace(VIEJO, NUEVO)

    with open(path, "wb") as f:
        f.write(src)

    print("[OK] " + str(count) + " reemplazo(s) en " + path)

print("[DONE] Canal actualizado a walks-v5")