import os, sys, shutil

PATH = r"C:\woffy-mobile\src\tasks\backgroundNotification.ts"

backup = PATH + ".payload.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

orig = src
nl = b"\r\n" if b"\r\n" in src[:5000] else b"\n"

viejo = b'  const payload = data?.notification?.data || {};'
nuevo = (
    b'  // Expo TaskManager entrega el data del payload directo.\n'.replace(b"\n", nl) +
    b'  // Puede venir como data.data (si viene envuelto en notification) o data directo.\n'.replace(b"\n", nl) +
    b'  const raw = (data as any) || {};\n'.replace(b"\n", nl) +
    b'  const payload = raw.notification?.data || raw.data || raw;'
)

if viejo not in src:
    print("[FAIL] no encontre la linea del payload")
    sys.exit(1)

src = src.replace(viejo, nuevo, 1)

# Tambien agregar un log para debug
viejo2 = b'  console.log("[notif-task] Notif local mostrada, canal:", channelId);'
nuevo2 = (
    b'  console.log("[notif-task] Payload recibido:", JSON.stringify(raw));\n'.replace(b"\n", nl) +
    b'  console.log("[notif-task] Title:", title, "| Body:", body);\n'.replace(b"\n", nl) +
    b'  console.log("[notif-task] Notif local mostrada, canal:", channelId);'
)
if viejo2 in src:
    src = src.replace(viejo2, nuevo2, 1)
    print("[OK] logs de debug agregados")

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] backgroundNotification.ts actualizado")