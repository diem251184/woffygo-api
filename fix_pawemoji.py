import os, sys, shutil

PATH = r"C:\woffy-mobile\src\screens\WalkDetailScreen.tsx"

backup = PATH + ".pawemoji.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

nl = b"\r\n" if b"\r\n" in src[:5000] else b"\n"

# --- 1) Reemplazar el bloque START ---
viejo_start = b'''              <View style={[styles.markerCircle, styles.markerCircleStart]}>
                <Image
                  source={require("../../assets/paw-marker.png")}
                  style={styles.markerPawImage}
                  resizeMode="contain"
                />
              </View>'''

nuevo_start = b'''              <View style={[styles.markerCircle, styles.markerCircleStart]}>
                <Text style={styles.markerPawEmoji}>{"\\u{1F43E}"}</Text>
              </View>'''

if viejo_start in src:
    src = src.replace(viejo_start, nuevo_start, 1)
    print("[OK] START cambiado a emoji")
else:
    print("[WARN] no encontre bloque START exacto")

# --- 2) Reemplazar el bloque END ---
viejo_end = b'''              <View style={[styles.markerCircle, styles.markerCircleEnd]}>
                <Image
                  source={require("../../assets/paw-marker.png")}
                  style={styles.markerPawImage}
                  resizeMode="contain"
                />
              </View>'''

nuevo_end = b'''              <View style={[styles.markerCircle, styles.markerCircleEnd]}>
                <Text style={styles.markerPawEmoji}>{"\\u{1F43E}"}</Text>
              </View>'''

if viejo_end in src:
    src = src.replace(viejo_end, nuevo_end, 1)
    print("[OK] END cambiado a emoji")
else:
    print("[WARN] no encontre bloque END exacto")

# --- 3) Actualizar estilos ---
viejo_style = b'    markerPawImage: { width: 30, height: 30 },'
nuevo_style = b'    markerPawEmoji: { fontSize: 24, color: "#FFFFFF" },'

if viejo_style in src:
    src = src.replace(viejo_style, nuevo_style, 1)
    print("[OK] Estilo actualizado")

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] Marcadores cambiados a emoji paw")