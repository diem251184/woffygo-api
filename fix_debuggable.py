import os, sys, shutil, re

PATH = r"C:\woffy-mobile\android\app\build.gradle"

backup = PATH + ".debuggable.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

if b"debuggableVariants" in src:
    print("[SKIP] ya tiene debuggableVariants")
    sys.exit(0)

# Buscar el bloque react { ... } y agregar la linea antes del cierre
# Buscamos "bundleCommand = \"export:embed\"" que es la ultima propiedad conocida
anchor = b'bundleCommand = "export:embed"'
if anchor not in src:
    print("[FAIL] no encontre bundleCommand")
    sys.exit(1)

# Detectar el tipo de newline
nl = b"\r\n" if b"\r\n" in src[:5000] else b"\n"

# Insertar debuggableVariants = [] despues de bundleCommand
nuevo = anchor + nl + b'    debuggableVariants = []'
src = src.replace(anchor, nuevo, 1)

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] debuggableVariants = [] agregado")