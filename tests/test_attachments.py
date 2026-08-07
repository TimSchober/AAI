"""
Tests for `backend.attachments`: what a chat turn is allowed to carry as an image.
"""

from __future__ import annotations

import base64
from io import BytesIO

import pytest
from flask import Flask, request

from backend import attachments
from backend.attachments import AttachmentError, parse_chat_request

PNG_BYTES = b"\x89PNG\r\n\x1a\n not a real image, but bytes are bytes"
PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode("ascii")


@pytest.fixture
def app() -> Flask:
    """Only used to build real Werkzeug requests to parse."""
    return Flask(__name__)


@pytest.fixture(autouse=True)
def fixed_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the limits so the assertions do not depend on the local .env."""
    monkeypatch.setattr(
        attachments, "ALLOWED_IMAGE_TYPES", frozenset({"image/png", "image/jpeg"})
    )
    monkeypatch.setattr(attachments, "MAX_UPLOAD_MB", 1)
    monkeypatch.setattr(attachments, "MAX_UPLOAD_BYTES", 1024 * 1024)


def test_json_data_url_becomes_an_attachment(app: Flask) -> None:
    with app.test_request_context(
        json={
            "message": "  Was steht auf dem Lebenslauf?  ",
            "thread_id": "t-1",
            "images": [{"filename": "lebenslauf.png", "data": PNG_DATA_URL}],
        }
    ):
        message, thread_id, files = parse_chat_request(request)

    assert message == "Was steht auf dem Lebenslauf?"
    assert thread_id == "t-1"
    assert len(files) == 1

    image = files[0]
    assert image.filename == "lebenslauf.png"
    assert image.mime_type == "image/png"
    assert image.data == PNG_BYTES
    assert image.data_url == PNG_DATA_URL
    assert image.describe() == {
        "filename": "lebenslauf.png",
        "mime_type": "image/png",
        "size": len(PNG_BYTES),
    }


def test_bare_data_url_gets_a_generated_filename(app: Flask) -> None:
    with app.test_request_context(json={"message": "hi", "images": [PNG_DATA_URL]}):
        _, thread_id, files = parse_chat_request(request)

    assert thread_id is None
    assert files[0].filename.startswith("upload-")
    assert files[0].filename.endswith(".png")


def test_multipart_upload_is_read_from_the_file_part(app: Flask) -> None:
    with app.test_request_context(
        content_type="multipart/form-data",
        data={
            "message": "Passt das zur Stelle?",
            "thread_id": "t-2",
            "images": (BytesIO(PNG_BYTES), "zeugnis.png", "image/png"),
        },
    ):
        message, thread_id, files = parse_chat_request(request)

    assert (message, thread_id) == ("Passt das zur Stelle?", "t-2")
    assert [(f.filename, f.mime_type, f.data) for f in files] == [
        ("zeugnis.png", "image/png", PNG_BYTES)
    ]


def test_client_supplied_path_is_stripped_from_the_filename(app: Flask) -> None:
    with app.test_request_context(
        json={
            "message": "",
            "images": [{"filename": "../../etc/passwd.png", "data": PNG_DATA_URL}],
        }
    ):
        _, _, files = parse_chat_request(request)

    assert files[0].filename == "passwd.png"


@pytest.mark.parametrize(
    ("payload", "status", "fragment"),
    [
        (
            {"images": ["data:application/pdf;base64,QQ=="]},
            415,
            "unsupported image type",
        ),
        ({"images": ["not-a-data-url"]}, 400, "not a base64 data URL"),
        ({"images": ["data:image/png;base64,!!!not-base64!!!"]}, 400, "valid base64"),
        ({"images": ["data:image/png;base64,"]}, 400, "not a base64 data URL"),
        ({"images": [123]}, 400, "must be data URLs"),
    ],
)
def test_unusable_images_are_rejected(
    app: Flask, payload: dict, status: int, fragment: str
) -> None:
    with app.test_request_context(json={"message": "x", **payload}):
        with pytest.raises(AttachmentError) as excinfo:
            parse_chat_request(request)

    assert excinfo.value.status == status
    assert fragment in str(excinfo.value)


def test_single_image_over_the_limit_is_rejected(app: Flask) -> None:
    oversized = base64.b64encode(b"x" * (attachments.MAX_UPLOAD_BYTES + 1)).decode()
    with app.test_request_context(
        json={"message": "x", "images": [f"data:image/png;base64,{oversized}"]}
    ):
        with pytest.raises(AttachmentError) as excinfo:
            parse_chat_request(request)

    assert excinfo.value.status == 413
    assert "1 MB limit" in str(excinfo.value)


def test_images_that_only_together_exceed_the_limit_are_rejected(app: Flask) -> None:
    half = base64.b64encode(b"x" * (attachments.MAX_UPLOAD_BYTES // 2 + 1)).decode()
    data_url = f"data:image/png;base64,{half}"
    with app.test_request_context(
        json={"message": "x", "images": [data_url, data_url]}
    ):
        with pytest.raises(AttachmentError) as excinfo:
            parse_chat_request(request)

    assert excinfo.value.status == 413
    assert "in total" in str(excinfo.value)
