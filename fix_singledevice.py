import os, sys, shutil

PATH = r"C:\woffygo\app\routers\auth.py"

backup = PATH + ".singledevice.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

viejo = b'''    """Registra o actualiza el token de push del dispositivo actual."""
    existing = (
        db.query(DeviceToken)
        .filter(DeviceToken.token == payload.token)
        .first()
    )
    if existing is not None:
        existing.user_id = current_user.id
        existing.platform = payload.platform
        existing.is_active = True
    else:
        db.add(DeviceToken(
            user_id=current_user.id,
            token=payload.token,
            platform=payload.platform,
            is_active=True,
        ))
    db.commit()'''

nuevo = b'''    """Registra o actualiza el token de push del dispositivo actual.

    Estrategia single-device: al recibir un token nuevo, desactiva los
    tokens viejos del mismo usuario. Evita acumular tokens muertos y
    enviar push a dispositivos que ya no usan la app.
    """
    # Desactivar todos los tokens activos del user que NO sean el nuevo
    db.query(DeviceToken).filter(
        DeviceToken.user_id == current_user.id,
        DeviceToken.token != payload.token,
        DeviceToken.is_active.is_(True),
    ).update({"is_active": False}, synchronize_session=False)

    # Registrar o reactivar el token actual
    existing = (
        db.query(DeviceToken)
        .filter(DeviceToken.token == payload.token)
        .first()
    )
    if existing is not None:
        existing.user_id = current_user.id
        existing.platform = payload.platform
        existing.is_active = True
    else:
        db.add(DeviceToken(
            user_id=current_user.id,
            token=payload.token,
            platform=payload.platform,
            is_active=True,
        ))
    db.commit()'''

if viejo not in src:
    print("[FAIL] no encontre el bloque exacto del endpoint")
    sys.exit(1)

src = src.replace(viejo, nuevo, 1)

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] Endpoint actualizado: single-device activo")