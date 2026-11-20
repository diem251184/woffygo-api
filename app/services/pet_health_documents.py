"""Private storage helpers for pet health documents.

Authorization and file-content validation belong to the API layer.
This module never returns a public image URL.
"""

import re
from uuid import uuid4

import cloudinary.uploader

# Initialize the same Cloudinary configuration used by existing services.
from app.services import cloudinary_service as _cloudinary_config


MAX_HEALTH_DOCUMENT_BYTES = 8 * 1024 * 1024

ALLOWED_HEALTH_DOCUMENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


def _valid_positive_id(value: int) -> bool:
    return type(value) is int and value > 0


def _document_folder(owner_id: int, pet_id: int) -> str:
    if not _valid_positive_id(owner_id):
        raise ValueError("Invalid pet owner")
    if not _valid_positive_id(pet_id):
        raise ValueError("Invalid pet identifier")

    return f"woffygo/pet-health/{owner_id}/{pet_id}"


def upload_pet_health_document(
    file_bytes: bytes,
    owner_id: int,
    pet_id: int,
    content_type: str,
) -> str:
    """Store an authenticated image; return only its Cloudinary ID."""
    folder = _document_folder(owner_id, pet_id)

    if content_type not in ALLOWED_HEALTH_DOCUMENT_TYPES:
        raise ValueError("Unsupported health document type")

    if not isinstance(file_bytes, bytes):
        raise ValueError("Invalid document data")

    if not 0 < len(file_bytes) <= MAX_HEALTH_DOCUMENT_BYTES:
        raise ValueError("Invalid document size")

    public_name = f"health_{uuid4().hex}"
    expected_id = f"{folder}/{public_name}"

    result = cloudinary.uploader.upload(
        file_bytes,
        folder=folder,
        public_id=public_name,
        overwrite=False,
        resource_type="image",
        type="authenticated",
    )

    if not isinstance(result, dict):
        raise RuntimeError("Invalid storage response")

    if result.get("public_id") != expected_id:
        raise RuntimeError("Unexpected stored document identifier")

    return expected_id


def delete_pet_health_document(
    public_id: str,
    owner_id: int,
    pet_id: int,
) -> bool:
    """Delete only a document belonging to this pet's private folder."""
    folder = _document_folder(owner_id, pet_id)

    if not isinstance(public_id, str):
        raise ValueError("Invalid document identifier")

    pattern = re.escape(folder) + r"/health_[0-9a-f]{32}"

    if re.fullmatch(pattern, public_id, flags=re.ASCII) is None:
        raise ValueError("Document outside permitted folder")

    result = cloudinary.uploader.destroy(
        public_id,
        resource_type="image",
        type="authenticated",
        invalidate=True,
    )

    return isinstance(result, dict) and result.get("result") == "ok"
