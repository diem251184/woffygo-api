import os, sys, shutil

PATH = r"C:\woffygo\app\schemas\walker.py"

backup = PATH + ".radius.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

orig = src

# Cambiar le=50 por le=5 en las 3 apariciones
count = src.count(b"le=50")
if count == 0:
    print("[FAIL] no encontre 'le=50'")
    sys.exit(1)

src = src.replace(b"le=50", b"le=5")

with open(PATH, "wb") as f:
    f.write(src)

print(f"[DONE] {count} ocurrencias de le=50 -> le=5")