import os, sys, shutil

PATH = r"C:\woffy-mobile\src\tasks\backgroundNotification.ts"

backup = PATH + ".fixparse.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

if b"data: payload," not in src:
    print("[SKIP] ya fue corregido")
    sys.exit(0)

src = src.replace(b"data: payload,", b"data: parsed,", 1)

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] data: payload -> data: parsed")