import os, shutil

PATH = r"C:\woffy-mobile\src\tasks\backgroundNotification.ts"
backup = PATH + ".fastrefresh.bak"

if os.path.exists(backup):
    shutil.copyfile(backup, PATH)
    os.remove(backup)
    print("[OK] Archivo restaurado")
else:
    print("[SKIP] No habia backup")