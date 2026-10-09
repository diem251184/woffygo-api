import json

PATH = r"C:\woffy-mobile\package.json"

with open(PATH, "r", encoding="utf-8") as f:
    pkg = json.load(f)

# Forzar la version correcta
deps = pkg.get("dependencies", {})
viejo = deps.get("expo-notifications")
deps["expo-notifications"] = "~57.0.21"
pkg["dependencies"] = deps

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(pkg, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"[OK] expo-notifications: {viejo} -> ~57.0.21")