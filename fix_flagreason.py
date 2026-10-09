import os, sys, shutil

PATH = r"C:\woffy-mobile\src\screens\WalkDetailScreen.tsx"

backup = PATH + ".flagreason.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

if b"flag_reason" in src:
    print("[SKIP] ya tiene flag_reason")
    sys.exit(0)

nl = b"\r\n" if b"\r\n" in src[:5000] else b"\n"

# Buscar el bloque del cancelBanner para insertar despues
ancla = b'        {walk.status === "cancelado" && walk.cancel_reason && ('

if ancla not in src:
    print("[FAIL] no encontre el bloque cancelBanner")
    sys.exit(1)

# Encontrar el final del bloque cancelBanner: buscamos la linea "        )}" que lo cierra
# Insertamos DESPUES del cierre del banner de cancelado
# Mejor: insertar el bloque flag ANTES del cancelBanner, usando el ancla como referencia
bloque_flag = (
    b'        {walk.flag_reason && (' + nl +
    b'          <View style={styles.flagBanner}>' + nl +
    b'            <Text style={styles.flagBannerTitle}>Revisado por admin</Text>' + nl +
    b'            <Text style={styles.flagBannerText}>{walk.flag_reason}</Text>' + nl +
    b'          </View>' + nl +
    b'        )}' + nl +
    nl
)

src = src.replace(ancla, bloque_flag + ancla, 1)
print("[OK] Bloque flag_reason agregado al JSX")

# Agregar los estilos
style_anchor = b'    cancelBanner: {'
if style_anchor not in src:
    print("[FAIL] no encontre cancelBanner en los estilos")
    sys.exit(1)

style_new = (
    b'    flagBanner: {' + nl +
    b'      backgroundColor: "rgba(201,169,97,0.12)",' + nl +
    b'      borderWidth: 1,' + nl +
    b'      borderColor: "#C9A961",' + nl +
    b'      borderRadius: radius.md,' + nl +
    b'      padding: spacing.md,' + nl +
    b'      marginBottom: spacing.md,' + nl +
    b'    },' + nl +
    b'    flagBannerTitle: {' + nl +
    b'      fontSize: 14,' + nl +
    b'      fontWeight: "800",' + nl +
    b'      color: "#C9A961",' + nl +
    b'      marginBottom: 4,' + nl +
    b'    },' + nl +
    b'    flagBannerText: {' + nl +
    b'      fontSize: 13,' + nl +
    b'      color: colors.text,' + nl +
    b'      lineHeight: 18,' + nl +
    b'    },' + nl +
    b'    ' + style_anchor
)

src = src.replace(style_anchor, style_new, 1)
print("[OK] Estilos agregados")

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] WalkDetailScreen actualizado con flag_reason")