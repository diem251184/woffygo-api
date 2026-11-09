"""Seleccion y validacion estricta de referencias KYC.

No autentica usuarios, no firma URLs y no realiza conexiones.
El endpoint llamador debera validar rol y permisos previamente.
"""

import re
from urllib.parse import urlsplit

KYC_FIELDS = frozenset({
    "dni_front",
    "dni_back",
    "selfie",
    "license_front",
    "license_back",
    "vehicle_photo",
    "vehicle_cedula",
    "vehicle_insurance",
    "vehicle_inspection",
})

KYC_URL_FIELDS = frozenset(
    f"{name}_url" for name in KYC_FIELDS
)


class KYCDocumentAccessError(ValueError):
    """Referencia KYC ausente, antigua o no admitida."""


def select_authenticated_kyc_document(
    verification,
    document_type: str,
    expected_cloud_name: str,
) -> tuple[str, str]:
    """Devuelve (public_id, formato) de un documento validado.

    Solo valida referencias para el futuro almacenamiento
    Cloudinary authenticated. No concede acceso por si misma.
    """

    if not isinstance(document_type, str):
        raise KYCDocumentAccessError("Tipo de documento invalido")

    if document_type not in KYC_FIELDS:
        raise KYCDocumentAccessError("Tipo de documento no permitido")

    if (
        not isinstance(expected_cloud_name, str)
        or re.fullmatch(
            r"[A-Za-z0-9_-]+",
            expected_cloud_name,
            flags=re.ASCII,
        ) is None
    ):
        raise KYCDocumentAccessError("Cuenta Cloudinary invalida")

    if verification is None:
        raise KYCDocumentAccessError("Verificacion inexistente")

    user_id = getattr(verification, "user_id", None)

    if type(user_id) is not int or user_id <= 0:
        raise KYCDocumentAccessError("Propietario invalido")

    field = f"{document_type}_url"
    if field not in KYC_URL_FIELDS:
        raise KYCDocumentAccessError("Campo no permitido")

    value = getattr(verification, field, None)

    if not isinstance(value, str) or not value:
        raise KYCDocumentAccessError("Documento no disponible")

    if len(value) > 500:
        raise KYCDocumentAccessError("Referencia demasiado larga")

    parsed = urlsplit(value)

    if parsed.scheme != "https":
        raise KYCDocumentAccessError("Esquema no permitido")

    if parsed.hostname != "res.cloudinary.com":
        raise KYCDocumentAccessError("Origen no permitido")

    cloud_path = parsed.path.split("/")
    if (
        len(cloud_path) < 3
        or cloud_path[1] != expected_cloud_name
    ):
        raise KYCDocumentAccessError("Cuenta Cloudinary no autorizada")

    if parsed.username or parsed.password or parsed.port is not None:
        raise KYCDocumentAccessError("Autoridad no permitida")

    if parsed.query or parsed.fragment:
        raise KYCDocumentAccessError("Parametros no permitidos")

    prefix = (
        r"/[a-zA-Z0-9_-]+/image/authenticated/"
        r"v[0-9]+/woffygo/kyc/"
        + str(user_id)
        + r"/"
    )

    match = re.fullmatch(
        prefix
        + re.escape(document_type)
        + r"_([0-9a-f]{32})\.(jpg|jpeg|png|webp)",
        parsed.path,
        flags=re.ASCII,
    )

    if match is None:
        raise KYCDocumentAccessError(
            "Documento no corresponde al almacenamiento protegido"
        )

    identifier = (
        f"woffygo/kyc/{user_id}/"
        f"{document_type}_{match.group(1)}"
    )

    return identifier, match.group(2)
