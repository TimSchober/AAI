"""Endpoints for listing and talking to the agents in ./agents."""

from __future__ import annotations

import json
import uuid
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from backend.attachments import Attachment, parse_chat_request
from backend.errors import friendly_message

agents_bp = Blueprint("agents", __name__, url_prefix="/api/agents")


def _service() -> Any:
    return current_app.extensions["agent_service"]


def _turn() -> tuple[str, str, list[Attachment]]:
    """Read one chat turn: JSON body or multipart with image parts."""
    message, thread_id, attachments = parse_chat_request(request)
    return message, thread_id or uuid.uuid4().hex, attachments


@agents_bp.get("")
def list_agents() -> Any:
    agents = _service().list_agents()
    return jsonify({"count": len(agents), "agents": agents})


@agents_bp.post("/<agent_id>/chat")
def chat(agent_id: str) -> Any:
    message, thread_id, attachments = _turn()
    if not message and not attachments:
        return jsonify({"error": "field 'message' or an image is required"}), 400
    return jsonify(_service().chat(agent_id, message, thread_id, attachments))


@agents_bp.post("/<agent_id>/chat/stream")
def chat_stream(agent_id: str) -> Any:
    message, thread_id, attachments = _turn()
    if not message and not attachments:
        return jsonify({"error": "field 'message' or an image is required"}), 400

    service = _service()
    logger = current_app.logger
    service.ensure_exists(agent_id)

    def events() -> Any:
        yield _sse(
            {
                "type": "start",
                "agent": agent_id,
                "thread_id": thread_id,
                "attachments": [a.describe() for a in attachments],
            }
        )
        try:
            for event in service.stream(agent_id, message, thread_id, attachments):
                yield _sse(event)
        except Exception as exc:
            logger.exception("streaming turn failed")
            yield _sse({"type": "error", "error": friendly_message(exc)})
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
