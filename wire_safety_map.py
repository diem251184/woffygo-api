import os, sys

MOBILE = r"C:\woffy-mobile"

# ============================================================
# 1) App.tsx: agregar ruta
# ============================================================
APP_PATH = os.path.join(MOBILE, "App.tsx")
with open(APP_PATH, "rb") as f:
    src = f.read()

if b"SafetyReportsMapScreen" in src:
    print("[SKIP] App.tsx ya tiene ruta")
else:
    viejo = b'import { AdminActionsScreen } from "./src/screens/AdminActionsScreen";'
    nuevo = (
        viejo + b'\n'
        b'import { SafetyReportsMapScreen } from "./src/screens/SafetyReportsMapScreen";'
    )
    if viejo not in src:
        print("[FAIL] no encontre import de AdminActionsScreen")
        sys.exit(1)
    src = src.replace(viejo, nuevo, 1)

    viejo2 = b'<Stack.Screen name="AdminActions" component={AdminActionsScreen} options={{ title: "Historial de acciones" }} />'
    nuevo2 = (
        viejo2 + b'\n'
        b'            <Stack.Screen name="SafetyReportsMap" component={SafetyReportsMapScreen} options={{ headerShown: false }} />'
    )
    if viejo2 not in src:
        print("[FAIL] no encontre Stack.Screen de AdminActions")
        sys.exit(1)
    src = src.replace(viejo2, nuevo2, 1)

    with open(APP_PATH, "wb") as f:
        f.write(src)
    print("[OK] Ruta SafetyReportsMap agregada")

# ============================================================
# 2) HomeScreen: agregar boton "Zonas de seguridad"
# ============================================================
HOME_PATH = os.path.join(MOBILE, "src", "screens", "HomeScreen.tsx")
with open(HOME_PATH, "rb") as f:
    src = f.read()

if b"SafetyReportsMap" in src:
    print("[SKIP] HomeScreen ya tiene boton")
else:
    # Insertar despues del bloque isAdmin (que termina con )} antes del </ScrollView>)
    viejo = '''      {isAdmin && (
        <View style={styles.actionsColumn}>
          <TouchableOpacity
            style={styles.primaryActionCard}
            onPress={() => navigation.navigate("AdminHome")}'''

    if viejo not in src.decode('utf-8'):
        print("[FAIL] no encontre bloque isAdmin en HomeScreen")
        sys.exit(1)

    nuevo = '''      <View style={styles.actionsColumn}>
        <TouchableOpacity
          style={styles.actionCard}
          onPress={() => navigation.navigate("SafetyReportsMap")}
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>{"\\u26A0\\uFE0F"}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Zonas de seguridad</Text>
            <Text style={styles.actionSubtitle}>Ver reportes cerca tuyo</Text>
          </View>
          <Text style={styles.actionArrow}>{"\\u203A"}</Text>
        </TouchableOpacity>
      </View>

''' + viejo

    src_str = src.decode('utf-8')
    src_str = src_str.replace(viejo, nuevo, 1)
    src = src_str.encode('utf-8')

    with open(HOME_PATH, "wb") as f:
        f.write(src)
    print("[OK] Boton Zonas de seguridad agregado a HomeScreen")

print("[DONE]")