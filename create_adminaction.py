import os, sys, shutil

# ============================================================
# 1) Crear modelo AdminAction
# ============================================================
MODEL_PATH = r"C:\woffygo\app\models\admin_action.py"

MODEL_CONTENT = '''from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AdminAction(Base):
    """Registro de acciones administrativas (auditoria)."""

    __tablename__ = "admin_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Snapshot del email del admin (por si el user se elimina)
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)

    # Tipo de accion: user_block, user_unblock, flag_clear, dispute_resolve
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Sobre que actuo: user, walk, payment
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Descripcion legible para el panel
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    admin = relationship("User", foreign_keys=[admin_id])
'''

with open(MODEL_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(MODEL_CONTENT)
print("[OK] models/admin_action.py")

# ============================================================
# 2) Registrar en models/__init__.py
# ============================================================
INIT_PATH = r"C:\woffygo\app\models\__init__.py"

backup = INIT_PATH + ".adminaction.bak"
if not os.path.exists(backup):
    shutil.copyfile(INIT_PATH, backup)
    print("[BACKUP] " + backup)

with open(INIT_PATH, "r", encoding="utf-8") as f:
    init_src = f.read()

if "AdminAction" in init_src:
    print("[SKIP] AdminAction ya registrado en __init__")
else:
    # Insertar la linea de import
    linea = "from app.models.admin_action import AdminAction\n"
    if "from app.models.device_token import DeviceToken" in init_src:
        init_src = init_src.replace(
            "from app.models.device_token import DeviceToken\n",
            "from app.models.device_token import DeviceToken\n" + linea,
            1
        )
    else:
        init_src = linea + init_src
    with open(INIT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(init_src)
    print("[OK] AdminAction registrado en __init__")

# ============================================================
# 3) Schema de AdminAction + Stats
# ============================================================
SCHEMA_PATH = r"C:\woffygo\app\schemas\admin_action.py"

SCHEMA_CONTENT = '''from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AdminActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_id: int | None
    admin_email: str
    action: str
    target_type: str
    target_id: int | None
    description: str
    created_at: datetime


class AdminStats(BaseModel):
    # Usuarios
    users_total: int
    users_active: int
    users_owners: int
    users_walkers: int
    users_admins: int
    walkers_online_now: int

    # Paseos
    walks_total: int
    walks_pending: int
    walks_accepted: int
    walks_in_progress: int
    walks_completed: int
    walks_cancelled: int
    walks_today: int
    walks_this_month: int

    # Dinero
    revenue_total: str
    revenue_this_month: str
    escrow_pending_total: str
    disputed_total: str

    # Moderacion
    flagged_walks: int
    disputed_payments: int
'''

with open(SCHEMA_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(SCHEMA_CONTENT)
print("[OK] schemas/admin_action.py")

print("\n[DONE] Modelo + schema creados")