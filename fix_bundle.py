import os, sys, shutil

PATH = r"C:\woffy-mobile\android\app\build.gradle"

backup = PATH + ".bundle.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

if b"project.ext.react" in src:
    print("[SKIP] ya tiene project.ext.react")
    sys.exit(0)

# Insertar el bloque project.ext.react justo despues de la primera linea del archivo
# Buscar la primera aparicion de "apply plugin" o similar para insertar antes
nuevo = b'''
// Forzar bundle JS embebido en debug para que el headless lo use
project.ext.react = [
    bundleInDebug: true,
    bundleInRelease: true,
    devDisabledInDebug: false,
    enableHermes: true,
]

'''

# Insertar al principio del archivo
src = nuevo + src

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] project.ext.react agregado al build.gradle")