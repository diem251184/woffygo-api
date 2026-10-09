import sys

try:
    from PIL import Image
except ImportError:
    print("[INFO] Instalando Pillow...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image

PATH = r"C:\woffy-mobile\android\app\src\main\res\drawable\notification_icon.png"

img = Image.open(PATH)
print(f"Formato:      {img.format}")
print(f"Modo:         {img.mode}")  # RGBA = tiene alpha, RGB = no tiene alpha
print(f"Dimensiones:  {img.width} x {img.height} px")

if img.mode != "RGBA":
    print("[WARNING] NO tiene canal alpha -> Android lo va a aplanar a cuadrado")
else:
    # Analizar alpha
    alpha = img.split()[-1]
    pixels = list(alpha.getdata())
    transparent = sum(1 for p in pixels if p == 0)
    opaque = sum(1 for p in pixels if p == 255)
    semi = len(pixels) - transparent - opaque
    total = len(pixels)
    print(f"Alpha - Transparentes: {transparent} ({100*transparent/total:.1f}%)")
    print(f"Alpha - Opacos:        {opaque} ({100*opaque/total:.1f}%)")
    print(f"Alpha - Semitransp:    {semi} ({100*semi/total:.1f}%)")

    # Analizar color de los pixeles opacos
    if img.mode == "RGBA":
        # Separar en RGBA
        r, g, b, a = img.split()
        # Contar pixeles blancos vs coloreados
        img_rgb = img.convert("RGBA")
        data = list(img_rgb.getdata())
        opacos = [px for px in data if px[3] > 128]
        if opacos:
            blancos = sum(1 for px in opacos if px[0] > 230 and px[1] > 230 and px[2] > 230)
            print(f"Pixeles opacos blancos: {blancos} de {len(opacos)} ({100*blancos/len(opacos):.1f}%)")
            # Mostrar algunos pixeles de muestra
            print(f"Primeros 5 pixeles opacos: {opacos[:5]}")
