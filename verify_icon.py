import sys, os
try:
    from PIL import Image
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "--quiet"])
    from PIL import Image

PATH = r"C:\woffy-mobile\assets\android-icon-monochrome.png"

if not os.path.exists(PATH):
    print(f"[FAIL] No existe: {PATH}")
    sys.exit(1)

print(f"Archivo:      {PATH}")
print(f"Tamaño:       {os.path.getsize(PATH)} bytes")
print(f"Modificado:   {os.path.getmtime(PATH)}")

img = Image.open(PATH)
print(f"\nFormato:      {img.format}")
print(f"Modo:         {img.mode}")
print(f"Dimensiones:  {img.width} x {img.height} px")

if img.mode != "RGBA":
    print("\n❌ PROBLEMA: NO tiene canal alpha (transparencia)")
    print("   En Canva, tenés que marcar 'Fondo transparente' al descargar.")
    sys.exit(1)

# Analizar alpha
alpha = img.split()[-1]
data = list(alpha.getdata())
total = len(data)
transp = sum(1 for p in data if p < 50)
opaco = sum(1 for p in data if p > 200)

print(f"\nAnálisis de transparencia:")
print(f"  Pixeles transparentes: {transp} ({100*transp/total:.1f}%)")
print(f"  Pixeles opacos:        {opaco} ({100*opaco/total:.1f}%)")

if transp < total * 0.3:
    print("\n⚠️  Advertencia: menos del 30% es transparente.")
    print("   Puede que el fondo no sea realmente transparente.")
elif transp > total * 0.95:
    print("\n⚠️  Advertencia: más del 95% es transparente.")
    print("   Puede que el paw sea muy chico o que no se guardó bien.")

# Verificar color de los pixeles opacos
data_all = list(img.getdata())
opacos_rgb = [px[:3] for px in data_all if px[3] > 128]
if opacos_rgb:
    blancos = sum(1 for px in opacos_rgb if px[0] > 230 and px[1] > 230 and px[2] > 230)
    print(f"\nColor de pixeles opacos:")
    print(f"  Blancos (>230,>230,>230): {blancos} de {len(opacos_rgb)} ({100*blancos/len(opacos_rgb):.1f}%)")
    if blancos < len(opacos_rgb) * 0.9:
        print("  ⚠️  No es blanco puro. Android lo va a aplanar.")
        print(f"  Muestra: {opacos_rgb[:3]}")
    else:
        print("  ✅ Blanco puro, perfecto")

print("\n===== RESUMEN =====")
problemas = []
if img.width != 96 or img.height != 96:
    problemas.append(f"❌ Tamaño es {img.width}x{img.height}, se esperaba 96x96")
else:
    print("✅ Tamaño correcto: 96x96")
if transp < total * 0.3:
    problemas.append("❌ Falta transparencia de fondo")
else:
    print("✅ Fondo transparente OK")
if opacos_rgb and blancos < len(opacos_rgb) * 0.9:
    problemas.append("❌ El paw no es blanco puro")
else:
    print("✅ Paw blanco puro OK")

if problemas:
    print("\nPROBLEMAS A CORREGIR:")
    for p in problemas:
        print("  " + p)
else:
    print("\n🎉 ¡ICONO PERFECTO! Listo para usar.")