import os, sys, shutil

PATH = r"C:\woffy-mobile\src\screens\WalkDetailScreen.tsx"

backup = PATH + ".pawbig.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

orig = src

# Agrandar circulos de 36 a 44, paw de 20 a 28
src = src.replace(b"      width: 36,\n      height: 36,\n      borderRadius: 18,",
                  b"      width: 44,\n      height: 44,\n      borderRadius: 22,")
src = src.replace(b"      width: 36,\r\n      height: 36,\r\n      borderRadius: 18,",
                  b"      width: 44,\r\n      height: 44,\r\n      borderRadius: 22,")

src = src.replace(b"markerPawImage: { width: 20, height: 20 },",
                  b"markerPawImage: { width: 30, height: 30 },")

if src == orig:
    print("[WARN] no hubo cambios")
    sys.exit(1)

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] Marcadores agrandados (44px circulo, 30px paw)")