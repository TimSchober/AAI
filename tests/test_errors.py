"""
Tests for `backend.errors`.
"""

from __future__ import annotations

import httpx
import pytest

import config
from backend.errors import friendly_message, is_connection_error


def nested_connect_error() -> Exception:
    """The shape a failed model call really has."""
    try:
        try:
            raise httpx.ConnectError("All connection attempts failed")
        except httpx.ConnectError as inner:
            raise RuntimeError("Connection error.") from inner
    except RuntimeError as outer:
        return outer


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (httpx.ConnectError("refused"), True),
        (httpx.ConnectTimeout("timed out"), True),
        (ConnectionRefusedError(111, "refused"), True),
        (nested_connect_error(), True),
        (ValueError("something else"), False),
        (httpx.HTTPStatusError("500", request=None, response=None), False),  # type: ignore[arg-type]
    ],
)
def test_connection_failures_are_recognised_through_the_cause_chain(
    exc: Exception, expected: bool
) -> None:
    assert is_connection_error(exc) is expected


def test_a_connection_failure_names_the_addresses_to_check() -> None:
    message = friendly_message(nested_connect_error())

    assert config.OLLAMA_BASE_URL in message
    assert config.MCP_URL in message
    assert "/ready" in message
    assert "Einstellungen" in message


def test_any_other_failure_is_passed_through_unchanged() -> None:
    assert friendly_message(ValueError("kaputt")) == "kaputt"


def test_a_self_referencing_cause_chain_terminates() -> None:
    """Guards the loop that walks __cause__/__context__."""
    first = ValueError("a")
    second = ValueError("b")
    first.__cause__ = second
    second.__cause__ = first

    assert is_connection_error(first) is False
