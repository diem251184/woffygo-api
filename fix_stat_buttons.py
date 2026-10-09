import os, sys, shutil

ADMIN_HOME = r"C:\woffy-mobile\src\screens\AdminHomeScreen.tsx"

backup = ADMIN_HOME + ".statbuttons.bak"
if not os.path.exists(backup):
    shutil.copyfile(ADMIN_HOME, backup)
    print("[BACKUP] " + backup)

# Leer como UTF-8 (str) para trabajar con strings
with open(ADMIN_HOME, "r", encoding="utf-8") as f:
    src = f.read()

if 'navigate("AdminStats")' in src:
    print("[SKIP] ya tiene los botones")
    sys.exit(0)

viejo = '''        <TouchableOpacity
          style={[styles.actionCard, styles.actionCardDisabled]}
          disabled
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>{"\\u{1F6E1}\\uFE0F"}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Reportes de seguridad</Text>
            <Text style={styles.actionSubtitle}>Proximamente</Text>
          </View>
          <Text style={styles.actionArrow}>{"\\u203A"}</Text>
        </TouchableOpacity>'''

nuevos = '''        <TouchableOpacity
          style={styles.actionCard}
          onPress={() => navigation.navigate("AdminStats")}
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>{"\\u{1F4CA}"}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Estadisticas</Text>
            <Text style={styles.actionSubtitle}>Contadores y metricas</Text>
          </View>
          <Text style={styles.actionArrow}>{"\\u203A"}</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionCard}
          onPress={() => navigation.navigate("AdminActions")}
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>{"\\u{1F4DC}"}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Historial de acciones</Text>
            <Text style={styles.actionSubtitle}>Auditoria de admins</Text>
          </View>
          <Text style={styles.actionArrow}>{"\\u203A"}</Text>
        </TouchableOpacity>

''' + viejo

if viejo not in src:
    print("[FAIL] no encontre el bloque de Reportes de seguridad")
    print("Buscando 'actionCardDisabled' en el archivo...")
    idx = src.find("actionCardDisabled")
    if idx >= 0:
        print("Contexto:")
        print(src[max(0, idx-200):idx+600])
    sys.exit(1)

src = src.replace(viejo, nuevos, 1)

with open(ADMIN_HOME, "w", encoding="utf-8", newline="\n") as f:
    f.write(src)

print("[OK] Botones Stats y Actions agregados a AdminHome")
print("[DONE]")