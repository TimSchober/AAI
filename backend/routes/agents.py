"""Endpoints for listing and talking to the agents in ./agents."""

from __future__ import annotations

import json
import uuid
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

agents_bp = Blueprint("agents", __name__, url_prefix="/api/agents")


def _service() -> Any:
    return current_app.extensions["agent_service"]


def _payload() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def _message_and_thread() -> tuple[str, str]:
    body = _payload()
    message = (body.get("message") or "").strip()
    thread_id = body.get("thread_id") or uuid.uuid4().hex
    return message, thread_id


@agents_bp.get("")
def list_agents() -> Any:
    agents = _service().list_agents()
    return jsonify({"count": len(agents), "agents": agents})


@agents_bp.post("/<agent_id>/chat")
def chat(agent_id: str) -> Any:
    message, thread_id = _message_and_thread()
    if not message:
        return jsonify({"error": "field 'message' is required"}), 400
    return jsonify(_service().chat(agent_id, message, thread_id))


@agents_bp.post("/<agent_id>/chat/stream")
def chat_stream(agent_id: str) -> Any:
    message, thread_id = _message_and_thread()
    if not message:
        return jsonify({"error": "field 'message' is required"}), 400

    # Bind these now: the generator below runs after the request context is
    # gone, so `current_app` is no longer available inside it.
    service = _service()
    logger = current_app.logger
    # Surface an unknown agent as a 404 rather than an error event mid-stream.
    service.ensure_exists(agent_id)

    def events() -> Any:
        yield _sse({"type": "start", "agent": agent_id, "thread_id": thread_id})
        try:
            for event in service.stream(agent_id, message, thread_id):
                yield _sse(event)
        except Exception as exc:
            logger.exception("streaming turn failed")
            yield _sse({"type": "error", "error": str(exc)})
        yield _sse({"type": "end", "thread_id": thread_id})

    return Response(
        events(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@agents_bp.get("/<agent_id>/threads/<thread_id>")
def history(agent_id: str, thread_id: str) -> Any:
    return jsonify(_service().history(agent_id, thread_id))


@agents_bp.delete("/<agent_id>/threads/<thread_id>")
def reset_thread(agent_id: str, thread_id: str) -> Any:
    return jsonify(_service().reset_thread(agent_id, thread_id))


def _sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
