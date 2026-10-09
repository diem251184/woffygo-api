import json, shutil, os

PATH = r"C:\woffy-mobile\app.json"

backup = PATH + ".icon.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

# Buscar el plugin de expo-notifications y cambiar el icon
plugins = data["expo"]["plugins"]
changed = False
for p in plugins:
    if isinstance(p, list) and p[0] == "expo-notifications":
        p[1]["icon"] = "./assets/android-icon-monochrome.png"
        changed = True
        print(f"[OK] icon cambiado a android-icon-monochrome.png")
        break

if not changed:
    print("[FAIL] no encontre el plugin expo-notifications")
    import sys
    sys.exit(1)

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")

print("[DONE] app.json actualizado")