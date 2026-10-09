import os, shutil

PATH = r"C:\woffygo\app\services\push.py"

backup = PATH + ".dataonly.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

# Nuevo _build_message: data-only
viejo = b'''def _build_message(token: str, title: str, body: str, data: dict | None = None) -> dict:
    msg = {
        "to": token,
        "title": title,
        "body": body,
        "priority": "high",
        "channelId": "walks-v5",
        "vibrate": [0, 250, 250, 250],
        "badge": 1,
    }
    if data:
        msg["data"] = data
    return msg'''

nuevo = b'''def _build_message(token: str, title: str, body: str, data: dict | None = None) -> dict:
    # Data-only push: el titulo/cuerpo y el channelId van dentro de data.
    # El cliente los reconstruye con TaskManager para forzar el canal walks-v5.
    msg = {
        "to": token,
        "priority": "high",
        "data": {
            "title": title,
            "body": body,
            "channelId": "walks-v5",
            "_contentAvailable": True,
        },
    }
    if data:
        msg["data"].update(data)
    return msg'''

if viejo not in src:
    print("[FAIL] No encontre la funcion _build_message exacta")
    import sys
    sys.exit(1)

src = src.replace(viejo, nuevo, 1)

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] push.py actualizado a data-only")