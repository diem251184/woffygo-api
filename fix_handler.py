import os, sys, shutil

PATH = r"C:\woffy-mobile\src\screens\WalkDetailScreen.tsx"

backup = PATH + ".handlerfix.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# Cambiar como se obtienen las coords
viejo = '''      let lat = safetyCoords?.latitude;
      let lng = safetyCoords?.longitude;
      if (!lat || !lng) {
        await refreshSafetyCoords();
        lat = safetyCoords?.latitude;
        lng = safetyCoords?.longitude;
      }
      if (!lat || !lng) {'''

nuevo = '''      let lat = safetyCoords?.latitude;
      let lng = safetyCoords?.longitude;
      if (!lat || !lng) {
        const fresh = await refreshSafetyCoords();
        lat = fresh?.latitude;
        lng = fresh?.longitude;
      }
      if (!lat || !lng) {'''

if viejo not in src:
    print("[FAIL] no encontre el bloque del handler")
    sys.exit(1)

src = src.replace(viejo, nuevo, 1)

# Fix de tildes
reemplazos = [
    ('"Falta categoria", "Elegi un tipo de reporte"', '"Falta categoría", "Elegí un tipo de reporte"'),
    ('"Sin ubicacion", "No pudimos obtener tu ubicacion. Activa el GPS."', '"Sin ubicación", "No pudimos obtener tu ubicación. Activá el GPS."'),
    ('"Reporte enviado", "Gracias, tu reporte ya esta visible en el mapa"', '"Reporte enviado", "Gracias, tu reporte ya está visible en el mapa"'),
    ('placeholder="Contanos mas (opcional)"', 'placeholder="Contanos más (opcional)"'),
]
for viejo_t, nuevo_t in reemplazos:
    if viejo_t in src:
        src = src.replace(viejo_t, nuevo_t)
        print(f"[OK] Tilde arreglada: {nuevo_t[:40]}...")

with open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(src)
print("[DONE] WalkDetailScreen actualizado")