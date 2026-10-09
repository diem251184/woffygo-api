import os, sys, shutil

PATH = r"C:\woffy-mobile\src\hooks\useLocation.ts"

backup = PATH + ".returns.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# 1) Cambiar el type del refresh en la interface
viejo_type = "  refresh: () => Promise<void>;"
nuevo_type = "  refresh: () => Promise<Coords | null>;"
if viejo_type in src:
    src = src.replace(viejo_type, nuevo_type, 1)
    print("[OK] Type del refresh actualizado")

# 2) Cambiar la implementacion del refresh
viejo_impl = '''  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const hasPermission = await requestPermission();
      if (!hasPermission) {
        setLoading(false);
        return;
      }
      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      setCoords({
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
        accuracy: location.coords.accuracy ?? null,
      });
    } catch (e: any) {
      setError("No se pudo obtener la ubicaci\\u00f3n");
    } finally {
      setLoading(false);
    }
  }, [requestPermission]);'''

nuevo_impl = '''  const refresh = useCallback(async (): Promise<Coords | null> => {
    setLoading(true);
    setError(null);
    try {
      const hasPermission = await requestPermission();
      if (!hasPermission) {
        setLoading(false);
        return null;
      }
      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      const c: Coords = {
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
        accuracy: location.coords.accuracy ?? null,
      };
      setCoords(c);
      return c;
    } catch (e: any) {
      setError("No se pudo obtener la ubicaci\\u00f3n");
      return null;
    } finally {
      setLoading(false);
    }
  }, [requestPermission]);'''

if viejo_impl in src:
    src = src.replace(viejo_impl, nuevo_impl, 1)
    print("[OK] Implementacion del refresh actualizada")
else:
    print("[WARN] no encontre la implementacion exacta, buscando variantes...")
    # Intentar con \\u en lugar de \u
    viejo_impl2 = viejo_impl.replace("\\\\u00f3", "\\u00f3")
    if viejo_impl2 in src:
        src = src.replace(viejo_impl2, nuevo_impl, 1)
        print("[OK] Implementacion del refresh actualizada (variante 2)")
    else:
        print("[FAIL] no encontre el bloque del refresh")
        sys.exit(1)

with open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(src)
print("[DONE] useLocation.ts actualizado")