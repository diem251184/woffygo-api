import os, sys, shutil

PATH = r"C:\woffy-mobile\src\screens\AdminStatsScreen.tsx"

backup = PATH + ".moneyfix.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# Cambiar los estilos del moneyRow
viejo = '''    moneyRow: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      paddingVertical: 6,
    },
    moneyLabel: { fontSize: 13, color: colors.textMuted },
    moneyValue: { fontSize: 15, fontWeight: "800", color: colors.accent },'''

nuevo = '''    moneyRow: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      paddingVertical: 8,
      gap: spacing.md,
    },
    moneyLabel: { fontSize: 13, color: colors.textMuted, flex: 1 },
    moneyValue: { fontSize: 15, fontWeight: "800", color: colors.accent, flexShrink: 0 },'''

if viejo not in src:
    print("[FAIL] no encontre los estilos moneyRow")
    sys.exit(1)

src = src.replace(viejo, nuevo, 1)

# Tambien cambiar los textos mas largos para que sean legibles
# "Comision este mes" -> "Comision del mes"
# "En escrow ahora" -> "En escrow"
# "En disputa" queda corto

with open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(src)

print("[OK] Estilos del bloque Ingresos ajustados")