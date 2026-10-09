import os, sys, shutil

PATH = r"C:\woffy-mobile\src\screens\AdminUsersScreen.tsx"

backup = PATH + ".fixname.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

# Leer como UTF-8, no como bytes (para trabajar con strings reales)
with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# Ver qué hay ahora
import re
m = re.search(r'owner:\s*"([^"]*)"', src)
if m:
    print(f"[INFO] Valor actual de owner: '{m.group(1)}'")

# Reemplazar todas las variantes posibles por la palabra correcta
reemplazos = [
    ('"DUE\\xc3\\x91O"', '"DUEÑO"'),  # literal backslash-x-c3
    ('"DUEÃ‘O"', '"DUEÑO"'),           # mojibake clásico
    ('"DUEÃ\x91O"', '"DUEÑO"'),
]

original = src
for viejo, nuevo in reemplazos:
    if viejo in src:
        src = src.replace(viejo, nuevo)
        print(f"[OK] Reemplazado: '{viejo}' -> '{nuevo}'")

if src == original:
    print("[WARN] No hubo cambios. Ver contenido actual.")

with open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

# Verificación
with open(PATH, "r", encoding="utf-8") as f:
    check = f.read()
m2 = re.search(r'owner:\s*"([^"]*)"', check)
if m2:
    print(f"[VERIFY] Valor nuevo de owner: '{m2.group(1)}'")
    if m2.group(1) == "DUEÑO":
        print("🎉 Quedo bien!")