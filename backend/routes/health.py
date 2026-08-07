"""Health and readiness endpoints."""

from __future__ import annotations

from typing import Any

import httpx
from flask import Blueprint, current_app, jsonify

import config

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health() -> Any:
    """Liveness only - never touches downstream services."""
    return jsonify({"status": "ok", "service": "agent-backend"})


@health_bp.get("/ready")
def ready() -> Any:
    """Readiness: reports on the dependencies an agent turn actually needs."""
    checks = {"ollama": _check_ollama(), "mcp": _check_mcp()}
    ready_now = all(c["ok"] for c in checks.values())
    return (
        jsonify({"status": "ready" if ready_now else "degraded", "checks": checks}),
        200 if ready_now else 503,
    )


def _check_ollama() -> dict[str, Any]:
    # Read through the module: the settings page can repoint these at runtime.
    url, model = config.OLLAMA_BASE_URL, config.OLLAMA_MODEL
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{url}/api/tags")
            resp.raise_for_status()
            names = [m.get("name") for m in resp.json().get("models", [])]
        return {
            "ok": model in names,
            "url": url,
            "model": model,
            "detail": (
                "model loaded" if model in names else f"model '{model}' not pulled"
            ),
        }
    except Exception as exc:
        return {"ok": False, "url": url, "model": model, "detail": str(exc)}


def _check_mcp() -> dict[str, Any]:
    try:
        tools = current_app.extensions["mcp_service"].list_tools()
        return {"ok": True, "url": config.MCP_URL, "tools": tools["count"]}
    except Exception as exc:
        return {"ok": False, "url": config.MCP_URL, "detail": str(exc)}
