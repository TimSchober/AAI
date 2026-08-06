"""
Image attachments on a chat request.

A chat turn arrives either as JSON or as `multipart/form-data` with real file parts. This accepts both.
"""

from __future__ import annotations

import base64
import binascii
import re
import uuid
from dataclasses import dataclass
from typing import Any

from werkzeug.datastructures import FileStorage

from config import ALLOWED_IMAGE_TYPES, MAX_UPLOAD_MB

MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

_DATA_URL = re.compile(r"^data:(?P<mime>[\w.+-]+/[\w.+-]+);base64,(?P<data>.+)$", re.S)


class AttachmentError(ValueError):
    """Raised when an attachment is unusable; carries an HTTP status."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Attachment:
    filename: str
    mime_type: str
    data: bytes

    @property
    def base64(self) -> str:
        return base64.b64encode(self.data).decode("ascii")

    @property
    def data_url(self) -> str:
        """The form the OpenAI-compatible vision API expects."""
        return f"data:{self.mime_type};base64,{self.base64}"

    def describe(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size": len(self.data),
        }


def parse_chat_request(request: Any) -> tuple[str, str | None, list[Attachment]]:
    """Return (message, thread_id, attachments) for a chat request."""
    if request.mimetype == "multipart/form-data":
        message = request.form.get("message", "")
        thread_id = request.form.get("thread_id") or None
        attachments = [
            _from_file(f) for f in request.files.getlist("images") if f.filename
        ]
    else:
        body = request.get_json(silent=True) or {}
        message = body.get("message") or ""
        thread_id = body.get("thread_id") or None
        attachments = [_from_data_url(item) for item in body.get("images") or []]

    _check_total_size(attachments)
    return message.strip(), thread_id, attachments


def _from_file(part: FileStorage) -> Attachment:
    data = part.read()
    mime = (part.mimetype or "").lower()
    return _validated(part.filename or _generated_name(mime), mime, data)


def _from_data_url(item: Any) -> Attachment:
    """Accept either a bare data URL or {"filename": ..., "data": <data URL>}."""
    filename = ""
    if isinstance(item, dict):
        filename = item.get("filename") or ""
        item = item.get("data") or ""
    if not isinstance(item, str):
        raise AttachmentError("images must be data URLs or {filename, data} objects")

    match = _DATA_URL.match(item.strip())
    if not match:
        raise AttachmentError("image is not a base64 data URL")
    mime = match.group("mime").lower()
    try:
        data = base64.b64decode(match.group("data"), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AttachmentError(f"image is not valid base64: {exc}") from exc

    return _validated(filename or _generated_name(mime), mime, data)


def _validated(filename: str, mime: str, data: bytes) -> Attachment:
    if mime not in ALLOWED_IMAGE_TYPES:
        raise AttachmentError(
            f"unsupported image type '{mime}', allowed: "
            f"{', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
            status=415,
        )
    if not data:
        raise AttachmentError(f"image '{filename}' is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise AttachmentError(
            f"image '{filename}' exceeds the {MAX_UPLOAD_MB} MB limit", status=413
        )
    return Attachment(filename=_safe_name(filename), mime_type=mime, data=data)


def _check_total_size(attachments: list[Attachment]) -> None:
    if sum(len(a.data) for a in attachments) > MAX_UPLOAD_BYTES:
        raise AttachmentError(
            f"the attachments exceed the {MAX_UPLOAD_MB} MB limit in total", status=413
        )


def _safe_name(filename: str) -> str:
    """Strip any path components a client may have sent along."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    return re.sub(r"[^\w.\- ]", "_", name)[:120] or "bild"


def _generated_name(mime: str) -> str:
    return f"upload-{uuid.uuid4().hex[:8]}.{mime.rsplit('/', 1)[-1]}"
