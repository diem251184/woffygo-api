import os, sys, shutil, re

PATH = r"C:\woffy-mobile\android\app\build.gradle"

backup = PATH + ".variants2.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

activa = re.search(rb'^\s*debuggableVariants\s*=', src, re.MULTILINE)
if activa:
    print("[INFO] ya activo, skip")
    sys.exit(0)

anchor = b'bundleCommand = "export:embed"'
nl = b"\r\n" if b"\r\n" in src[:5000] else b"\n"
src = src.replace(anchor, anchor + nl + b'    debuggableVariants = []', 1)

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] debuggableVariants = [] agregado activo")