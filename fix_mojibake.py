import os, sys, shutil

# Archivos con mojibake detectado
ARCHIVOS = [
    r"C:\woffy-mobile\src\screens\HomeScreen.tsx",
    r"C:\woffy-mobile\App.tsx",
    r"C:\woffy-mobile\src\screens\SettingsScreen.tsx",
    r"C:\woffy-mobile\src\screens\WalkDetailScreen.tsx",
    r"C:\woffy-mobile\src\screens\WalkerDashboardScreen.tsx",
]

# Mapa de caracteres mal codificados a correctos
MAP = {
    "Ã±": "ñ", "Ã‘": "Ñ",
    "Ã¡": "á", "Ã©": "é", "Ã­": "í", "Ã³": "ó", "Ãº": "ú",
    "Ã ": "Á", "Ã‰": "É", "Ã": "Í", "Ã“": "Ó", "Ãš": "Ú",
    "Â¿": "¿", "Â¡": "¡", "Â°": "°", "Â·": "·",
    "â€": "’", "â€œ": "“", "â€\x9d": "”", "â€”": "—", "â€“": "–",
    "ðŸ": "🐾",  # emoji
    "ð": "",
}

total_cambios = 0

for path in ARCHIVOS:
    if not os.path.exists(path):
        print(f"[SKIP] no existe: {path}")
        continue

    backup = path + ".mojibake.bak"
    if not os.path.exists(backup):
        shutil.copyfile(path, backup)

    with open(path, "r", encoding="utf-8", errors="surrogateescape") as f:
        src = f.read()

    original = src
    for viejo, nuevo in MAP.items():
        src = src.replace(viejo, nuevo)

    if src != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        count = sum(1 for k in MAP if k in original)
        print(f"[OK] {os.path.basename(path)}: {count} tipos de mojibake")
        total_cambios += 1
    else:
        print(f"[SKIP] {os.path.basename(path)}: sin cambios")

print(f"\n[DONE] {total_cambios} archivos corregidos")