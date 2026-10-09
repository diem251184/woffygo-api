import os, sys, shutil

PATH = r"C:\woffy-mobile\src\tasks\backgroundNotification.ts"

backup = PATH + ".parse.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

orig = src
nl = b"\r\n" if b"\r\n" in src[:5000] else b"\n"

viejo = b'''  // Expo TaskManager entrega el data del payload directo.
  // Puede venir como data.data (si viene envuelto en notification) o data directo.
  const raw = (data as any) || {};
  const payload = raw.notification?.data || raw.data || raw;
  const title = payload.title || "Woofy Go";
  const body = payload.body || "";
  const channelId = payload.channelId || "walks-v5";'''

nuevo = b'''  // Expo TaskManager entrega el data del payload directo.
  // El backend manda los campos reales dentro de data.body como string JSON.
  const raw = (data as any) || {};
  const outer = raw.notification?.data || raw.data || raw;

  // Caso 1: data.body es un string JSON con {title, body, channelId, ...}
  // Caso 2: los campos estan directos en outer
  let parsed: any = outer;
  if (outer && typeof outer.body === "string" && outer.body.trim().startsWith("{")) {
    try {
      parsed = JSON.parse(outer.body);
    } catch (e) {
      console.warn("[notif-task] No pude parsear outer.body como JSON:", e);
      parsed = outer;
    }
  }

  const title = parsed.title || "Woofy Go";
  const body = parsed.body || "";
  const channelId = parsed.channelId || "walks-v5";'''

if viejo not in src:
    print("[FAIL] no encontre el bloque del payload")
    sys.exit(1)

src = src.replace(viejo, nuevo, 1)

# Tambien actualizar el log de debug para mostrar parsed
viejo2 = b'  console.log("[notif-task] Payload recibido:", JSON.stringify(raw));'
nuevo2 = b'  console.log("[notif-task] Parsed:", JSON.stringify(parsed));'
if viejo2 in src:
    src = src.replace(viejo2, nuevo2, 1)

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] backgroundNotification.ts actualizado con parse de JSON")