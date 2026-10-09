import os, shutil
from PIL import Image

PATH = r"C:\woffy-mobile\assets\android-icon-monochrome.png"

backup = PATH + ".gray.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

img = Image.open(PATH).convert("RGBA")
data = img.getdata()

# Regla: si el pixel tiene alpha > 0, forzar RGB a (255,255,255)
# Se preserva el alpha original (mantiene la anti-aliasing en los bordes)
new_data = []
for px in data:
    r, g, b, a = px
    if a > 0:
        new_data.append((255, 255, 255, a))
    else:
        new_data.append((255, 255, 255, 0))  # transparente puro

img.putdata(new_data)
img.save(PATH, "PNG", optimize=True)
print(f"[OK] Guardado: {PATH}")

# Verificacion
img2 = Image.open(PATH)
opacos = [px for px in img2.getdata() if px[3] > 128]
blancos = sum(1 for px in opacos if px[0] == 255 and px[1] == 255 and px[2] == 255)
print(f"[VERIFY] Opacos blancos: {blancos}/{len(opacos)}")
if blancos == len(opacos):
    print("🎉 Icono ahora es blanco puro")
else:
    print(f"⚠️ Quedan {len(opacos) - blancos} pixeles no-blancos")