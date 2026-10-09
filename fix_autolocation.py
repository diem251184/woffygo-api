import os, sys, shutil

PATH = r"C:\woffy-mobile\src\screens\WalkerDashboardScreen.tsx"

backup = PATH + ".autoloc.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

orig = src
nl = b"\r\n" if b"\r\n" in src[:5000] else b"\n"

# 1) Agregar useEffect al import de React
viejo_import = b'import React, { useState, useCallback } from "react";'
nuevo_import = b'import React, { useState, useCallback, useEffect } from "react";'
if viejo_import not in src:
    print("[FAIL] import de React no encontrado")
    sys.exit(1)
src = src.replace(viejo_import, nuevo_import, 1)
print("[OK] useEffect importado")

# 2) Insertar los useEffect justo despues del useFocusEffect existente
viejo_focus = (
    b'  useFocusEffect(' + nl +
    b'    useCallback(() => {' + nl +
    b'      load();' + nl +
    b'    }, [load])' + nl +
    b'  );'
)
nuevo_focus = (
    viejo_focus + nl + nl +
    b'  // Auto-reporte de ubicacion: al entrar a la pantalla y cada vez que cambian las coords' + nl +
    b'  useEffect(() => {' + nl +
    b'    if (!profile?.is_online || !coords) return;' + nl +
    b'    (async () => {' + nl +
    b'      try {' + nl +
    b'        const updated = await setWalkerLocation(coords.latitude, coords.longitude);' + nl +
    b'        setProfile(updated);' + nl +
    b'        console.log("[walker] Ubicacion auto-reportada:", coords.latitude.toFixed(4), coords.longitude.toFixed(4));' + nl +
    b'      } catch (e: any) {' + nl +
    b'        console.warn("[walker] Error auto-reportando ubicacion:", e?.message);' + nl +
    b'      }' + nl +
    b'    })();' + nl +
    b'  }, [profile?.is_online, coords]);' + nl + nl +
    b'  // Re-envio periodico cada 5 minutos mientras la pantalla este activa' + nl +
    b'  useEffect(() => {' + nl +
    b'    const id = setInterval(async () => {' + nl +
    b'      try {' + nl +
    b'        await refreshLocation();' + nl +
    b'      } catch {}' + nl +
    b'    }, 5 * 60 * 1000);' + nl +
    b'    return () => clearInterval(id);' + nl +
    b'  }, [refreshLocation]);'
)
if viejo_focus not in src:
    print("[FAIL] bloque useFocusEffect no encontrado")
    sys.exit(1)
src = src.replace(viejo_focus, nuevo_focus, 1)
print("[OK] useEffects de auto-reporte agregados")

if src == orig:
    print("[WARN] sin cambios")
    sys.exit(1)

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] WalkerDashboardScreen.tsx actualizado")