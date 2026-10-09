import os, sys, shutil

PATH = r"C:\woffy-mobile\src\screens\WalkDetailScreen.tsx"

backup = PATH + ".tz.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

# Reemplazar la funcion formatDateTime completa
viejo = b'''function formatDateTime(iso: string | null): string {
  try {
    const d = new Date(iso);
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mn = String(d.getMinutes()).padStart(2, "0");
    return dd + "/" + mm + " " + hh + ":" + mn;
  } catch {
    return iso;
  }
}'''

nuevo = b'''function formatDateTime(iso: string | null): string {
  if (!iso) return "-";
  try {
    // Forzar timezone Argentina (UTC-3) sin depender del dispositivo
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

if viejo not in src:
    print("[FAIL] no encontre la funcion formatDateTime exacta")
    print("Buscando variantes...")
    # Ver como esta realmente
    import re
    m = re.search(rb'function formatDateTime\(iso: string \| null\): string \{.*?\n\}', src, re.DOTALL)
    if m:
        print("Encontrada esta variante:")
        print(m.group(0).decode('utf-8', errors='replace')[:500])
    sys.exit(1)

src = src.replace(viejo, nuevo, 1)

with open(PATH, "wb") as f:
    f.write(src)

print("[OK] formatDateTime actualizado a UTC-3 en WalkDetailScreen")