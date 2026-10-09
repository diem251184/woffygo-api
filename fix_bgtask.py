import os

PATH = r"C:\woffy-mobile\src\contexts\NotificationContext.tsx"

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# 1) Agregar imports
viejo_import = 'import * as Notifications from "expo-notifications";\nimport { Platform } from "react-native";'
nuevo_import = '''import * as Notifications from "expo-notifications";
import * as TaskManager from "expo-task-manager";
import { Platform } from "react-native";

const BACKGROUND_NOTIFICATION_TASK = "BACKGROUND_NOTIFICATION_TASK";

TaskManager.defineTask(BACKGROUND_NOTIFICATION_TASK, async ({ data, error }: any) => {
  if (error) {
    console.warn("[notif] Background task error:", error);
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
      sound: "notification.wav",
      data: payload,
    },
    trigger: null,
    ...( { channelId } as any ),
  });
  console.log("[notif] Background task: notif local mostrada, canal:", channelId);
});'''

if viejo_import not in src:
    print("[FAIL] No encontre el import exacto")
    import sys
    sys.exit(1)

src = src.replace(viejo_import, nuevo_import, 1)

# 2) Registrar la task dentro del useEffect
viejo_effect = '        if (Platform.OS === "android") {\n          await Notifications.setNotificationChannelAsync("walks-v5", {'
nuevo_effect = '''        if (Platform.OS === "android") {
          await Notifications.setNotificationChannelAsync("walks-v5", {'''

# Registrar la task despues del bloque de canales
viejo_fin = '          console.log("[notif] Canal info creado OK");\n        }'
nuevo_fin = '''          console.log("[notif] Canal info creado OK");
        }

        // Registrar background task para notificaciones data-only
        try {
          await Notifications.registerTaskAsync(BACKGROUND_NOTIFICATION_TASK);
          console.log("[notif] Background task registrada OK");
        } catch (e: any) {
          console.warn("[notif] Error registrando background task:", e?.message);
        }'''

if viejo_fin not in src:
    print("[FAIL] No encontre el cierre del bloque de canales")
    import sys
    sys.exit(1)

src = src.replace(viejo_fin, nuevo_fin, 1)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("[DONE] NotificationContext.tsx actualizado con background task")