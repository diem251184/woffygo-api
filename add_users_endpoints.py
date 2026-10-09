import os, sys, shutil

# ============================================================
# 1) Agregar schemas al admin.py
# ============================================================
SCHEMA_PATH = r"C:\woffygo\app\schemas\admin.py"

backup = SCHEMA_PATH + ".users.bak"
if not os.path.exists(backup):
    shutil.copyfile(SCHEMA_PATH, backup)
    print("[BACKUP] " + backup)

with open(SCHEMA_PATH, "rb") as f:
    src = f.read()

if b"AdminUserListItem" in src:
    print("[SKIP] schemas ya tienen AdminUserListItem")
else:
    add = b'''

# ============================================
# Admin - Usuarios
# ============================================

class AdminUserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str
    role: str
    is_active: bool
    created_at: datetime


class AdminWalkerProfileInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bio: str | None
    hourly_rate: Decimal
    search_radius_km: int
    is_online: bool
    rating_avg: Decimal | None
    total_walks: int
    current_latitude: float | None = None
    current_longitude: float | None = None


class AdminUserDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Contadores
    pets_count: int = 0
    walks_as_owner_count: int = 0
    walks_as_walker_count: int = 0
    # Perfil walker (si aplica)
    walker_profile: AdminWalkerProfileInfo | None = None


class ToggleActiveRequest(BaseModel):
    is_active: bool
'''

    src = src.rstrip() + add
    with open(SCHEMA_PATH, "wb") as f:
        f.write(src)
    print("[OK] Schemas agregados")

# ============================================================
# 2) Endpoints en admin.py
# ============================================================
ROUTER_PATH = r"C:\woffygo\app\routers\admin.py"

backup = ROUTER_PATH + ".users.bak"
if not os.path.exists(backup):
    shutil.copyfile(ROUTER_PATH, backup)
    print("[BACKUP] " + backup)

with open(ROUTER_PATH, "rb") as f:
    src = f.read()

if b"list_users" in src:
    print("[SKIP] endpoints de users ya existen")
    sys.exit(0)

# Agregar imports
viejo_imports = b'from app.schemas.payment import PaymentResponse'
nuevo_imports = (
    viejo_imports + b'\n'
    b'from app.schemas.admin import AdminUserListItem, AdminUserDetail, AdminWalkerProfileInfo, ToggleActiveRequest\n'
    b'from app.models.pet import Pet\n'
    b'from app.models.walk import Walk, WalkStatus'
)
if viejo_imports not in src:
    print("[FAIL] no encontre imports de PaymentResponse")
    sys.exit(1)
src = src.replace(viejo_imports, nuevo_imports, 1)
print("[OK] Imports agregados")

# Endpoints
endpoints = b'''


@router.get("/users", response_model=list[AdminUserListItem])
def list_users(
    role: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Lista usuarios con filtros opcionales.

    - role: owner | walker | admin
    - is_active: true | false
    - search: busca por email o nombre (contiene)
    """
    query = db.query(User)
    if role:
        try:
            query = query.filter(User.role == UserRole(role))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rol invalido: {role}",
            )
    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            (User.email.ilike(like)) | (User.full_name.ilike(like))
        )
    return (
        query.order_by(User.created_at.desc())
        .limit(min(limit, 200))
        .offset(offset)
        .all()
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user_detail(
    user_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Devuelve el detalle de un usuario con contadores y perfil walker."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    # Contadores
    pets_count = db.query(Pet).filter(Pet.owner_id == user.id).count()
    walks_as_owner = db.query(Walk).filter(Walk.owner_id == user.id).count()
    walks_as_walker = db.query(Walk).filter(Walk.walker_id == user.id).count()

    # Perfil walker
    wp_info = None
    wp = user.walker_profile
    if wp is not None:
        lat = lon = None
        try:
            from sqlalchemy import text as _text
            row = db.execute(_text(
                "SELECT ST_Y(CAST(current_location AS geometry)) AS lat, "
                "ST_X(CAST(current_location AS geometry)) AS lon "
                "FROM walker_profiles WHERE user_id = :uid"
            ), {"uid": user.id}).first()
            if row is not None:
                lat = float(row.lat) if row.lat is not None else None
                lon = float(row.lon) if row.lon is not None else None
        except Exception:
            pass
        wp_info = AdminWalkerProfileInfo(
            bio=wp.bio,
            hourly_rate=wp.hourly_rate,
            search_radius_km=wp.search_radius_km,
            is_online=wp.is_online,
            rating_avg=wp.rating_avg,
            total_walks=wp.total_walks,
            current_latitude=lat,
            current_longitude=lon,
        )

    return AdminUserDetail(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        pets_count=pets_count,
        walks_as_owner_count=walks_as_owner,
        walks_as_walker_count=walks_as_walker,
        walker_profile=wp_info,
    )


@router.post("/users/{user_id}/toggle-active", response_model=AdminUserDetail)
def toggle_user_active(
    user_id: int,
    payload: ToggleActiveRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Bloquea o desbloquea un usuario."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No podes bloquearte a vos mismo",
        )
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede bloquear a otro admin",
        )

    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)

    # Devolvemos el detalle actualizado
    return get_user_detail(user.id, current_user, db)
'''

src = src.rstrip() + endpoints

with open(ROUTER_PATH, "wb") as f:
    f.write(src)
print("[DONE] Endpoints agregados a admin.py")