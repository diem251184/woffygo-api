import os, sys, shutil

PATH = r"C:\woffygo\app\routers\admin.py"

backup = PATH + ".disputes.bak"
if not os.path.exists(backup):
    shutil.copyfile(PATH, backup)
    print("[BACKUP] " + backup)

with open(PATH, "rb") as f:
    src = f.read()

if b"disputed_payments" in src:
    print("[SKIP] ya tiene endpoint de disputas")
    sys.exit(0)

# 1) Agregar imports al inicio
viejo_imports = b'from app.services.verification import get_verification_summary'
nuevo_imports = (
    b'from app.services.verification import get_verification_summary\n'
    b'from app.models.payment import Payment, PaymentStatus\n'
    b'from app.schemas.payment import PaymentResponse'
)
if viejo_imports not in src:
    print("[FAIL] no encontre imports esperados")
    sys.exit(1)
src = src.replace(viejo_imports, nuevo_imports, 1)
print("[OK] Imports agregados")

# 2) Agregar el endpoint al final
endpoint = b'''


@router.get("/payments/disputed", response_model=list[PaymentResponse])
def list_disputed_payments(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Lista los pagos con disputa abierta, mas recientes primero."""
    return (
        db.query(Payment)
        .filter(Payment.status == PaymentStatus.DISPUTED)
        .order_by(Payment.dispute_opened_at.desc().nullslast(), Payment.created_at.desc())
        .all()
    )
'''

src = src.rstrip() + endpoint

with open(PATH, "wb") as f:
    f.write(src)

print("[DONE] Endpoint GET /admin/payments/disputed agregado")