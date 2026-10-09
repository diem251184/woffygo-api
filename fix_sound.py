import os, shutil

PATH = r"C:\woffygo\app\services\push.py"

backup = PATH + ".sound.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

# Quitar la linea de "sound": "notification.wav",
viejo = b'        "sound": "notification.wav",\r\n'
viejo2 = b'        "sound": "notification.wav",\n'
nuevo = b''

if viejo in src:
    src = src.replace(viejo, nuevo, 1)
    print("[OK] sound quitado (CRLF)")
elif viejo2 in src:
    src = src.replace(viejo2, nuevo, 1)
    print("[OK] sound quitado (LF)")
else:
    print("[WARN] no encontre la linea del sound")
    import sys
    sys.exit(1)

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] push.py actualizado (sound removido, canal gobierna el sonido)")