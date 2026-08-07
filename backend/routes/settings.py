"""
Endpoints behind the settings page.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, request

import config
from backend import settings as settings_module

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")


@settings_bp.get("")
def read_settings() -> Any:
    return jsonify(settings_module.describe())


@settings_bp.put("")
def write_settings() -> Any:
    """
    Takes {"values": {KEY: value, ...}} - only the fields the user changed.

    Anything the backend reads itself is applied straight away; the response
    lists which other services still have to be restarted.
    """
    body = request.get_json(silent=True) or {}
    values = body.get("values", body)

    report = settings_module.update(values, on_live_change=_rebuild_services)
    return jsonify(report)


def _rebuild_services() -> None:
    """Throw away everything that captured the old configuration."""
    app = current_app._get_current_object()  # type: ignore[attr-defined]
    app.config["MAX_CONTENT_LENGTH"] = (config.MAX_UPLOAD_MB + 1) * 1024 * 1024
    app.extensions["mcp_service"].invalidate()
    app.extensions["agent_service"].invalidate()
