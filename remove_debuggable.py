import os, sys, shutil

PATH = r"C:\woffy-mobile\android\app\build.gradle"

backup = PATH + ".no-debuggable.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

if b"debuggableVariants = []" not in src:
    print("[SKIP] no hay linea activa")
    sys.exit(0)

if b"// debuggableVariants = []" in src:
    print("[SKIP] ya esta comentada")
    sys.exit(0)

# Comentar la linea (agregar // al principio)
src = src.replace(
    b"    debuggableVariants = []",
    b"    // debuggableVariants = []  // reactivar para testear headless task",
    1
)

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] debuggableVariants = [] comentada")