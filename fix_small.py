import os, sys, shutil, re

# ============================================
# 1) Fix banner admin en WalkDetailScreen
# ============================================
PATH_WD = r"C:\woffy-mobile\src\screens\WalkDetailScreen.tsx"

backup = PATH_WD + ".cleanbanner.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH_WD, backup)
    print("[BACKUP] " + backup)

with open(PATH_WD, "rb") as f:
    src = f.read()

# Cambiar el render del texto para que limpie el prefijo
viejo = b'<Text style={styles.flagBannerText}>{walk.flag_reason}</Text>'
nuevo = b'<Text style={styles.flagBannerText}>{walk.flag_reason.replace(/^\\[REVISADO POR ADMIN\\]\\s*/, "")}</Text>'

if viejo in src:
    src = src.replace(viejo, nuevo, 1)
    with open(PATH_WD, "wb") as f:
        f.write(src)
    print("[OK] Banner limpiado (prefijo removido)")
else:
    print("[SKIP] no encontre el texto del flagBanner")

# ============================================
# 2) Buscar emojis rotos (mojibake) en todas las pantallas
# ============================================
print("\n[SCAN] Buscando emojis rotos...")
SCREENS_DIR = r"C:\woffy-mobile\src"

patrones_roto = [
    "ðŸ",  # inicio de emoji mal codificado
    "âš",  # simbolos
    "â€",  # comillas/puntos suspensivos
    "Ã¡", "Ã©", "Ã­", "Ã³", "Ãº", "Ã±", "Ã‘",
    "Â¡", "Â¿",
]

for root, dirs, files in os.walk(SCREENS_DIR):
    if "node_modules" in root: continue
    for fname in files:
        if not (fname.endswith(".tsx") or fname.endswith(".ts")): continue
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, "r", encoding="utf-8", errors="surrogateescape") as f:
                content = f.read()
            matches = [p for p in patrones_roto if p in content]
            if matches:
                print(f"  {fname}: {matches}")
        except Exception as e:
            pass

print("\n[DONE] Scan completo")