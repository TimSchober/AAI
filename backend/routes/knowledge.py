"""
Endpoints behind the knowledge-base page.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from werkzeug.datastructures import FileStorage

import config

knowledge_bp = Blueprint("knowledge", __name__, url_prefix="/api/knowledge")

DOC_TYPES = (
    "lebenslauf",
    "motivation",
    "noten",
    "zeugnis",
    "arbeitszeugnis",
    "abschlusszeugnis",
    "praeferenz",
    "stellenangebot",
    "unternehmen",
    "anhang",
)

DOCUMENT_SUFFIXES = (".md", ".txt", ".json", ".pdf", ".csv")


def _service() -> Any:
    return current_app.extensions["mcp_service"]


def _call(tool: str, arguments: dict[str, Any]) -> Any:
    """Invoke an MCP tool and unwrap its result."""
    return _unwrap(_service().call_tool(tool, arguments).get("result"))


def _unwrap(result: Any) -> Any:
    """
    Decode what an MCP tool returned.

    langchain-mcp-adapters hands the result over as a list of content blocks
    ([{"type": "text", "text": "{...}"}]); older versions return the bare
    string. Both end up as the parsed JSON the tools actually produce.
    """
    if isinstance(result, (list, tuple)):
        texts = [
            block.get("text", "")
            for block in result
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        if not texts:
            return result
        result = "".join(texts)

    if isinstance(result, str):
        try:
            return json.loads(result)
        except ValueError:
            return result
    return result


@knowledge_bp.get("")
def overview() -> Any:
    """
    What is in the store, plus what the page may upload.

    An unreachable MCP server costs the counts, not the page: the form still
    renders and says why the numbers are missing.
    """
    counts: dict[str, Any] = {}
    unavailable = ""
    try:
        result = _call("list_knowledge", {})
        counts = result if isinstance(result, dict) else {}
    except Exception as exc:
        current_app.logger.warning("knowledge overview unavailable: %s", exc)
        unavailable = str(exc)

    return jsonify(
        {
            "counts": counts,
            "total": sum(int(v) for v in counts.values() if isinstance(v, int)),
            "doc_types": list(DOC_TYPES),
            "unavailable": unavailable,
            "accepts": {
                "documents": list(DOCUMENT_SUFFIXES),
                "images": sorted(config.ALLOWED_IMAGE_TYPES),
                "max_mb": config.MAX_UPLOAD_MB,
            },
        }
    )


@knowledge_bp.post("/documents")
def upload_documents() -> Any:
    """
    Take `multipart/form-data` with one or more `files` parts.

    Optional fields: `doc_type` (otherwise the MCP server infers it from the
    file name) and `caption`, which is stored alongside an image.
    """
    files = [f for f in request.files.getlist("files") if f.filename]
    if not files:
        return jsonify({"error": "no files in the request"}), 400

    doc_type = (request.form.get("doc_type") or "").strip().lower()
    if doc_type and doc_type not in DOC_TYPES:
        return (
            jsonify({"error": f"unknown doc_type '{doc_type}'", "allowed": list(DOC_TYPES)}),
            400,
        )
    caption = (request.form.get("caption") or "").strip()

    results = [_ingest(part, doc_type, caption) for part in files]
    stored = sum(r.get("stored", 0) for r in results if r["ok"])

    status = 200 if any(r["ok"] for r in results) else 415
    return (
        jsonify(
            {
                "results": results,
                "stored": stored,
                "counts": _counts_or_empty(),
            }
        ),
        status,
    )


def _ingest(part: FileStorage, doc_type: str, caption: str) -> dict[str, Any]:
    """One file: validate it here, store it through the MCP server."""
    name = Path(part.filename or "").name
    mime = (part.mimetype or "").lower()
    data = part.read()

    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    if not data:
        return _failed(name, "die Datei ist leer")
    if len(data) > limit:
        return _failed(name, f"größer als das Limit von {config.MAX_UPLOAD_MB} MB")

    suffix = Path(name).suffix.lower()
    is_image = mime in config.ALLOWED_IMAGE_TYPES
    if not is_image and suffix not in DOCUMENT_SUFFIXES:
        return _failed(
            name,
            "nicht unterstützt - erlaubt sind "
            f"{', '.join(DOCUMENT_SUFFIXES)} sowie {', '.join(sorted(config.ALLOWED_IMAGE_TYPES))}",
        )

    encoded = base64.b64encode(data).decode("ascii")
    try:
        if is_image:
            result = _call(
                "ingest_image",
                {
                    "filename": name,
                    "mime_type": mime,
                    "data_base64": encoded,
                    "caption": caption,
                },
            )
        else:
            result = _call(
                "ingest_file",
                {"filename": name, "data_base64": encoded, "doc_type": doc_type},
            )
    except Exception as exc:  # one bad file must not fail the whole upload
        current_app.logger.warning("ingesting %s failed: %s", name, exc)
        return _failed(name, str(exc))

    if not isinstance(result, dict):
        return _failed(name, str(result))

    return {
        "ok": True,
        "filename": name,
        "kind": "image" if is_image else "document",
        "doc_type": result.get("type") or (doc_type or "anhang"),
        "stored": int(result.get("stored") or 0),
        "source": result.get("source", name),
    }


def _failed(filename: str, reason: str) -> dict[str, Any]:
    return {"ok": False, "filename": filename, "error": reason}


def _counts_or_empty() -> dict[str, Any]:
    """The fresh totals for the UI; never worth failing the upload over."""
    try:
        counts = _call("list_knowledge", {})
        return counts if isinstance(counts, dict) else {}
    except Exception:
        return {}
