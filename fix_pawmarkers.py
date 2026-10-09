import os, sys, shutil

PATH = r"C:\woffy-mobile\src\screens\WalkDetailScreen.tsx"

backup = PATH + ".pawmarkers.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

nl = b"\r\n" if b"\r\n" in src[:5000] else b"\n"

# --- 1) Agregar Image al import de react-native ---
viejo_import = b'''  KeyboardAvoidingView,
  Platform,
} from "react-native";'''
nuevo_import = b'''  KeyboardAvoidingView,
  Platform,
  Image,
} from "react-native";'''
if b"  Image,\n} from \"react-native\";" in src or b"  Image,\r\n} from \"react-native\";" in src:
    print("[SKIP] Image ya importado")
elif viejo_import in src:
    src = src.replace(viejo_import, nuevo_import, 1)
    print("[OK] Image agregado al import")
else:
    print("[FAIL] no encontre el import de react-native")
    sys.exit(1)

# --- 2) Reemplazar marcador START ---
viejo_start = b'''              <View style={styles.markerWrap}>
                <Text style={styles.markerEmoji}>{"\\u{1F7E2}"}</Text>
              </View>'''
nuevo_start = b'''              <View style={[styles.markerCircle, styles.markerCircleStart]}>
                <Image
                  source={require("../../assets/android-icon-monochrome.png")}
                  style={styles.markerPawImage}
                  resizeMode="contain"
                />
              </View>'''

if viejo_start in src:
    src = src.replace(viejo_start, nuevo_start, 1)
    print("[OK] Marcador START reemplazado")
else:
    print("[WARN] no encontre marcador start con emoji verde, buscando alternativa...")
    # Intento alternativo con LF
    viejo_start_lf = b'''              <View style={styles.markerWrap}>\n                <Text style={styles.markerEmoji}>{"\\u{1F7E2}"}</Text>\n              </View>'''
    if viejo_start_lf in src:
        src = src.replace(viejo_start_lf, nuevo_start, 1)
        print("[OK] Marcador START reemplazado (LF)")

# --- 3) Reemplazar marcador END ---
viejo_end = b'''              <View style={styles.markerWrap}>
                <Text style={styles.markerEmoji}>{"\\u{1F534}"}</Text>
              </View>'''
nuevo_end = b'''              <View style={[styles.markerCircle, styles.markerCircleEnd]}>
                <Image
                  source={require("../../assets/android-icon-monochrome.png")}
                  style={styles.markerPawImage}
                  resizeMode="contain"
                />
              </View>'''

if viejo_end in src:
    src = src.replace(viejo_end, nuevo_end, 1)
    print("[OK] Marcador END reemplazado")
else:
    print("[WARN] no encontre marcador end con emoji rojo")

# --- 4) Reemplazar los estilos ---
viejo_styles = b'    markerWrap: { alignItems: "center", justifyContent: "center" },\n    markerEmoji: { fontSize: 22 },'
if viejo_styles not in src:
    viejo_styles = b'    markerWrap: { alignItems: "center", justifyContent: "center" },\r\n    markerEmoji: { fontSize: 22 },'

nuevo_styles = (
    b'    markerCircle: {\n' +
    b'      width: 36,\n' +
    b'      height: 36,\n' +
    b'      borderRadius: 18,\n' +
    b'      alignItems: "center",\n' +
    b'      justifyContent: "center",\n' +
    b'      borderWidth: 3,\n' +
    b'      borderColor: "#FFFFFF",\n' +
    b'      shadowColor: "#000",\n' +
    b'      shadowOffset: { width: 0, height: 2 },\n' +
    b'      shadowOpacity: 0.35,\n' +
    b'      shadowRadius: 4,\n' +
    b'      elevation: 5,\n' +
    b'    },\n' +
    b'    markerCircleStart: { backgroundColor: "#10B981" },\n' +
    b'    markerCircleEnd: { backgroundColor: "#EF4444" },\n' +
    b'    markerPawImage: { width: 20, height: 20 },\n' +
    b'    markerWrap: { alignItems: "center", justifyContent: "center" },\n' +
    b'    markerEmoji: { fontSize: 22 },'
)

if viejo_styles in src:
    src = src.replace(viejo_styles, nuevo_styles, 1)
    print("[OK] Estilos reemplazados")
else:
    print("[WARN] no encontre los estilos markerWrap/markerEmoji")

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] Marcadores actualizados a paw en circulo de color")