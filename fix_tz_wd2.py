import os, sys, shutil, re

PATH = r"C:\woffy-mobile\src\screens\WalkDetailScreen.tsx"

backup = PATH + ".tz2.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

# Usar regex para reemplazar la funcion completa sin importar la indentacion exacta
pattern = rb'function formatDateTime\(iso: string \| null\): string \{.*?\n  \}'

m = re.search(pattern, src, re.DOTALL)
if not m:
    print("[FAIL] no encontre la funcion")
    sys.exit(1)

viejo = m.group(0)
print("[INFO] Funcion original (primeras lineas):")
print(viejo[:150].decode('utf-8', errors='replace'))

nuevo = b'''function formatDateTime(iso: string | null): string {
    if (!iso) return "-";
    try {
      const d = new Date(iso);
      const argMs = d.getTime() - 3 * 60 * 60 * 1000;
      const arg = new Date(argMs);
      const dd = String(arg.getUTCDate()).padStart(2, "0");
      const mm = String(arg.getUTCMonth() + 1).padStart(2, "0");
      const yy = arg.getUTCFullYear();
      const hh = String(arg.getUTCHours()).padStart(2, "0");
      const mn = String(arg.getUTCMinutes()).padStart(2, "0");
      return dd + "/" + mm + "/" + yy + " " + hh + ":" + mn;
    } catch {
      return iso;
    }
  }'''

src = src.replace(viejo, nuevo, 1)

with open(PATH, "wb") as f:
    f.write(src)

print("[OK] formatDateTime actualizado a UTC-3 en WalkDetailScreen")