import os, sys, re

PATH = r"C:\woffy-mobile\src\screens\WalkDetailScreen.tsx"
BACKUP = PATH + ".banner.bak"

if not os.path.exists(BACKUP):
    import shutil
    shutil.copyfile(PATH, BACKUP)
    print("[BACKUP] " + BACKUP)

with open(PATH, "rb") as f:
    src = f.read()

orig = src
nl = b"\r\n" if b"\r\n" in src[:5000] else b"\n"

# --- 1) Banner en el JSX ---
anchor = b'      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>'
banner = (
    anchor + nl +
    b'        {walk.status === "cancelado" && walk.cancel_reason && (' + nl +
    b'          <View style={styles.cancelBanner}>' + nl +
    b'            <Text style={styles.cancelBannerTitle}>Paseo cancelado</Text>' + nl +
    b'            <Text style={styles.cancelBannerText}>Motivo: {walk.cancel_reason}</Text>' + nl +
    b'          </View>' + nl +
    b'        )}'
)
if anchor not in src:
    print("[FAIL] 1 - no encontre el ScrollView")
    sys.exit(1)
src = src.replace(anchor, banner, 1)
print("[OK] 1 - banner agregado al JSX")

# --- 2) Estilos al final del StyleSheet ---
# Buscamos el cierre del StyleSheet: la ultima vez que aparece "  });"
# Lo hacemos insertando antes de "notesText:" que ya existe como referencia
style_anchor = b'    notesText: { fontSize: 13, color: colors.text, fontStyle: "italic" },'
style_new = (
    b'    cancelBanner: {' + nl +
    b'      backgroundColor: "rgba(185,28,28,0.12)",' + nl +
    b'      borderWidth: 1,' + nl +
    b'      borderColor: "#B91C1C",' + nl +
    b'      borderRadius: radius.md,' + nl +
    b'      padding: spacing.md,' + nl +
    b'      marginBottom: spacing.md,' + nl +
    b'    },' + nl +
    b'    cancelBannerTitle: {' + nl +
    b'      fontSize: 14,' + nl +
    b'      fontWeight: "800",' + nl +
    b'      color: "#F87171",' + nl +
    b'      marginBottom: 4,' + nl +
    b'    },' + nl +
    b'    cancelBannerText: {' + nl +
    b'      fontSize: 13,' + nl +
    b'      color: colors.text,' + nl +
    b'      lineHeight: 18,' + nl +
    b'    },' + nl +
    b'    ' + style_anchor
)
if style_anchor not in src:
    print("[FAIL] 2 - no encontre notesText en los estilos")
    sys.exit(1)
src = src.replace(style_anchor, style_new, 1)
print("[OK] 2 - estilos agregados")

if src == orig:
    print("[WARN] sin cambios")
    sys.exit(1)

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] Banner de cancelacion agregado")