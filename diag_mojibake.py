import os

PATH = r"C:\woffy-mobile\src\screens\HomeScreen.tsx"

with open(PATH, "rb") as f:
    contenido = f.read()

# Buscar la linea con "Dueño de mascota"
for i, line in enumerate(contenido.split(b"\n"), start=1):
    if b"de mascota" in line and b"isOwner" in line:
        print(f"Linea {i} (bytes crudos):")
        print("  repr:", repr(line.decode('utf-8', errors='replace')))
        print()
        # Mostrar los bytes de la palabra
        idx = line.find(b"Due")
        if idx >= 0:
            snippet = line[idx:idx+25]
            print(f"  Bytes: {' '.join(f'{b:02x}' for b in snippet)}")
            print(f"  Como UTF-8: '{snippet.decode('utf-8', errors='replace')}'")
            print(f"  Como Latin-1: '{snippet.decode('latin-1', errors='replace')}'")
        break