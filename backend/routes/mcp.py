"""Endpoints that surface the MCP server's tools to API clients."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, request

from config import MCP_URL

mcp_bp = Blueprint("mcp", __name__, url_prefix="/api/mcp")


def _service() -> Any:
    return current_app.extensions["mcp_service"]


@mcp_bp.get("/tools")
def list_tools() -> Any:
    refresh = request.args.get("refresh", "").lower() in {"1", "true", "yes"}
    payload = _service().list_tools(refresh=refresh)
    return jsonify({"server": MCP_URL, **payload})


@mcp_bp.post("/tools/<tool_name>/call")
def call_tool(tool_name: str) -> Any:
    body = request.get_json(silent=True) or {}
    arguments = body.get("arguments", body)
    if not isinstance(arguments, dict):
        return jsonify({"error": "'arguments' must be an object"}), 400
    return jsonify(_service().call_tool(tool_name, arguments))
