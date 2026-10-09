import os, shutil, re

FILES = [
    (r"C:\woffy-mobile\src\screens\MyWalksScreen.tsx", "formatDate"),
    (r"C:\woffy-mobile\src\screens\FlaggedWalksScreen.tsx", "formatDate"),
]

for PATH, fname in FILES:
    if not os.path.exists(PATH):
        print(f"[SKIP] no existe {PATH}")
        continue

    backup = PATH + ".tz.bak"
    if not os.path.exists(backup):
        shutil.copyfile(PATH, backup)

    with open(PATH, "rb") as f:
        src = f.read()

    # Buscar y reemplazar la funcion usando regex
    pattern = rb'function ' + fname.encode() + rb'\(iso: string \| null\): string \{.*?\n\}'
    m = re.search(pattern, src, re.DOTALL)
    if not m:
        print(f"[SKIP] no encontre {fname} en {os.path.basename(PATH)}")
        continue

    viejo = m.group(0)
    nuevo = (
        b'function ' + fname.encode() + b'(iso: string | null): string {\n'
        b'  if (!iso) return "-";\n'
        b'  try {\n'
        b'    const d = new Date(iso);\n'
        b'    const argMs = d.getTime() - 3 * 60 * 60 * 1000;\n'
        b'    const arg = new Date(argMs);\n'
        b'    const dd = String(arg.getUTCDate()).padStart(2, "0");\n'
        b'    const mm = String(arg.getUTCMonth() + 1).padStart(2, "0");\n'
        b'    const yy = arg.getUTCFullYear();\n'
        b'    const hh = String(arg.getUTCHours()).padStart(2, "0");\n'
        b'    const mn = String(arg.getUTCMinutes()).padStart(2, "0");\n'
        b'    return dd + "/" + mm + " " + hh + ":" + mn;\n'
        b'  } catch {\n'
        b'    return iso;\n'
        b'  }\n'
        b'}'
    )

    src = src.replace(viejo, nuevo, 1)

    with open(PATH, "wb") as f:
        f.write(src)

    print(f"[OK] {os.path.basename(PATH)} actualizado")