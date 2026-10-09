import os
from PIL import Image

SRC = r"C:\woffy-mobile\assets\android-icon-monochrome.png"
RES_DIR = r"C:\woffy-mobile\android\app\src\main\res"

SIZES = {
    "drawable-mdpi": 24,
    "drawable-hdpi": 36,
    "drawable-xhdpi": 48,
    "drawable-xxhdpi": 72,
    "drawable-xxxhdpi": 96,
    "drawable": 96,
}

img = Image.open(SRC)
print(f"Origen: {img.width}x{img.height} px, modo {img.mode}")

for folder, size in SIZES.items():
    dst_dir = os.path.join(RES_DIR, folder)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, "notification_icon.png")
    resized = img.resize((size, size), Image.LANCZOS)
    resized.save(dst, "PNG", optimize=True)
    print(f"[OK] {folder}/notification_icon.png ({size}x{size})")

print("[DONE] Iconos generados en todas las densidades")