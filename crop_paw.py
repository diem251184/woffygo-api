import os
from PIL import Image

SRC = r"C:\woffy-mobile\assets\android-icon-monochrome.png"
DST = r"C:\woffy-mobile\assets\paw-marker.png"

img = Image.open(SRC).convert("RGBA")
print(f"Original: {img.width}x{img.height}")

# Obtener el bounding box del contenido (no transparente)
bbox = img.getbbox()
print(f"Bounding box del contenido: {bbox}")

# Recortar
cropped = img.crop(bbox)
print(f"Recortado: {cropped.width}x{cropped.height}")

# Guardar como PNG
cropped.save(DST, "PNG", optimize=True)
print(f"[DONE] Guardado: {DST}")

# Verificar
img2 = Image.open(DST)
print(f"Verificacion: {img2.width}x{img2.height}")