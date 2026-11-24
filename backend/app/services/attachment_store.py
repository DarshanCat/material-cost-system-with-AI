"""Storage and validation of uploaded supporting documents (GRN attachments).

Files are checked on the SERVER before they are stored: size limit, an allow-list of file types, and the file's real
content (its first bytes) must match the type its name claims. The type served back is decided here from the extension,
never taken from the upload. The stored name is generated (the visitor's file name is only kept as a label), so a name
can never reach the file system or the bucket path.

Backends: "local" (a folder, for development) and "gcs" (a private Cloud Storage bucket, for production).
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from app.core.config import settings

# extension -> (content type served, magic-byte check)
ALLOWED_TYPES: dict[str, tuple[str, tuple[bytes, ...]]] = {
    "pdf": ("application/pdf", (b"%PDF-",)),
    "png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    "jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", (b"PK\x03\x04",)),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", (b"PK\x03\x04",)),
}
ALLOWED_EXTENSIONS_TEXT = ", ".join(sorted(ALLOWED_TYPES))


class AttachmentRejected(ValueError):
    """The upload failed validation; the message is safe to show to the user."""


@dataclass(frozen=True)
class CheckedUpload:
    display_name: str
    content_type: str
    size_bytes: int
    sha256: str


def safe_display_name(raw: Optional[str]) -> str:
    """The file name as a harmless label: no path, no control characters, bounded length."""
    name = (raw or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip().strip(".")
    name = re.sub(r"\s+", " ", name)
    return name[:150] or "document"


def check_upload(filename: Optional[str], data: bytes) -> CheckedUpload:
    max_bytes = settings.ATTACHMENT_MAX_MB * 1024 * 1024
    if not data:
        raise AttachmentRejected("The file is empty.")
    if len(data) > max_bytes:
        raise AttachmentRejected(f"The file is larger than {settings.ATTACHMENT_MAX_MB} MB.")
    display = safe_display_name(filename)
    ext = display.rsplit(".", 1)[-1].lower() if "." in display else ""
    if ext not in ALLOWED_TYPES:
        raise AttachmentRejected(f"This file type is not allowed. Allowed: {ALLOWED_EXTENSIONS_TEXT}.")
    content_type, magics = ALLOWED_TYPES[ext]
    if not any(data.startswith(m) for m in magics):
        raise AttachmentRejected("The file content does not match its type. Upload the original document.")
    return CheckedUpload(display, content_type, len(data), hashlib.sha256(data).hexdigest())


def new_storage_key(prefix: str, display_name: str) -> str:
    """A generated key such as grn/12/9f3a...c1.pdf (only the validated extension comes from the file name)."""
    ext = display_name.rsplit(".", 1)[-1].lower()
    return f"{prefix}/{secrets.token_hex(16)}.{ext}"


class AttachmentStore(Protocol):
    def save(self, key: str, data: bytes, content_type: str) -> None: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStore:
    def __init__(self, root: str):
        self._root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if self._root not in path.parents:
            raise ValueError("invalid storage key")
        return path

    def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            pass


class GcsStore:
    def __init__(self, bucket: str):
        if not bucket:
            raise RuntimeError("ATTACHMENT_BUCKET is not set.")
        from google.cloud import storage  # imported lazily: only the cloud deployment needs it

        self._bucket = storage.Client().bucket(bucket)

    def save(self, key: str, data: bytes, content_type: str) -> None:
        self._bucket.blob(key).upload_from_string(data, content_type=content_type)

    def read(self, key: str) -> bytes:
        return self._bucket.blob(key).download_as_bytes()

    def delete(self, key: str) -> None:
        blob = self._bucket.blob(key)
        if blob.exists():
            blob.delete()


_store: Optional[AttachmentStore] = None


def get_attachment_store() -> AttachmentStore:
    """FastAPI dependency (replaced in tests)."""
    global _store
    if _store is None:
        if settings.ATTACHMENT_STORAGE == "gcs":
            _store = GcsStore(settings.ATTACHMENT_BUCKET)
        else:
            _store = LocalStore(os.path.abspath(settings.ATTACHMENT_LOCAL_DIR))
    return _store
