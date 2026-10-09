import os, sys, shutil, re

# Archivos a modificar
FILES = [
    (r"C:\woffy-mobile\src\contexts\NotificationContext.tsx", "walks-v5", "walks-v6"),
    (r"C:\woffy-mobile\src\tasks\backgroundNotification.ts", "walks-v5", "walks-v6"),
]

for path, viejo, nuevo in FILES:
    if not os.path.exists(path):
        print(f"[FAIL] no existe {path}")
        continue

    backup = path + ".v6.bak"
    if not os.path.exists(backup):
        shutil.copyfile(path, backup)
        print(f"[BACKUP] {backup}")

    with open(path, "rb") as f:
        src = f.read()

    count = src.count(viejo.encode())
    if count == 0:
        print(f"[SKIP] {path} no tiene {viejo}")
        continue

    src = src.replace(viejo.encode(), nuevo.encode())
    with open(path, "wb") as f:
        f.write(src)

    print(f"[OK] {count} reemplazos en {os.path.basename(path)}")

print("[DONE] Canal actualizado a walks-v6")