import os, sys, shutil

MOBILE = r"C:\woffy-mobile"
TASK_PATH = os.path.join(MOBILE, "src", "tasks", "backgroundNotification.ts")
INDEX_PATH = os.path.join(MOBILE, "index.ts")

# --- 1) Crear archivo del task ---
os.makedirs(os.path.dirname(TASK_PATH), exist_ok=True)

TASK_CONTENT = b'''import * as Notifications from "expo-notifications";
import * as TaskManager from "expo-task-manager";

export const BACKGROUND_NOTIFICATION_TASK = "BACKGROUND_NOTIFICATION_TASK";

TaskManager.defineTask(BACKGROUND_NOTIFICATION_TASK, async ({ data, error }: any) => {
  if (error) {
    console.warn("[notif-task] Error:", error);
    return;
  }
  const payload = data?.notification?.data || {};
  const title = payload.title || "Woofy Go";
  const body = payload.body || "";
  const channelId = payload.channelId || "walks-v5";

  await Notifications.scheduleNotificationAsync({
    content: {
      title,
      body,
      data: payload,
    },
    trigger: {
      channelId,
    } as any,
  });
  console.log("[notif-task] Notif local mostrada, canal:", channelId);
});
'''

with open(TASK_PATH, "wb") as f:
    f.write(TASK_CONTENT)
print("[OK] Creado: " + TASK_PATH)

# --- 2) Modificar index.ts ---
backup = INDEX_PATH + ".bak"
if not os.path.exists(backup):
    shutil.copyfile(INDEX_PATH, backup)
    print("[BACKUP] " + backup)

with open(INDEX_PATH, "rb") as f:
    src = f.read()

if b"backgroundNotification" in src:
    print("[SKIP] index.ts ya tiene el import")
else:
    viejo = b"import { registerRootComponent } from 'expo';"
    nuevo = b"import \"./src/tasks/backgroundNotification\";\nimport { registerRootComponent } from 'expo';"
    if viejo not in src:
        print("[FAIL] No encontre el import de registerRootComponent")
        sys.exit(1)
    src = src.replace(viejo, nuevo, 1)
    with open(INDEX_PATH, "wb") as f:
        f.write(src)
    print("[OK] Import agregado a index.ts")

# --- 3) Sacar defineTask de NotificationContext.tsx ---
CTX_PATH = os.path.join(MOBILE, "src", "contexts", "NotificationContext.tsx")
backup2 = CTX_PATH + ".bgtask.bak"
if not os.path.exists(backup2):
    shutil.copyfile(CTX_PATH, backup2)
    print("[BACKUP] " + backup2)

with open(CTX_PATH, "rb") as f:
    ctx = f.read()

# Buscar el bloque del defineTask
bloque_inicio = b'const BACKGROUND_NOTIFICATION_TASK = "BACKGROUND_NOTIFICATION_TASK";'
bloque_fin = b'  console.log("[notif] Background task: notif local mostrada, canal:", channelId);\r\n});'
bloque_fin_lf = b'  console.log("[notif] Background task: notif local mostrada, canal:", channelId);\n});'

if bloque_inicio in ctx:
    idx_ini = ctx.find(bloque_inicio)
    if bloque_fin in ctx:
        idx_fin = ctx.find(bloque_fin) + len(bloque_fin)
    elif bloque_fin_lf in ctx:
        idx_fin = ctx.find(bloque_fin_lf) + len(bloque_fin_lf)
    else:
        print("[FAIL] No encontre el cierre del bloque defineTask")
        sys.exit(1)
    # Reemplazar por import
    nuevo_ctx = b'import { BACKGROUND_NOTIFICATION_TASK } from "../tasks/backgroundNotification";'
    ctx = ctx[:idx_ini] + nuevo_ctx + ctx[idx_fin:]
    with open(CTX_PATH, "wb") as f:
        f.write(ctx)
    print("[OK] defineTask removido de NotificationContext.tsx")
else:
    print("[SKIP] defineTask ya no estaba en el Context")

print("[DONE] Todo listo")