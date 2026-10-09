import os, sys, shutil

# ============================================
# AdminUsersScreen.tsx — cambiar badges
# ============================================
PATH = r"C:\woffy-mobile\src\screens\AdminUsersScreen.tsx"

backup = PATH + ".espanol.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

viejo = b'''const ROLE_LABELS: Record<string, string> = {
  owner: "OWNER",
  walker: "WALKER",
  admin: "ADMIN",
};'''

nuevo = b'''const ROLE_LABELS: Record<string, string> = {
  owner: "DUE\\xc3\\x91O",
  walker: "PASEADOR",
  admin: "ADMIN",
};'''

if viejo not in src:
    print("[WARN] no encontre el bloque exacto en AdminUsersScreen")
else:
    src = src.replace(viejo, nuevo, 1)
    with open(PATH, "wb") as f:
        f.write(src)
    print("[OK] AdminUsersScreen: badges en espanol")

# ============================================
# AdminUserDetailScreen.tsx — verificar
# ============================================
PATH2 = r"C:\woffy-mobile\src\screens\AdminUserDetailScreen.tsx"
with open(PATH2, "rb") as f:
    src2 = f.read()

if b'"Due\\xc3\\xb1o"' in src2 or b'"Paseador"' in src2:
    print("[SKIP] AdminUserDetailScreen ya esta en espanol")
else:
    print("[WARN] AdminUserDetailScreen no tiene los labels esperados")

print("[DONE]")