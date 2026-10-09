import os, sys, shutil, re

PATH = r"C:\woffy-mobile\src\screens\AdminHomeScreen.tsx"

backup = PATH + ".usersbutton.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

if b'navigate("AdminUsers")' in src:
    print("[SKIP] ya tiene navigate AdminUsers")
    sys.exit(0)

# Buscar el bloque de Usuarios (marcado como disabled/Proximamente)
# Usamos regex para capturar el bloque completo
pattern = re.compile(
    rb'<TouchableOpacity\s+style=\{\[styles\.actionCard,\s*styles\.actionCardDisabled\]\}\s+disabled\s+activeOpacity=\{0\.9\}\s*>\s*<View style=\{styles\.actionIconWrap\}>\s*<Text style=\{styles\.actionEmoji\}>[^<]*</Text>\s*</View>\s*<View style=\{\{ flex: 1 \}\}>\s*<Text style=\{styles\.actionTitle\}>Usuarios</Text>\s*<Text style=\{styles\.actionSubtitle\}>Proximamente</Text>\s*</View>\s*<Text style=\{styles\.actionArrow\}>[^<]*</Text>\s*</TouchableOpacity>',
    re.DOTALL
)

m = pattern.search(src)
if not m:
    print("[FAIL] no matcheo con regex. Buscando 'actionCardDisabled'...")
    idx = src.find(b"actionCardDisabled")
    if idx >= 0:
        print("Contexto (300 chars):")
        print(src[max(0, idx-200):idx+500].decode('utf-8', errors='replace'))
    sys.exit(1)

viejo = m.group(0)
# Reemplazo: mismo bloque pero activo con navigate
nuevo = (
    b'<TouchableOpacity\n'
    b'          style={styles.actionCard}\n'
    b'          onPress={() => navigation.navigate("AdminUsers")}\n'
    b'          activeOpacity={0.9}\n'
    b'        >\n'
    b'          <View style={styles.actionIconWrap}>\n'
    b'            <Text style={styles.actionEmoji}>{"\\u{1F465}"}</Text>\n'
    b'          </View>\n'
    b'          <View style={{ flex: 1 }}>\n'
    b'            <Text style={styles.actionTitle}>Usuarios</Text>\n'
    b'            <Text style={styles.actionSubtitle}>Ver, bloquear y desbloquear</Text>\n'
    b'          </View>\n'
    b'          <Text style={styles.actionArrow}>{"\\u203A"}</Text>\n'
    b'        </TouchableOpacity>'
)

src = src.replace(viejo, nuevo, 1)

with open(PATH, "wb") as f:
    f.write(src)

print("[OK] Boton Usuarios activado")
print("[DONE] AdminHomeScreen actualizado")