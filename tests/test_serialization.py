"""
Tests for `backend.serialization`: LangChain objects -> JSON for the frontend.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from backend.serialization import message_to_dict, tool_to_dict


@pytest.mark.parametrize(
    ("message", "role"),
    [
        (HumanMessage(content="hallo"), "user"),
        (AIMessage(content="moin"), "assistant"),
        (SystemMessage(content="du bist ein agent"), "system"),
    ],
)
def test_langchain_roles_map_to_api_roles(message, role: str) -> None:
    assert message_to_dict(message)["role"] == role


def test_block_style_content_is_flattened_to_text() -> None:
    """A vision turn arrives as content blocks; the API exposes plain text."""
    message = AIMessage(
        content=[
            {"type": "text", "text": "Im Lebenslauf steht: "},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,QQ=="}},
            {"type": "text", "text": "Python, Docker"},
        ]
    )

    assert message_to_dict(message)["content"] == "Im Lebenslauf steht: Python, Docker"


def test_tool_calls_are_reduced_to_id_name_and_args() -> None:
    message = AIMessage(
        content="",
        id="ai-1",
        tool_calls=[
            {
                "id": "call-1",
                "name": "search_jobs",
                "args": {"was": "Data Engineer", "wo": "Köln"},
                "type": "tool_call",
            }
        ],
    )

    data = message_to_dict(message)

    assert data["id"] == "ai-1"
    assert data["tool_calls"] == [
        {
            "id": "call-1",
            "name": "search_jobs",
            "args": {"was": "Data Engineer", "wo": "Köln"},
        }
    ]


def test_tool_result_keeps_the_call_it_answers() -> None:
    data = message_to_dict(
        ToolMessage(content="3 Treffer", name="search_jobs", tool_call_id="call-1")
    )

    assert data["role"] == "tool"
    assert data["name"] == "search_jobs"
    assert data["tool_call_id"] == "call-1"
    assert "tool_calls" not in data


def test_tool_to_dict_expands_a_pydantic_args_schema() -> None:
    class Args:
        @staticmethod
        def model_json_schema() -> dict:
            return {"type": "object", "properties": {"was": {"type": "string"}}}

    tool = SimpleNamespace(
        name="search_jobs",
        description="  Sucht Stellenangebote.  ",
        args_schema=Args,
    )

    assert tool_to_dict(tool) == {
        "name": "search_jobs",
        "description": "Sucht Stellenangebote.",
        "input_schema": {"type": "object", "properties": {"was": {"type": "string"}}},
    }


def test_tool_to_dict_survives_a_tool_without_schema_or_description() -> None:
    tool = SimpleNamespace(name="ping", description=None, args_schema=None)

    assert tool_to_dict(tool) == {
        "name": "ping",
        "description": "",
        "input_schema": None,
    }
