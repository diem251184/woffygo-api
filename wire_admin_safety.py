import os, sys

MOBILE = r"C:\woffy-mobile"

# ============================================================
# 1) App.tsx
# ============================================================
APP_PATH = os.path.join(MOBILE, "App.tsx")
with open(APP_PATH, "rb") as f:
    src = f.read()

if b"AdminSafetyReportsScreen" in src:
    print("[SKIP] App.tsx ya tiene ruta")
else:
    viejo = b'import { SafetyReportsMapScreen } from "./src/screens/SafetyReportsMapScreen";'
    nuevo = (
        viejo + b'\n'
        b'import { AdminSafetyReportsScreen } from "./src/screens/AdminSafetyReportsScreen";'
    )
    if viejo not in src:
        print("[FAIL] no encontre import de SafetyReportsMapScreen")
        sys.exit(1)
    src = src.replace(viejo, nuevo, 1)

    viejo2 = b'<Stack.Screen name="SafetyReportsMap" component={SafetyReportsMapScreen} options={{ headerShown: false }} />'
    nuevo2 = (
        viejo2 + b'\n'
        b'            <Stack.Screen name="AdminSafetyReports" component={AdminSafetyReportsScreen} options={{ title: "Reportes de seguridad" }} />'
    )
    if viejo2 not in src:
        print("[FAIL] no encontre Stack.Screen")
        sys.exit(1)
    src = src.replace(viejo2, nuevo2, 1)

    with open(APP_PATH, "wb") as f:
        f.write(src)
    print("[OK] Ruta AdminSafetyReports agregada")

# ============================================================
# 2) AdminHomeScreen: activar boton Reportes de seguridad
# ============================================================
HOME_PATH = os.path.join(MOBILE, "src", "screens", "AdminHomeScreen.tsx")

with open(HOME_PATH, "r", encoding="utf-8") as f:
    src = f.read()

if 'navigate("AdminSafetyReports")' in src:
    print("[SKIP] AdminHome ya tiene boton activo")
else:
    viejo = '''        <TouchableOpacity
          style={[styles.actionCard, styles.actionCardDisabled]}
          disabled
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>🛡️</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Reportes de seguridad</Text>
            <Text style={styles.actionSubtitle}>Proximamente</Text>
          </View>
          <Text style={styles.actionArrow}>›</Text>
        </TouchableOpacity>'''

    nuevo = '''        <TouchableOpacity
          style={styles.actionCard}
          onPress={() => navigation.navigate("AdminSafetyReports")}
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>🛡️</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Reportes de seguridad</Text>
            <Text style={styles.actionSubtitle}>Ver, verificar y eliminar</Text>
          </View>
          <Text style={styles.actionArrow}>›</Text>
        </TouchableOpacity>'''

    if viejo not in src:
        print("[FAIL] no encontre el bloque Proximamente")
        sys.exit(1)

    src = src.replace(viejo, nuevo, 1)

    with open(HOME_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    print("[OK] Boton Reportes de seguridad activado")

print("[DONE]")