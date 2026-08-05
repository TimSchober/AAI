"""Turn LangChain / LangGraph objects into plain JSON-friendly structures."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage

_ROLES = {
    "human": "user",
    "ai": "assistant",
    "system": "system",
    "tool": "tool",
}


def message_to_dict(message: BaseMessage) -> dict[str, Any]:
    role = _ROLES.get(message.type, message.type)
    data: dict[str, Any] = {
        "role": role,
        "content": _content_to_text(message.content),
    }

    if message.id:
        data["id"] = message.id

    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        data["tool_calls"] = [
            {
                "id": call.get("id"),
                "name": call.get("name"),
                "args": call.get("args", {}),
            }
            for call in tool_calls
        ]

    if name := getattr(message, "name", None):
        data["name"] = name
    if tool_call_id := getattr(message, "tool_call_id", None):
        data["tool_call_id"] = tool_call_id

    return data


def _content_to_text(content: Any) -> str:
    """Flatten the block-style content LangChain may return into text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content) if content is not None else ""


def tool_to_dict(tool: Any) -> dict[str, Any]:
    """Describe an MCP-backed LangChain tool for the API."""
    schema = getattr(tool, "args_schema", None)
    if schema is not None and not isinstance(schema, dict):
        schema = (
            schema.model_json_schema()
            if hasattr(schema, "model_json_schema")
            else None
        )

    return {
        "name": tool.name,
        "description": (tool.description or "").strip(),
        "input_schema": schema,
    }
