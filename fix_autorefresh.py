import os, sys, shutil

PATH = r"C:\woffy-mobile\src\screens\WalkerDashboardScreen.tsx"

backup = PATH + ".autorefresh.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

orig = src
nl = b"\r\n" if b"\r\n" in src[:5000] else b"\n"

# 1) Cambiar useLocation(false) por useLocation(true)
viejo = b'const { coords, refresh: refreshLocation } = useLocation(false);'
nuevo = b'const { coords, refresh: refreshLocation } = useLocation(true);'
if viejo not in src:
    print("[FAIL] no encontre useLocation(false)")
    sys.exit(1)
src = src.replace(viejo, nuevo, 1)
print("[OK] useLocation(true) - auto-pide coords al montar")

# 2) Modificar el useEffect para que llame a refresh si coords es null
viejo_eff = (
    b'  useEffect(() => {' + nl +
    b'    if (!profile?.is_online || !coords) return;' + nl +
    b'    (async () => {'
)
nuevo_eff = (
    b'  useEffect(() => {' + nl +
    b'    if (!profile?.is_online) return;' + nl +
    b'    (async () => {' + nl +
    b'      if (!coords) {' + nl +
    b'        try { await refreshLocation(); } catch {}' + nl +
    b'        return;' + nl +
    b'      }'
)
if viejo_eff not in src:
    print("[FAIL] no encontre el useEffect de auto-reporte")
    sys.exit(1)
src = src.replace(viejo_eff, nuevo_eff, 1)
print("[OK] useEffect ahora pide coords si faltan")

if src == orig:
    print("[WARN] sin cambios")
    sys.exit(1)

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] WalkerDashboardScreen.tsx actualizado (auto-refresh)")