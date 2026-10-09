import os, sys, shutil

ADMIN_HOME = r"C:\woffy-mobile\src\screens\AdminHomeScreen.tsx"

with open(ADMIN_HOME, "r", encoding="utf-8") as f:
    src = f.read()

if 'navigate("AdminStats")' in src:
    print("[SKIP] ya tiene los botones")
    sys.exit(0)

# Los emojis son literales en el archivo
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

nuevos = '''        <TouchableOpacity
          style={styles.actionCard}
          onPress={() => navigation.navigate("AdminStats")}
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>📊</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Estadisticas</Text>
            <Text style={styles.actionSubtitle}>Contadores y metricas</Text>
          </View>
          <Text style={styles.actionArrow}>›</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionCard}
          onPress={() => navigation.navigate("AdminActions")}
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>📜</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Historial de acciones</Text>
            <Text style={styles.actionSubtitle}>Auditoria de admins</Text>
          </View>
          <Text style={styles.actionArrow}>›</Text>
        </TouchableOpacity>

''' + viejo

if viejo not in src:
    print("[FAIL] aun no matchea")
    sys.exit(1)

src = src.replace(viejo, nuevos, 1)

with open(ADMIN_HOME, "w", encoding="utf-8", newline="\n") as f:
    f.write(src)

print("[OK] Botones Stats y Actions agregados")