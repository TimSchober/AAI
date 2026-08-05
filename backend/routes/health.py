"""Health and readiness endpoints."""

from __future__ import annotations

from typing import Any

import httpx
from flask import Blueprint, current_app, jsonify

from config import MCP_URL, OLLAMA_BASE_URL, OLLAMA_MODEL

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
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            names = [m.get("name") for m in resp.json().get("models", [])]
        return {
            "ok": OLLAMA_MODEL in names,
            "url": OLLAMA_BASE_URL,
            "model": OLLAMA_MODEL,
            "detail": (
                "model loaded"
                if OLLAMA_MODEL in names
                else f"model '{OLLAMA_MODEL}' not pulled"
            ),
        }
    except Exception as exc:
        return {"ok": False, "url": OLLAMA_BASE_URL, "detail": str(exc)}


def _check_mcp() -> dict[str, Any]:
    try:
        tools = current_app.extensions["mcp_service"].list_tools()
        return {"ok": True, "url": MCP_URL, "tools": tools["count"]}
    except Exception as exc:
        return {"ok": False, "url": MCP_URL, "detail": str(exc)}
