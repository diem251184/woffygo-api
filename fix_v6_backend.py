import os, sys, shutil

PATH = r"C:\woffygo\app\services\push.py"

backup = PATH + ".v6.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

count = src.count(b"walks-v5")
if count == 0:
    print("[SKIP] no hay walks-v5 en push.py")
    sys.exit(0)

src = src.replace(b"walks-v5", b"walks-v6")
with open(PATH, "wb") as f:
    f.write(src)

print(f"[DONE] {count} reemplazos walks-v5 -> walks-v6")