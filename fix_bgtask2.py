import os, sys

PATH = r"C:\woffy-mobile\src\contexts\NotificationContext.tsx"

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

viejo = '''  await Notifications.scheduleNotificationAsync({
    content: {
      title,
      body,
      sound: "notification.wav",
      data: payload,
    },
    trigger: null,
    ...( { channelId } as any ),
  });'''

nuevo = '''  await Notifications.scheduleNotificationAsync({
    content: {
      title,
      body,
      data: payload,
    },
    trigger: {
      channelId,
    } as any,
  });'''

if viejo not in src:
    print("[FAIL] No encontre el bloque exacto")
    sys.exit(1)

src = src.replace(viejo, nuevo, 1)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("[OK] channelId movido a trigger, sound removido de content")