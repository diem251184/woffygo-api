import os, sys, shutil

# ============================================================
# 1) Modelo SafetyReport
# ============================================================
MODEL_PATH = r"C:\woffygo\app\models\safety_report.py"

MODEL_CONTENT = '''from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Integer, func, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class SafetyCategory(str, enum.Enum):
    DANGER = "danger"                 # ⚠️ Peligro
    LOW_VISIBILITY = "low_visibility" # 🌑 Poca visibilidad
    OTHER = "other"                   # ❓ Otro


class SafetyReport(Base):
    """Reporte de seguridad tipo Waze, asociado a un paseo."""

    __tablename__ = "safety_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reporter_role: Mapped[str] = mapped_column(String(20), nullable=False)

    walk_id: Mapped[int | None] = mapped_column(
        ForeignKey("walks.id", ondelete="SET NULL"), nullable=True, index=True
    )

    category: Mapped[SafetyCategory] = mapped_column(
        SAEnum(SafetyCategory, name="safety_category",
               values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Coordenadas (guardadas directo, no PostGIS para simplificar)
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)

    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    reporter = relationship("User")
    walk = relationship("Walk")
'''

with open(MODEL_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(MODEL_CONTENT)
print("[OK] models/safety_report.py")

# ============================================================
# 2) Registrar en models/__init__.py
# ============================================================
INIT_PATH = r"C:\woffygo\app\models\__init__.py"

backup = INIT_PATH + ".safety.bak"
if not os.path.exists(backup):
    shutil.copyfile(INIT_PATH, backup)
    print("[BACKUP] " + backup)

with open(INIT_PATH, "r", encoding="utf-8") as f:
    init_src = f.read()

if "SafetyReport" in init_src:
    print("[SKIP] SafetyReport ya registrado")
else:
    linea = "from app.models.safety_report import SafetyReport, SafetyCategory\n"
    init_src = linea + init_src
    with open(INIT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(init_src)
    print("[OK] SafetyReport registrado en __init__")

# ============================================================
# 3) Schema
# ============================================================
SCHEMA_PATH = r"C:\woffygo\app\schemas\safety_report.py"

SCHEMA_CONTENT = '''from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.models.safety_report import SafetyCategory


class SafetyReportCreate(BaseModel):
    category: SafetyCategory
    description: str | None = Field(default=None, max_length=500)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    walk_id: int | None = None


class SafetyReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: SafetyCategory
    description: str | None
    latitude: float
    longitude: float
    verified: bool
    created_at: datetime
    expires_at: datetime
    reporter_id: int
    reporter_name: str
    reporter_role: str
    walk_id: int | None


class SafetyReportAdminResponse(SafetyReportResponse):
    deleted: bool
    deleted_reason: str | None


class SafetyReportDeleteRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=300)
'''

with open(SCHEMA_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(SCHEMA_CONTENT)
print("[OK] schemas/safety_report.py")

# ============================================================
# 4) Router público /safety-reports
# ============================================================
ROUTER_PATH = r"C:\woffygo\app\routers\safety_reports.py"

ROUTER_CONTENT = '''from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.safety_report import SafetyReport, SafetyCategory
from app.schemas.safety_report import SafetyReportCreate, SafetyReportResponse


router = APIRouter(prefix="/safety-reports", tags=["safety-reports"])

EXPIRATION_DAYS = 30


def _to_response(db: Session, r: SafetyReport) -> SafetyReportResponse:
    name = "Usuario"
    try:
        u = db.get(User, r.reporter_id)
        if u is not None:
            name = u.full_name
    except Exception:
        pass
    return SafetyReportResponse(
        id=r.id,
        category=r.category,
        description=r.description,
        latitude=r.latitude,
        longitude=r.longitude,
        verified=r.verified,
        created_at=r.created_at,
        expires_at=r.expires_at,
        reporter_id=r.reporter_id,
        reporter_name=name,
        reporter_role=r.reporter_role,
        walk_id=r.walk_id,
    )


@router.post("", response_model=SafetyReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: SafetyReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crea un reporte de seguridad. Cualquier usuario logueado puede reportar."""
    now = datetime.now(timezone.utc)
    report = SafetyReport(
        reporter_id=current_user.id,
        reporter_role=current_user.role.value,
        walk_id=payload.walk_id,
        category=payload.category,
        description=payload.description,
        latitude=payload.latitude,
        longitude=payload.longitude,
        expires_at=now + timedelta(days=EXPIRATION_DAYS),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _to_response(db, report)


@router.get("/nearby", response_model=list[SafetyReportResponse])
def list_nearby(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(default=5.0, ge=0.5, le=50.0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista reportes activos (no vencidos, no eliminados) dentro del radio.

    Filtra por distancia usando Haversine aproximado (suficiente para radio chico).
    """
    now = datetime.now(timezone.utc)

    # Bounding box rapido antes del filtro exacto
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * max(0.1, abs(__import__("math").cos(__import__("math").radians(lat)))))

    q = (
        db.query(SafetyReport)
        .filter(SafetyReport.deleted.is_(False))
        .filter(SafetyReport.expires_at > now)
        .filter(SafetyReport.latitude >= lat - lat_delta)
        .filter(SafetyReport.latitude <= lat + lat_delta)
        .filter(SafetyReport.longitude >= lng - lng_delta)
        .filter(SafetyReport.longitude <= lng + lng_delta)
        .order_by(SafetyReport.created_at.desc())
        .limit(200)
    )

    import math

    def haversine_km(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return 2 * R * math.asin(math.sqrt(a))

    results = []
    for r in q.all():
        if haversine_km(lat, lng, r.latitude, r.longitude) <= radius_km:
            results.append(_to_response(db, r))
    return results
'''

with open(ROUTER_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(ROUTER_CONTENT)
print("[OK] routers/safety_reports.py")

# ============================================================
# 5) Endpoints admin en admin.py
# ============================================================
ADMIN_PATH = r"C:\woffygo\app\routers\admin.py"

backup = ADMIN_PATH + ".safety.bak"
if not os.path.exists(backup):
    shutil.copyfile(ADMIN_PATH, backup)
    print("[BACKUP] " + backup)

with open(ADMIN_PATH, "r", encoding="utf-8") as f:
    src = f.read()

if "safety-reports" in src or "SafetyReport" in src:
    print("[SKIP] endpoints admin de safety ya existen")
else:
    # Agregar imports
    viejo_imports = "from app.services.admin_log import log_action"
    nuevo_imports = (
        viejo_imports + "\n"
        "from app.models.safety_report import SafetyReport\n"
        "from app.schemas.safety_report import SafetyReportAdminResponse, SafetyReportDeleteRequest"
    )
    if viejo_imports not in src:
        print("[FAIL] no encontre imports base en admin.py")
        sys.exit(1)
    src = src.replace(viejo_imports, nuevo_imports, 1)

    # Endpoints al final
    endpoints = '''

# ============================================
# Reportes de seguridad
# ============================================


@router.get("/safety-reports", response_model=list[SafetyReportAdminResponse])
def list_safety_reports(
    include_deleted: bool = False,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Lista reportes de seguridad. Por defecto solo los activos."""
    q = db.query(SafetyReport)
    if not include_deleted:
        q = q.filter(SafetyReport.deleted.is_(False))
    rows = q.order_by(SafetyReport.created_at.desc()).limit(200).all()

    out = []
    for r in rows:
        reporter_name = "Usuario"
        try:
            u = db.get(User, r.reporter_id)
            if u is not None:
                reporter_name = u.full_name
        except Exception:
            pass
        out.append(SafetyReportAdminResponse(
            id=r.id,
            category=r.category,
            description=r.description,
            latitude=r.latitude,
            longitude=r.longitude,
            verified=r.verified,
            created_at=r.created_at,
            expires_at=r.expires_at,
            reporter_id=r.reporter_id,
            reporter_name=reporter_name,
            reporter_role=r.reporter_role,
            walk_id=r.walk_id,
            deleted=r.deleted,
            deleted_reason=r.deleted_reason,
        ))
    return out


@router.post("/safety-reports/{report_id}/verify", response_model=SafetyReportAdminResponse)
def verify_safety_report(
    report_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Marca un reporte como verificado (util para destacar reportes validos)."""
    r = db.get(SafetyReport, report_id)
    if r is None or r.deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado")

    r.verified = True
    db.commit()
    db.refresh(r)

    try:
        log_action(db, current_user, "safety_verify", "safety_report", r.id,
                   f"Verifico el reporte #{r.id} ({r.category.value})")
    except Exception as _e:
        print(f"[admin_log] Error logueando safety_verify: {_e}")

    reporter_name = "Usuario"
    try:
        u = db.get(User, r.reporter_id)
        if u is not None:
            reporter_name = u.full_name
    except Exception:
        pass

    return SafetyReportAdminResponse(
        id=r.id, category=r.category, description=r.description,
        latitude=r.latitude, longitude=r.longitude, verified=r.verified,
        created_at=r.created_at, expires_at=r.expires_at,
        reporter_id=r.reporter_id, reporter_name=reporter_name,
        reporter_role=r.reporter_role, walk_id=r.walk_id,
        deleted=r.deleted, deleted_reason=r.deleted_reason,
    )


@router.delete("/safety-reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_safety_report(
    report_id: int,
    payload: SafetyReportDeleteRequest = None,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Elimina (soft delete) un reporte de seguridad."""
    r = db.get(SafetyReport, report_id)
    if r is None or r.deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado")

    r.deleted = True
    r.deleted_reason = (payload.reason if payload and payload.reason else "Eliminado por admin")[:300]
    db.commit()

    try:
        log_action(db, current_user, "safety_delete", "safety_report", r.id,
                   f"Elimino el reporte #{r.id} ({r.category.value}): {r.deleted_reason}")
    except Exception as _e:
        print(f"[admin_log] Error logueando safety_delete: {_e}")

    return None
'''

    src = src.rstrip() + endpoints
    with open(ADMIN_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    print("[OK] Endpoints admin de safety reports agregados")

# ============================================================
# 6) Registrar router en main.py
# ============================================================
MAIN_PATH = r"C:\woffygo\app\main.py"

backup = MAIN_PATH + ".safety.bak"
if not os.path.exists(backup):
    shutil.copyfile(MAIN_PATH, backup)
    print("[BACKUP] " + backup)

with open(MAIN_PATH, "r", encoding="utf-8") as f:
    main_src = f.read()

if "safety_reports" in main_src:
    print("[SKIP] router safety ya registrado en main")
else:
    # Buscar un import similar para basar
    import re
    m = re.search(r'from app\.routers import ([^\n]+)', main_src)
    if not m:
        print("[FAIL] no encontre import de routers en main.py")
        sys.exit(1)
    routers_actuales = m.group(1)
    if "safety_reports" not in routers_actuales:
        nuevo_import = "from app.routers import " + routers_actuales.rstrip() + ", safety_reports"
        main_src = main_src.replace(m.group(0), nuevo_import, 1)

    # Buscar donde se hace include_router
    m2 = re.search(r'app\.include_router\((\w+)\.router\)', main_src)
    if not m2:
        print("[FAIL] no encontre include_router en main.py")
        sys.exit(1)

    # Agregar despues del ultimo include_router
    ultimo = list(re.finditer(r'app\.include_router\([^)]+\)', main_src))[-1]
    main_src = (
        main_src[:ultimo.end()] +
        "\napp.include_router(safety_reports.router)" +
        main_src[ultimo.end():]
    )

    with open(MAIN_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(main_src)
    print("[OK] Router registrado en main.py")

print("\n[DONE] Feature Safety Reports backend listo")