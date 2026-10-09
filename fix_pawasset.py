import os, sys, shutil

PATH = r"C:\woffy-mobile\src\screens\WalkDetailScreen.tsx"

backup = PATH + ".pawasset.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

# Cambiar el require por el nuevo asset
viejo = b'require("../../assets/android-icon-monochrome.png")'
nuevo = b'require("../../assets/paw-marker.png")'

count = src.count(viejo)
if count == 0:
    print("[SKIP] no habia require del icon-monochrome")
    sys.exit(0)

src = src.replace(viejo, nuevo)
print(f"[OK] {count} require(s) cambiado(s) a paw-marker.png")

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] Referencia del asset actualizada")